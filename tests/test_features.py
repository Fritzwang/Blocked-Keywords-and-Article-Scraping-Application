import sqlite3
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from clipdesk.i18n import t, translate, STRINGS
from clipdesk.models import Article
from clipdesk.replacement import Rule, preview
from clipdesk.storage import Store
from clipdesk.ui import App, ReplaceDialog


class LanguageTests(unittest.TestCase):
    def test_zh_en_and_fallback(self):
        self.assertEqual(t('删除这篇文章', 'zh'), '删除这篇文章')
        self.assertEqual(t('删除这篇文章', 'en'), 'Delete Article')
        self.assertEqual(t('unknown', 'en'), 'unknown')
        self.assertEqual(t('删除这篇文章', 'unknown'), '删除这篇文章')
        self.assertEqual(STRINGS['zh'].keys(), STRINGS['en'].keys())

    def test_dynamic_messages_and_error_translation(self):
        self.assertEqual(t('缺失词 {number}', 'en', number=2), 'Missing Word 2')
        self.assertEqual(translate('答对 2 / 5', 'en'), '2 / 5 Correct')
        self.assertEqual(translate('2 / 5 Correct', 'zh', 'en'), '答对 2 / 5')
        self.assertEqual(translate('网页访问失败（HTTP 503）。', 'en'), 'Page request failed (HTTP 503).')
        self.assertEqual(translate('User article text', 'en'), 'User article text')


class DeleteAllStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'test.db')
        for name in ('A', 'B', 'C'):
            self.store.save(Article(title=name, body='before'))
        self.store.apply(preview(self.store.all(), [Rule('before', 'after')]))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_all_and_history_removed_idempotently(self):
        self.store.delete_all()
        self.assertEqual(self.store.all(), [])
        self.assertEqual(self.store.undo_batch(), 0)
        self.store.delete_all()
        self.assertEqual(self.store.all(), [])

    def test_transaction_rolls_back_on_failure(self):
        before = [a.to_dict() for a in self.store.all()]
        self.store.db.execute("CREATE TRIGGER fail_history BEFORE DELETE ON history BEGIN SELECT RAISE(ABORT, 'test'); END")
        with self.assertRaises(sqlite3.Error):
            self.store.delete_all()
        self.assertEqual([a.to_dict() for a in self.store.all()], before)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM history').fetchone()[0], 1)


class FeatureUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.app = App(self.root, Path(self.temp.name))
        self.article = Article(title='Title 标题', body='Forest river forest city.')
        self.app.store.save(self.article)
        self.app.store.save(Article(title='Other', body='Other forest'))
        self.app.show_article(self.article)
        self.root.update()

    def tearDown(self):
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.app.store.close()
        self.root.destroy()
        self.temp.cleanup()
        self.assertEqual(self.errors, [])

    def test_language_roundtrip_preserves_unsaved_editor_and_menu(self):
        self.app.title_var.set('unsaved 标题')
        self.app.editor.insert('end', ' unsaved')
        self.app.search.set('Forest')
        before = self.app.store.get(self.article.id).to_dict()
        editor = self.app.editor
        for language, label in [('en', 'Delete All Articles...'), ('zh', '删除所有文章...')]:
            self.app.set_language(language)
            self.root.update()
            self.assertEqual(self.app.article_popup.entrycget(3, 'label'), label)
            self.assertEqual(self.app.title_var.get(), 'unsaved 标题')
            self.assertTrue(self.app.editor.get('1.0', 'end-1c').endswith(' unsaved'))
            self.assertIs(editor, self.app.editor)
            self.assertEqual(self.app.current.id, self.article.id)
            self.assertEqual(self.app.search.get(), 'Forest')
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)

    def test_delete_all_cancel_then_confirm(self):
        self.app.search.set('Title')
        self.app.title_var.set('unsaved')
        before = [article.to_dict() for article in self.app.store.all()]
        with patch('clipdesk.ui.messagebox.askyesno', return_value=False) as confirm:
            self.app.delete_all_articles()
        self.assertIn('2', confirm.call_args.args[1])
        self.assertEqual([article.to_dict() for article in self.app.store.all()], before)
        self.assertEqual(self.app.title_var.get(), 'unsaved')
        self.app.set_language('en')
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True) as confirm:
            self.app.delete_all_articles()
        self.root.update()
        self.assertIn('all 2 articles', confirm.call_args.args[1])
        self.assertEqual(self.app.store.all(), [])
        self.assertIsNone(self.app.current)
        self.assertIsNone(self.app.save_job)
        self.assertEqual(self.app.title_var.get(), '')
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), '')
        self.assertEqual(self.app.drafts.get_children(), ())
        self.assertEqual(self.app.draft_count.get(), '0 / 0 articles')

    def test_delete_all_failure_keeps_editor_and_database(self):
        self.app.title_var.set('pending')
        before = [article.to_dict() for article in self.app.store.all()]
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True), \
                patch.object(self.app.store, 'delete_all', side_effect=sqlite3.OperationalError('disk')), \
                patch.object(self.app, 'error') as error:
            self.app.delete_all_articles()
        error.assert_called_once()
        self.assertEqual([article.to_dict() for article in self.app.store.all()], before)
        self.assertEqual(self.app.title_var.get(), 'pending')
        self.assertEqual(self.app.current.id, self.article.id)
        self.assertIsNotNone(self.app.save_job)

    def test_challenge_test_reveal_reset_return_and_language(self):
        before = self.app.store.get(self.article.id).to_dict()
        dialog = self.app.open_challenge()
        self.root.update()
        self.assertEqual(dialog.challenge.targets, ('forest', 'river', 'city'))
        self.assertEqual(len(dialog.answers), 3)
        self.assertEqual(dialog.text.get('1.0', 'end-1c'), '***** ***** ***** *****.')
        dialog.answers[0].set(' Forest ')
        dialog.answers[1].set('cat')
        dialog.test()
        self.assertEqual(dialog.text.get('1.0', 'end-1c'), 'Forest ***** forest *****.')
        self.assertEqual(dialog.challenge.results, ['correct', 'incorrect', 'unanswered'])
        self.assertEqual([v.get() for v in dialog.answer_vars], ['', '', ''])
        self.app.set_language('en')
        self.assertEqual(dialog.window.title(), 'Regrowth Challenge')
        self.assertEqual([v.get() for v in dialog.result_vars], ['✅ Correct', '❌ Incorrect', '⚪ Not answered'])
        with patch('clipdesk.challenge_ui.messagebox.askyesno', return_value=False):
            dialog.reveal()
        self.assertFalse(dialog.challenge.revealed)
        with patch('clipdesk.challenge_ui.messagebox.askyesno', return_value=True), \
                patch.object(self.app.store, 'save') as save:
            dialog.reveal()
            save.assert_not_called()
        self.assertEqual(dialog.challenge.score, 1)
        self.assertEqual(dialog.summary.get(), 'Player Recovery: 1 / 3 · Revealed: 2 · Document Restoration: 100%')
        self.assertEqual(dialog.text.get('1.0', 'end-1c'), self.article.body)
        self.assertEqual([v.get() for v in dialog.answer_vars], ['Answer: forest', 'Answer: river', 'Answer: city'])
        self.app.set_language('zh')
        self.assertIn('已揭露：2', dialog.summary.get())
        dialog.new_challenge()
        self.assertFalse(dialog.challenge.revealed)
        self.assertEqual([v.get() for v in dialog.answers], ['', '', ''])
        self.assertEqual([v.get() for v in dialog.result_vars], ['', '', ''])
        dialog.window.destroy()
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), self.article.body)
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)
        self.assertEqual(len(self.app.store.all()), 2)

    def test_challenge_uses_unsaved_snapshot(self):
        self.app.editor.insert('end', ' orange')
        source = self.app.editor.get('1.0', 'end-1c')
        dialog = self.app.open_challenge()
        self.assertEqual(dialog.source, source)
        self.assertNotIn('*****', self.app.editor.get('1.0', 'end-1c'))
        dialog.window.destroy()
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), source)

    def test_no_current_article_and_no_candidates(self):
        self.app.show_empty()
        with patch('clipdesk.ui.messagebox.showinfo') as info:
            self.assertIsNone(self.app.open_challenge())
            info.assert_called_once()
        self.app.show_article(Article(title='Short', body='the and'))
        dialog = self.app.open_challenge()
        self.assertEqual(len(dialog.answers), 0)
        self.assertEqual(dialog.test_button.cget('state'), 'disabled')
        dialog.window.destroy()

    def test_english_replacement_current_all_and_undo(self):
        self.app.set_language('en')
        dialog = ReplaceDialog(self.app)
        dialog.find.set('forest')
        dialog.replace.set('woods')
        dialog.case.set(False)
        dialog.scope.set('Body Only')
        dialog.add_rule()
        dialog.make_preview()
        self.assertEqual(len(dialog.changes), 1)
        dialog.apply()
        self.assertIn('woods', self.app.current.body)
        self.app.undo_batch()
        self.assertEqual(self.app.current.body, self.article.body)

        dialog = ReplaceDialog(self.app)
        dialog.target.set('All Articles')
        dialog.rules = [Rule('forest', 'woods', 'body', False), Rule('woods', 'trees')]
        dialog.make_preview()
        self.assertEqual(len(dialog.changes), 2)
        dialog.apply()
        self.assertTrue(all('trees' in a.body for a in self.app.store.all()))
        self.app.undo_batch()
        self.assertEqual(self.app.current.body, self.article.body)

    def test_open_article_saves_previous_and_busy_actions_do_not_delete(self):
        target = next(a for a in self.app.store.all() if a.id != self.article.id)
        self.app.title_var.set('Unsaved Title')
        self.app.open_article_by_id(target.id)
        self.assertEqual(self.app.current.id, target.id)
        self.assertEqual(self.app.store.get(self.article.id).title, 'Unsaved Title')
        self.app.busy = True
        with patch('clipdesk.ui.messagebox.showinfo'), patch('clipdesk.ui.messagebox.askyesno') as confirm:
            self.app.delete_all_articles()
            self.assertIsNone(self.app.open_challenge())
            confirm.assert_not_called()
        self.assertEqual(len(self.app.store.all()), 2)

    def test_english_error_message(self):
        self.app.set_language('en')
        self.app.url_var.set('')
        with patch('clipdesk.ui.messagebox.showerror') as error:
            self.app.start_fetch()
        self.assertEqual(error.call_args.args, ('Invalid URL', 'Enter a web page URL first.'))

import sqlite3
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from clipdesk.models import Article
from clipdesk.storage import Store
from clipdesk.ui import App


class DeleteStorageTests(unittest.TestCase):
    def test_delete_specific_missing_and_remaining(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.db')
            try:
                a = Article(title='A', body='keep', original_body='original A')
                b = Article(title='B', body='remove', original_body='original B')
                store.save(a)
                store.save(b)
                store.delete(b.id)
                self.assertIsNone(store.get(b.id))
                self.assertEqual(store.get(a.id).to_dict(), a.to_dict())
                self.assertEqual([x.id for x in store.all()], [a.id])
                store.delete('missing')
                self.assertEqual([x.to_dict() for x in store.all()], [a.to_dict()])
            finally:
                store.close()


class DeleteUITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root, Path(self.temp.name))
        self.articles = [Article(title='match ' + name, body=name) for name in 'ABC']
        for index, article in enumerate(self.articles):
            self.app.store.save(article)
            self.app.store.db.execute('UPDATE articles SET updated=? WHERE id=?',
                                      (str(3 - index), article.id))
        self.app.store.db.commit()
        self.app.show_article(self.articles[0])
        self.root.update()

    def tearDown(self):
        for job in self.root.tk.call('after', 'info'):
            self.root.after_cancel(job)
        self.app.store.close()
        self.root.destroy()
        self.temp.cleanup()

    def test_noncurrent_saves_editor_and_preserves_search(self):
        a, b, c = self.articles
        self.app.search.set('match')
        self.app.title_var.set('match edited A')
        self.app.editor.insert('end', ' unsaved')
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True) as confirm:
            self.app.delete_article_by_id(b.id)
        self.root.update()
        self.assertIn('《match B》', confirm.call_args.args[1])
        self.assertEqual(self.app.current.id, a.id)
        self.assertEqual(self.app.store.get(a.id).body, 'A unsaved')
        self.assertEqual(self.app.title_var.get(), 'match edited A')
        self.assertIsNone(self.app.store.get(b.id))
        self.assertEqual(self.app.search.get(), 'match')
        self.assertEqual(set(self.app.drafts.get_children()), {a.id, c.id})

    def test_cancel_does_not_write_even_during_modal_loop(self):
        before = [x.to_dict() for x in self.app.store.all()]
        self.app.title_var.set('unsaved title')
        def cancel(*args, **kwargs):
            self.assertIsNone(self.app.save_job)
            self.root.update()
            return False
        with patch('clipdesk.ui.messagebox.askyesno', side_effect=cancel):
            self.app.delete_article_by_id(self.articles[1].id)
        self.assertEqual([x.to_dict() for x in self.app.store.all()], before)
        self.assertEqual(self.app.title_var.get(), 'unsaved title')

    def test_current_next_previous_and_empty(self):
        a, b, c = self.articles
        self.app.show_article(b)
        self.app.title_var.set('pending B')
        job = self.app.save_job
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True):
            self.app.delete_article()
            self.assertEqual(self.app.current.id, c.id)
            self.assertNotIn(job, self.root.tk.call('after', 'info'))
            self.app.delete_article()
            self.assertEqual(self.app.current.id, a.id)
            self.app.delete_article()
        self.root.update()
        self.assertIsNone(self.app.current)
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), '')
        self.assertEqual(self.app.store.all(), [])

    def test_filtered_last_result_keeps_filter(self):
        self.app.search.set('match A')
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True):
            self.app.delete_article()
        self.root.update()
        self.assertEqual(self.app.search.get(), 'match A')
        self.assertEqual(self.app.drafts.get_children(), ())
        self.assertIsNone(self.app.current)
        self.assertEqual(len(self.app.store.all()), 2)

    def test_failed_save_prevents_delete(self):
        self.app.title_var.set('unsaved')
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True), \
                patch.object(self.app.store, 'save', side_effect=sqlite3.OperationalError('disk')), \
                patch.object(self.app, 'error'):
            self.app.delete_article_by_id(self.articles[1].id)
        self.assertEqual(len(self.app.store.all()), 3)
        self.assertEqual(self.app.title_var.get(), 'unsaved')

    def test_real_treeview_right_click_and_blank(self):
        a, b, c = self.articles
        self.app.search.set('match')
        self.root.deiconify()
        self.root.update()
        x, y, width, height = self.app.drafts.bbox(b.id)
        with patch('clipdesk.ui.messagebox.askyesno', return_value=True) as confirm:
            # Windows' native popup runs its own modal loop, which can starve
            # Tk after callbacks. Drive the real Treeview event and Menu command
            # separately so this regression test never needs external input.
            with patch.object(self.app.article_popup, 'tk_popup') as popup:
                self.app.drafts.event_generate('<Button-3>', x=x + 10, y=y + height // 2)
                popup.assert_called_once()
            observed = (self.app.drafts.selection(), self.app.current.id)
            self.app.article_popup.invoke(1)
            self.root.update()
        self.assertEqual(observed, ((b.id,), a.id))
        self.assertEqual(confirm.call_count, 1, confirm.call_args_list)
        self.assertIn('《match B》', confirm.call_args.args[1])
        self.assertIsNone(self.app.store.get(b.id))
        self.assertEqual(self.app.current.id, a.id)
        self.assertEqual(self.app.search.get(), 'match')
        self.app.drafts.event_generate('<Button-3>', x=10, y=300)
        self.root.update()
        self.assertFalse(self.app.article_popup.winfo_ismapped())
        self.assertEqual(len(self.app.store.all()), 2)

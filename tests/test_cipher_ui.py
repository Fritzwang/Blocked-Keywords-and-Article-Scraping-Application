from dataclasses import asdict
import sqlite3
import tkinter as tk
from unittest.mock import patch
import unittest

import test_features


class CipherUITests(unittest.TestCase):
    setUp = test_features.FeatureUITests.setUp
    tearDown = test_features.FeatureUITests.tearDown

    def solve(self, dialog):
        rule = dialog.game.state.puzzle.rule
        dialog.multiplier.set(str(rule.multiplier))
        dialog.addend.set(str(rule.addend))
        dialog.submit_button.invoke()

    def test_article_required_and_reuse_one_dialog(self):
        self.app.current = None
        with patch('clipdesk.ui.messagebox.showinfo') as info:
            self.assertIsNone(self.app.open_cipher())
            self.assertEqual(info.call_count, 1)
        self.app.show_article(self.article)
        for body in ('', '这是一篇没有英文字母的文章。'):
            self.app.editor.delete('1.0', 'end')
            self.app.editor.insert('1.0', body)
            with patch('clipdesk.ui.messagebox.showinfo'):
                self.assertIsNone(self.app.open_cipher())
        self.app.editor.insert('end', ' English article.')
        dialog = self.app.open_cipher()
        self.assertIsNotNone(dialog)
        self.assertIs(self.app.open_cipher(), dialog)
        self.assertEqual(len(dialog.team.get_children()), 5)
        self.assertEqual(dialog.game.state.coins, 20)

    def test_solve_reset_and_editor_isolation(self):
        self.app.editor.insert('end', ' Unsaved draft!')
        self.root.update()
        if self.app.save_job:
            self.root.after_cancel(self.app.save_job)
            self.app.save_job = None
        editor = self.app.editor.get('1.0', 'end-1c')
        before = self.app.store.get(self.article.id).to_dict()
        writes = self.app.store.db.total_changes
        dialog = self.app.open_cipher()
        self.assertEqual(dialog.game.state.puzzle.plaintext, editor)
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), dialog.game.state.puzzle.ciphertext)
        self.solve(dialog)
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), editor)
        self.assertEqual(str(dialog.article_text.cget('state')), 'disabled')
        self.assertEqual(dialog.game.state.coins, 30)
        self.assertIn('+', self.app.t('答对 +10 币；自己答题免费。金币与队伍自动保存。'))
        self.assertEqual(dialog.submit_button.cget('state'), 'disabled')
        dialog.submit()
        self.assertEqual(dialog.game.state.coins, 30)
        dialog.next_button.invoke()
        self.assertEqual(dialog.multiplier.get(), '')
        self.assertEqual(dialog.addend.get(), '')
        self.assertFalse(dialog.game.state.puzzle.solved)
        self.assertEqual(dialog.submit_button.cget('state'), 'normal')
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), editor)
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)
        self.assertEqual(self.app.store.db.total_changes, writes)

    def test_long_article_scroll_and_language_preserve_full_content(self):
        body = ('Abc XYZ! 中文123.\nThis is the complete second paragraph.\n\n' * 500) + 'FinalLine zZ!\n'
        self.app.editor.delete('1.0', 'end')
        self.app.editor.insert('1.0', body)
        dialog = self.app.open_cipher()
        self.root.deiconify()
        self.root.update()
        self.assertEqual(dialog.game.state.puzzle.plaintext, body)
        encrypted = dialog.article_text.get('1.0', 'end-1c')
        self.assertEqual(encrypted, dialog.game.state.puzzle.ciphertext)
        self.assertNotEqual(encrypted, dialog.game.state.puzzle.rule.encrypt(body))
        dialog.article_text.yview_moveto(1)
        self.root.update()
        scroll = dialog.article_text.yview()
        self.assertGreater(scroll[0], 0)
        self.app.set_language('en')
        self.root.update()
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), encrypted)
        self.assertAlmostEqual(dialog.article_text.yview()[0], scroll[0], places=3)
        self.solve(dialog)
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), body)
        self.assertLess(len(dialog.feedback.get()), 150)
        dialog.close()
        self.app.editor.insert('end', 'New ending paragraph.')
        reopened = self.app.open_cipher()
        self.assertEqual(reopened.game.state.puzzle.plaintext, body + 'New ending paragraph.')
        self.assertEqual(reopened.game.state.coins, 30)
        self.assertFalse(reopened.game.state.puzzle.solved)

    def test_only_secondary_substitutions_are_shown_and_kept_on_refresh(self):
        dialog = self.app.open_cipher()
        puzzle = dialog.game.state.puzzle
        pairs = dict(puzzle.substitutions)
        self.assertFalse(hasattr(dialog, 'clues'))
        self.assertEqual(dialog.substitutions.get().count('→'), 4)  # Heading plus three pairs.
        self.assertNotIn('原字母', dialog.substitutions.get())
        self.assertIn('密文二次替换', dialog.substitutions.get())
        for a, b in pairs.items():
            self.assertIn(f'{a} → {b}', dialog.substitutions.get())
        ciphertext = dialog.article_text.get('1.0', 'end-1c')
        dialog.command_button.invoke()
        dialog.all_button.invoke()
        self.app.set_language('en')
        self.assertIn('Cipher substitutions', dialog.substitutions.get())
        self.assertEqual(dialog.game.state.puzzle.substitutions, pairs)
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), ciphertext)
        dialog.close()
        dialog = self.app.open_cipher()
        self.assertEqual(dialog.game.state.puzzle.substitutions, pairs)
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), ciphertext)
        self.solve(dialog)
        self.assertEqual(dialog.article_text.get('1.0', 'end-1c'), puzzle.plaintext)
        self.assertEqual(dialog.game.state.coins, 25)

    def test_inputs_reject_empty_text_fraction_and_out_of_range(self):
        dialog = self.app.open_cipher()
        for m, b in (('', ''), ('two', '1'), ('1.5', '1'), ('3', '1'), ('2', '5'), ('1', '-1')):
            dialog.multiplier.set(m)
            dialog.addend.set(b)
            dialog.submit_button.invoke()
            self.assertFalse(dialog.game.state.puzzle.solved)
            self.assertEqual(dialog.game.state.puzzle.attempts, 0)
            self.assertEqual(dialog.game.state.coins, 20)
            self.assertTrue(dialog.feedback.get())

    def test_command_controls_staff_and_persistence(self):
        dialog = self.app.open_cipher()
        dialog.command_button.invoke()
        dialog.all_button.invoke()
        self.assertEqual(dialog.game.state.coins, 15)
        self.assertTrue(all(bot.hint is not None for bot in dialog.game.state.robots))
        dialog.team.selection_set('2')
        self.root.update()
        dialog.dismiss_button.invoke()
        self.assertIsNone(dialog.game.state.robots[2])
        self.assertEqual(dialog.game.state.coins, 10)
        self.assertEqual(dialog.act_button.cget('state'), 'disabled')
        dialog.recruit_button.invoke()
        self.assertEqual(dialog.game.state.coins, 5)
        self.assertEqual(dialog.game.state.robots[2].number, 6)
        expected = asdict(dialog.game.state)
        dialog.close()
        reopened = self.app.open_cipher()
        self.assertEqual(asdict(reopened.game.state), expected)
        self.assertEqual(reopened.game.state.mode, 'command')

    def test_bilingual_refresh_preserves_inputs_coins_hints_and_selection(self):
        dialog = self.app.open_cipher()
        dialog.command_button.invoke()
        dialog.all_button.invoke()
        dialog.multiplier.set('2')
        dialog.addend.set('1')
        dialog.team.selection_set('3')
        before = asdict(dialog.game.state)
        self.app.set_language('en')
        self.assertEqual(dialog.window.title(), 'Cipher Challenge')
        self.assertIn('Coins: 15', dialog.wallet.get())
        self.assertIn('Dispatched 5 robots', dialog.feedback.get())
        def inspect(widget):
            if isinstance(widget, (tk.Button, tk.Label)):
                text = str(widget.cget('text'))
                if text != '中文 / EN':
                    self.assertNotRegex(text, '[\u4e00-\u9fff]')
            for child in widget.winfo_children():
                inspect(child)
        inspect(dialog.window)
        self.app.set_language('zh')
        self.assertEqual(asdict(dialog.game.state), before)
        self.assertEqual((dialog.multiplier.get(), dialog.addend.get()), ('2', '1'))
        self.assertEqual(dialog.team.selection(), ('3',))

    def test_zero_coins_disable_paid_controls_and_allow_solving(self):
        dialog = self.app.open_cipher()
        dialog.command_button.invoke()
        for _ in range(4):
            dialog.all_button.invoke()
        self.assertEqual(dialog.game.state.coins, 0)
        for control in (dialog.act_button, dialog.all_button, dialog.dismiss_button, dialog.recruit_button):
            self.assertEqual(control.cget('state'), 'disabled')
        self.assertEqual(dialog.submit_button.cget('state'), 'normal')
        self.solve(dialog)
        self.assertEqual(dialog.game.state.coins, 10)
        self.assertEqual(dialog.all_button.cget('state'), 'disabled')
        dialog.next_button.invoke()
        self.assertEqual(dialog.all_button.cget('state'), 'normal')

    def test_save_failure_is_reported_without_charge(self):
        dialog = self.app.open_cipher()
        dialog.command_button.invoke()
        before = asdict(dialog.game.state)
        with patch.object(dialog.game, '_save', side_effect=sqlite3.OperationalError('disk full')), \
                patch('clipdesk.cipher_ui.messagebox.showerror') as error:
            dialog.all_button.invoke()
        self.assertEqual(asdict(dialog.game.state), before)
        self.assertEqual(error.call_count, 1)
        self.assertIn('操作未保存', dialog.feedback.get())

    def test_command_layout_at_minimum_size_in_both_languages(self):
        self.root.deiconify()
        self.root.geometry('1000x680')
        dialog = self.app.open_cipher()
        dialog.command_button.invoke()
        dialog.window.geometry('860x680')
        for language in ('en', 'zh'):
            self.app.set_language(language)
            self.root.update()
            bottom = dialog.window.winfo_rooty() + dialog.window.winfo_height()
            for control in (dialog.team, dialog.submit_button, dialog.next_button,
                            dialog.act_button, dialog.all_button, dialog.recruit_button,
                            dialog.dismiss_button, dialog.team_note, dialog.footer,
                            dialog.article_text, dialog.article_scrollbar):
                self.assertTrue(control.winfo_ismapped(), f'{language}: {control}')
                self.assertGreater(control.winfo_height(), 15)
                self.assertLessEqual(control.winfo_rooty() + control.winfo_height(), bottom)
            self.assertLessEqual(dialog.team_note.winfo_rooty() + dialog.team_note.winfo_height(),
                                 dialog.footer.winfo_rooty())
            self.assertGreater(dialog.team.winfo_height(), 140)
            self.assertTrue(self.app.cipher_button.winfo_ismapped())
            self.assertGreater(self.app.cipher_button.winfo_width(), 80)

import tkinter as tk
import unittest
from unittest.mock import patch

import test_features
from test_reframe import STORY
from clipdesk.i18n import STRINGS


class ReframeUITests(unittest.TestCase):
    setUp = test_features.FeatureUITests.setUp
    def tearDown(self):
        self.root.update_idletasks()
        test_features.FeatureUITests.tearDown(self)

    def open_story(self):
        self.article.body = STORY
        self.app.store.save(self.article)
        self.app.show_article(self.article)
        self.root.update()
        return self.app.open_reframe()

    def test_choice_then_pure_three_rounds_result_and_editor_database_isolation(self):
        dialog = self.open_story()
        before = self.app.store.get(self.article.id).to_dict()
        self.assertIsNone(dialog.session.method)
        for language in ('en', 'zh'):
            self.app.set_language(language)
            self.assertIsNone(dialog.session.current_round)
        dialog.start('pure')
        for number in range(3):
            self.assertEqual(dialog.remove_button.cget('state'), 'disabled')
            self.assertIn(dialog.session.current_round.goal, STRINGS['en'])
            dialog.down_button.invoke()
            dialog.down_button.invoke()
            dialog.lock_button.invoke()
            if number < 2:
                self.assertEqual(dialog.next_button.cget('state'), 'normal')
                self.assertEqual(dialog.up_button.cget('state'), 'disabled')
                dialog.next_button.invoke()
        self.assertTrue(dialog.session.finished)
        self.assertEqual(dialog.original_box.get('1.0', 'end-1c'), STORY)
        self.assertEqual(dialog.final_box.get('1.0', 'end-1c'), dialog.session.working_copy)
        self.assertIn('处理轮数：3', dialog.stats.get())
        self.assertIn('上下文偏移', dialog.stats.get())
        self.assertNotIn('扭曲度', dialog.stats.get())
        dialog.window.destroy()
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), STORY)
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)

    def test_editorial_limits_restore_history_and_restart(self):
        dialog = self.open_story()
        dialog.start('editorial')
        self.assertEqual(dialog.remove_button.cget('state'), 'disabled')
        dialog.lock()
        dialog.next_round()
        original_order = list(dialog.session.current_round.order)
        removed = original_order[1]
        dialog.fragments.selection_set(removed)
        dialog.update_controls()
        dialog.remove_button.invoke()
        self.assertIn(removed, dialog.session.current_round.removed)
        self.assertEqual(dialog.remove_button.cget('state'), 'disabled')
        self.assertEqual(dialog.restore_button.cget('state'), 'normal')
        dialog.restore_button.invoke()
        self.assertEqual(dialog.session.current_round.order, original_order)
        dialog.remove_button.invoke()
        dialog.lock()
        dialog.next_round()
        dialog.remove()
        self.assertEqual(dialog.remove_button.cget('state'), 'normal')
        dialog.remove()
        self.assertEqual(dialog.remove_button.cget('state'), 'disabled')
        dialog.lock()
        self.assertEqual(dialog.session.fragments_removed, 3)
        dialog.view_history()
        self.assertEqual(len(dialog.history_tabs.tabs()), 3)
        self.app.set_language('en')
        self.assertIn('Removed:', dialog.history_variables[2].get())
        dialog.close_history()
        dialog.restart()
        self.assertIsNone(dialog.session.method)
        self.assertEqual(dialog.session.history, [])
        self.assertEqual(dialog.session.used_section_ranges, set())
        self.assertEqual(dialog.session.working_copy, STORY)
        dialog.window.destroy()

    def test_language_keeps_selection_order_removed_goal_history_and_working_copy(self):
        dialog = self.open_story()
        dialog.start('editorial')
        dialog.down_button.invoke()
        dialog.lock()
        dialog.next_round()
        dialog.down_button.invoke()
        dialog.remove_button.invoke()
        state = dialog.session
        current = state.current_round
        selected = dialog.fragments.selection()
        removed_selected = dialog.removed_fragments.selection()
        snapshot = (list(current.order), list(current.removed), current.goal, state.working_copy,
                    list(state.history), set(state.used_section_ranges), state.outcome)
        for language in ('en', 'zh', 'en'):
            self.app.set_language(language)
            self.assertIs(dialog.session, state)
            self.assertEqual(dialog.fragments.selection(), selected)
            self.assertEqual(dialog.removed_fragments.selection(), removed_selected)
            self.assertEqual((list(current.order), list(current.removed), current.goal, state.working_copy,
                              list(state.history), set(state.used_section_ranges), state.outcome), snapshot)
            self.assertEqual(state.method, 'editorial')
            self.assertEqual(current.number, 2)
        self.assertEqual(dialog.fragments.heading('#0', 'text'), 'Fragments')
        self.assertEqual(dialog.restore_button.cget('text'), 'Restore')
        dialog.lock()
        dialog.next_round()
        dialog.lock()
        scores = dialog.session.outcome
        self.app.set_language('zh')
        self.app.set_language('en')
        self.assertEqual(dialog.session.outcome, scores)
        self.assertNotRegex(dialog.stats.get(), '[\u4e00-\u9fff]')
        dialog.window.destroy()

    def test_visible_english_labels_and_no_free_replacement_input(self):
        self.app.set_language('en')
        dialog = self.open_story()
        def inspect(widget):
            self.assertNotIsInstance(widget, tk.Entry)
            if isinstance(widget, tk.Text):
                self.assertEqual(widget.cget('state'), 'disabled')
            if isinstance(widget, (tk.Label, tk.Button)) and not widget.cget('textvariable'):
                if widget.cget('text') != '中文 / EN':
                    self.assertNotRegex(widget.cget('text'), '[\u4e00-\u9fff]')
            for child in widget.winfo_children():
                inspect(child)
        inspect(dialog.window)
        dialog.start('editorial')
        inspect(dialog.window)
        for number in range(3):
            dialog.lock()
            if number < 2:
                dialog.next_round()
        inspect(dialog.window)
        dialog.window.destroy()

    def test_snapshot_of_unsaved_editor_is_not_written_by_game(self):
        before = self.app.store.get(self.article.id).to_dict()
        self.app.editor.insert('end', ' ' + STORY)
        self.root.update()
        if self.app.save_job:
            self.root.after_cancel(self.app.save_job)
            self.app.save_job = None
        editor = self.app.editor.get('1.0', 'end-1c')
        dialog = self.app.open_reframe()
        self.assertEqual(dialog.source, editor)
        dialog.start('pure')
        dialog.down_button.invoke()
        dialog.lock()
        dialog.window.destroy()
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), editor)
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)

    def test_missing_article_busy_and_no_suitable_sections(self):
        self.app.busy = True
        with patch('clipdesk.ui.messagebox.showinfo'):
            self.assertIsNone(self.app.open_reframe())
        self.app.busy = False
        self.app.current = None
        with patch('clipdesk.ui.messagebox.showinfo'):
            self.assertIsNone(self.app.open_reframe())
        self.app.show_article(self.article)
        self.app.editor.delete('1.0', 'end')
        dialog = self.app.open_reframe()
        self.assertEqual(dialog.session.sections, ())
        self.assertIsNone(dialog.session.current_round)
        dialog.window.destroy()

    def test_round_actions_remain_visible_at_minimum_window_size(self):
        self.root.deiconify()
        for method in ('pure', 'editorial'):
            dialog = self.open_story()
            dialog.start(method)
            dialog.window.geometry('820x580')
            for language in ('zh', 'en'):
                self.app.set_language(language)
                self.root.update()
                bottom = dialog.window.winfo_rooty() + dialog.window.winfo_height()
                for control in (dialog.up_button, dialog.down_button, dialog.remove_button,
                                dialog.restore_button, dialog.lock_button, dialog.next_button):
                    self.assertTrue(control.winfo_ismapped())
                    self.assertGreater(control.winfo_height(), 20)
                    self.assertLessEqual(control.winfo_rooty() + control.winfo_height(), bottom)
                self.assertGreater(dialog.fragments.winfo_height(), 60)
            dialog.window.destroy()

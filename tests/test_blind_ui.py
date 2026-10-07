import copy
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import test_features
from test_blind import STORY, ANSWERS


def wait_reveal(dialog):
    done = tk.BooleanVar(master=dialog.window, value=False)
    dialog.window.after(520, lambda: done.set(True))
    dialog.window.wait_variable(done)


def open_growth(app):
    """Enter old growth regressions through the actual new UI with identity inputs."""
    dialog = app.open_twisted()
    for slot in dialog.session.blind_slots:
        dialog.blind_inputs[slot.id].set(slot.original)
    dialog.blind_regrow_button.invoke()
    wait_reveal(dialog)
    dialog.continue_button.invoke()
    return dialog


class BlindUITests(unittest.TestCase):
    setUp = test_features.FeatureUITests.setUp
    tearDown = test_features.FeatureUITests.tearDown

    def open_story(self):
        self.article.body = STORY
        self.app.store.save(self.article)
        self.app.show_article(self.article)
        self.root.update()
        return self.app.open_twisted()

    def fill(self, dialog):
        for slot in dialog.session.blind_slots:
            dialog.blind_inputs[slot.id].set(ANSWERS[slot.category])

    def widgets(self, parent):
        yield parent
        for child in parent.winfo_children():
            yield from self.widgets(child)

    def test_blind_has_no_story_preview_targets_history_or_scores(self):
        d = self.open_story()
        self.assertEqual(len(d.blind_inputs), 5)
        self.assertEqual(d.session.phase, 'blind')
        self.assertFalse(any(isinstance(w, tk.Text) for w in self.widgets(d.window)))
        labels = '\n'.join(str(w.cget('text')) for w in self.widgets(d.window) if isinstance(w, (tk.Label, tk.Button)))
        for slot in d.session.blind_slots:
            self.assertNotIn(slot.original, labels)
        for text in ('原始故事', '查看历史', '扭曲度', '可读性'):
            self.assertNotIn(text, labels)
        self.assertEqual(d.blind_regrow_button.cget('state'), 'disabled')
        self.assertIsNotNone(d.editor_cover)
        d.view_history()
        self.assertFalse(hasattr(d, 'history_window'))
        d.window.destroy()
        self.assertIsNone(d.editor_cover)
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), STORY)

    def test_real_delay_reveal_both_stories_highlights_and_database_isolation(self):
        d = self.open_story()
        before = self.app.store.get(self.article.id).to_dict()
        changes_before = self.app.store.db.total_changes
        self.fill(d)
        self.assertEqual(d.blind_regrow_button.cget('state'), 'normal')
        start = time.monotonic()
        d.blind_regrow_button.invoke()
        self.root.update()
        self.assertEqual(d.session.phase, 'blind')
        self.assertFalse(any(isinstance(w, tk.Text) for w in self.widgets(d.window)))
        wait_reveal(d)
        self.assertGreaterEqual(time.monotonic() - start, .3)
        self.assertEqual(d.session.phase, 'reveal')
        self.assertEqual(d.original_box.get('1.0', 'end-1c'), STORY)
        self.assertEqual(d.reveal_box.get('1.0', 'end-1c'), d.session.current_generation)
        self.assertEqual(len(d.reveal_box.tag_ranges('seed')), 10)
        self.assertIsNone(d.editor_cover)
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)
        self.assertEqual(self.app.store.db.total_changes, changes_before)
        self.assertEqual(self.article.body, STORY)
        self.assertEqual(d.session.generation, 0)
        d.window.destroy()

    def test_language_preserves_slots_locations_inputs_suggestions_and_reveal(self):
        d = self.open_story()
        self.app.set_language('en')
        for key in d.blind_inputs:
            d.wild_buttons[key].invoke()
        session = d.session
        slots, values = session.blind_slots, dict(session.blind_inputs)
        used = set(session.wild.used_wild_suggestions)
        for lang in ('zh', 'en', 'zh'):
            self.app.set_language(lang)
            self.assertIs(d.session, session)
            self.assertEqual(d.session.blind_slots, slots)
            self.assertEqual({k: v.get() for k, v in d.blind_inputs.items()}, values)
            self.assertEqual(session.wild.used_wild_suggestions, used)
        d.blind_regrow_button.invoke()
        self.app.set_language('en')  # Also while the reveal callback is pending.
        wait_reveal(d)
        before = (session.current_generation, copy.deepcopy(session.lineage), session.seed_record)
        self.app.set_language('zh')
        self.assertEqual(before, (session.current_generation, session.lineage, session.seed_record))
        self.assertEqual(d.continue_button.cget('text'), '继续生长')
        d.window.destroy()

    def test_wild_button_language_and_no_repeat(self):
        d = self.open_story()
        key = next(iter(d.blind_inputs))
        values = []
        for _ in range(4):
            d.wild_buttons[key].invoke()
            values.append(d.blind_inputs[key].get())
        self.assertEqual(len(set(values)), 4)
        self.assertTrue(all(not v.isascii() for v in values))
        self.app.set_language('en')
        d.wild_buttons[key].invoke()
        self.assertTrue(d.blind_inputs[key].get().isascii())
        d.window.destroy()

    def test_empty_input_blocks_reveal_and_error_is_translated(self):
        self.app.set_language('en')
        d = self.open_story()
        self.fill(d)
        next(iter(d.blind_inputs.values())).set('  ')
        self.assertEqual(d.blind_regrow_button.cget('state'), 'disabled')
        with patch('clipdesk.twisted_ui.messagebox.showerror') as error:
            d.regrow_seed()
        self.assertNotRegex(' '.join(error.call_args.args), '[\u4e00-\u9fff]')
        self.assertEqual(d.session.phase, 'blind')
        d.window.destroy()

    def test_reveal_can_enter_generation_one_or_restore_immediately(self):
        for restoring in (False, True):
            d = self.open_story()
            self.fill(d)
            d.blind_regrow_button.invoke()
            wait_reveal(d)
            (d.seed_back_button if restoring else d.continue_button).invoke()
            self.assertEqual(d.session.generation, 0)
            self.assertEqual(d.session.phase, 'growth')
            if restoring:
                self.assertEqual(d.session.action, 'restore')
                next(iter(d.restore_vars.values())).set(True)
                d.regrow_button.invoke()
                self.assertEqual(d.session.words_restored, 1)
            else:
                d.choose_direction('technology')
                d.inputs[d.session.targets[0]].set('robot')
                d.regrow_button.invoke()
            self.assertEqual(d.session.generation, 1)
            d.window.destroy()

    def test_three_rounds_history_seed_growth_feedback_not_awarded_twice(self):
        d = self.open_story()
        self.fill(d)
        d.blind_regrow_button.invoke()
        wait_reveal(d)
        d.continue_button.invoke()
        for index in range(3):
            d.choose_direction('technology' if index == 0 else 'surreal')
            d.regrow_button.invoke()
            if index < 2:
                d.next_button.invoke()
        self.assertTrue(d.session.finished)
        self.assertEqual(self.app.stories_regrown, 1)
        d.show_result()
        self.app.set_language('en')
        self.assertEqual(self.app.stories_regrown, 1)
        self.assertIn('Growth +1', d.growth_feedback.get())
        d.view_history()
        self.assertEqual(len(d.history_tabs.tabs()), 5)
        self.assertIn('Seed Mutation', d.history_tabs.tab(1, 'text'))
        self.assertIn('three suspicious ducks', d.history_details[1].get().lower())
        self.app.set_language('zh')
        self.assertIn('种子变异', d.history_tabs.tab(1, 'text'))
        d.close_history()
        d.new_mutation()
        self.assertEqual(d.session.phase, 'blind')
        self.assertTrue(all(not v.get() for v in d.blind_inputs.values()))
        self.assertEqual(self.app.stories_regrown, 1)
        d.window.destroy()

    def test_close_during_growing_cancels_callback_and_releases_cover(self):
        d = self.open_story()
        self.fill(d)
        d.blind_regrow_button.invoke()
        d.window.destroy()
        self.assertIsNone(d.reveal_job)
        self.assertIsNone(d.editor_cover)
        done = tk.BooleanVar(value=False)
        self.root.after(520, lambda: done.set(True))
        self.root.wait_variable(done)
        self.assertEqual(self.errors, [])

    def test_short_seed_safe_and_no_skip_button(self):
        self.app.editor.delete('1.0', 'end')
        self.app.editor.insert('1.0', 'the and')
        d = self.app.open_twisted()
        self.assertEqual(d.blind_inputs, {})
        self.assertEqual(d.blind_regrow_button.cget('state'), 'disabled')
        d.window.destroy()

    def test_minimum_window_keeps_primary_actions_visible(self):
        self.root.deiconify()
        d = self.open_story()
        d.window.geometry('820x580')
        for language in ('en', 'zh'):
            self.app.set_language(language)
            self.root.update()
            for button in [d.blind_regrow_button, *d.wild_buttons.values()]:
                self.assertTrue(button.winfo_viewable())
                self.assertLess(button.winfo_rooty() + button.winfo_height(), d.window.winfo_rooty() + d.window.winfo_height())
        self.fill(d)
        d.blind_regrow_button.invoke()
        wait_reveal(d)
        self.root.update()
        self.assertTrue(d.continue_button.winfo_viewable())
        d.window.destroy()

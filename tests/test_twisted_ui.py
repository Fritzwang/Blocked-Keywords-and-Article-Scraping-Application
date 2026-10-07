import json
from pathlib import Path
import re
import tkinter as tk
import unittest
from unittest.mock import patch

import test_features
from test_blind_ui import open_growth
from clipdesk.i18n import STRINGS


class TwistedUITests(unittest.TestCase):
    setUp = test_features.FeatureUITests.setUp
    tearDown = test_features.FeatureUITests.tearDown

    def test_three_rounds_suggestions_history_restart_and_isolation(self):
        before = self.app.store.get(self.article.id).to_dict()
        dialog = open_growth(self.app)
        self.root.update()
        self.assertEqual(dialog.session.generation, 0)
        self.assertEqual(len(dialog.inputs), 3)
        dialog.choose_direction('technology')
        dialog.inputs['forest'].set('machine')
        dialog.regrow()
        self.assertIn('Machine river machine', dialog.session.current_generation)
        self.assertEqual(dialog.next_button.cget('state'), 'normal')
        dialog.next_generation()
        dialog.choose_direction('surreal')
        target = dialog.session.targets[0]
        choice = dialog.session.suggestions[target][0]
        dialog.inputs[target].set(choice)
        dialog.regrow()
        dialog.next_generation()
        dialog.choose_direction('nature')
        dialog.regrow()
        self.assertTrue(dialog.session.finished)
        self.assertEqual(dialog.original_box.get('1.0', 'end-1c'), self.article.body)
        self.assertEqual(dialog.final_box.get('1.0', 'end-1c'), dialog.session.current_generation)
        self.assertIn('代数：3', dialog.stats.get())
        self.assertEqual(len(dialog.session.generation_history), 4)
        dialog.view_history()
        self.assertEqual(len(dialog.history_tabs.tabs()), 5)
        dialog.close_history()
        dialog.new_mutation()
        self.assertEqual(dialog.session.generation, 0)
        self.assertEqual(dialog.session.generation_history, [self.article.body])
        self.assertEqual(dialog.session.words_mutated, 0)
        self.assertTrue(all(not value.get() for value in dialog.blind_inputs.values()))
        dialog.window.destroy()
        self.assertEqual(self.app.store.get(self.article.id).to_dict(), before)
        self.assertEqual(self.app.editor.get('1.0', 'end-1c'), self.article.body)

    def test_language_does_not_reset_targets_choices_inputs_or_scores(self):
        dialog = open_growth(self.app)
        dialog.choose_direction('technology')
        dialog.inputs['forest'].set('machine')
        session = dialog.session
        targets, choices = session.targets, dict(session.suggestions)
        used_targets, used_choices = set(session.used_target_words), set(session.used_suggestions)
        for language in ('en', 'zh', 'en'):
            self.app.set_language(language)
            self.assertIs(dialog.session, session)
            self.assertEqual(session.targets, targets)
            self.assertEqual(session.suggestions, choices)
            self.assertEqual(session.used_target_words, used_targets)
            self.assertEqual(session.used_suggestions, used_choices)
            self.assertEqual(session.direction, 'technology')
            self.assertEqual(dialog.inputs['forest'].get(), 'machine')
        for index in range(3):
            dialog.regrow()
            if index < 2:
                dialog.next_generation()
                dialog.choose_direction('surreal')
        history, scores = list(session.generation_history), session.scores
        records, outcome = list(session.generation_records), session.outcome
        lineage = [(item.original_word, item.current_word, list(item.history)) for item in session.lineage]
        self.app.set_language('zh')
        self.assertIn('扭曲度：', dialog.stats.get())
        self.assertNotIn('Coherence', dialog.stats.get())
        self.app.set_language('en')
        self.assertIn('Distortion:', dialog.stats.get())
        self.assertNotRegex(dialog.stats.get(), '[\u4e00-\u9fff]')
        self.assertEqual(session.generation_history, history)
        self.assertEqual(session.scores, scores)
        self.assertEqual(session.generation_records, records)
        self.assertEqual(session.outcome, outcome)
        self.assertEqual([(item.original_word, item.current_word, list(item.history)) for item in session.lineage], lineage)
        dialog.window.destroy()

    def test_restore_action_can_switch_back_without_losing_inputs_or_checks(self):
        dialog = open_growth(self.app)
        dialog.choose_direction('technology')
        dialog.inputs['forest'].set('machine')
        dialog.regrow()
        dialog.next_generation()
        dialog.choose_direction('surreal')
        dialog.inputs['machine'].set('dragon')
        dialog.begin_restore()
        for key, value in dialog.restore_vars.items():
            if key[:2] == ('forest', 'machine'):
                value.set(True)
        self.assertEqual(dialog.session.direction, 'surreal')
        self.assertEqual(tuple(dialog.direction_combo.cget('values')), ('自然', '科技', '超现实'))
        dialog.choose_direction('nature')
        self.assertEqual(dialog.inputs['machine'].get(), 'dragon')
        dialog.begin_restore()
        self.assertTrue(all(value.get() for key, value in dialog.restore_vars.items() if key[:2] == ('forest', 'machine')))
        dialog.regrow()
        dialog.next_generation()
        dialog.choose_direction('technology')
        dialog.regrow()
        dialog.view_history()
        self.assertIn('Machine → Forest', dialog.history_details[3].get())
        self.app.set_language('en')
        self.assertIn('Restores applied: Machine → Forest', dialog.history_details[3].get())
        dialog.close_history()
        dialog.window.destroy()

    def test_invalid_input_stays_in_same_round_and_is_translated(self):
        self.app.set_language('en')
        dialog = open_growth(self.app)
        dialog.choose_direction('technology')
        dialog.inputs['forest'].set('!!!')
        with patch('clipdesk.twisted_ui.messagebox.showerror') as error:
            dialog.regrow()
        self.assertEqual(dialog.session.generation, 0)
        self.assertEqual(dialog.inputs['forest'].get(), '!!!')
        self.assertNotRegex(' '.join(error.call_args.args), '[\u4e00-\u9fff]')
        dialog.window.destroy()

    def test_regrowth_language_keeps_inputs_results_and_fixed_mask(self):
        dialog = self.app.open_challenge()
        dialog.answers[0].set('forest')
        dialog.answers[1].set('wrong')
        dialog.test()
        session = dialog.challenge
        for language in ('en', 'zh'):
            self.app.set_language(language)
            self.assertIs(dialog.challenge, session)
            self.assertEqual(dialog.answers[1].get(), 'wrong')
            self.assertEqual(dialog.challenge.results, ['correct', 'incorrect', 'unanswered'])
            self.assertEqual(dialog.text.get('1.0', 'end-1c'), 'Forest ***** forest *****.')
            self.assertEqual(dialog.text.tag_names(), ('sel',))
        dialog.window.destroy()

    def test_visible_chrome_english_no_missing_translations(self):
        self.app.set_language('en')
        dialog = open_growth(self.app)
        def inspect(widget):
            if isinstance(widget, (tk.Label, tk.Button)) and not widget.cget('textvariable'):
                text = str(widget.cget('text'))
                if text != '中文 / EN':
                    self.assertNotRegex(text, '[\u4e00-\u9fff]')
            for child in widget.winfo_children():
                inspect(child)
        inspect(self.root)
        for index in range(3):
            dialog.choose_direction('nature')
            dialog.regrow()
            if index < 2:
                dialog.next_generation()
        inspect(self.root)
        for key in ('模式 3 · 扭曲再生', '随机候选', '原始文本', '最终变异', '再生评分：{value}%'):
            self.assertIn(key, STRINGS['zh'])
            self.assertNotRegex(STRINGS['en'][key], '[\u4e00-\u9fff]')
        dialog.window.destroy()

    def test_export_txt_markdown_json_and_autosave(self):
        self.app.title_var.set('Edited Title')
        self.app.editor.insert('end', ' preserved')
        self.app.autosave()
        self.assertTrue(self.app.store.get(self.article.id).body.endswith(' preserved'))
        for extension in ('txt', 'md', 'json'):
            path = Path(self.temp.name) / ('export.' + extension)
            with patch('clipdesk.ui.filedialog.asksaveasfilename', return_value=str(path)):
                self.app.export_article()
            text = path.read_text(encoding='utf-8-sig')
            if extension == 'json':
                self.assertEqual(json.loads(text)['body'], self.app.current.body)
            else:
                self.assertIn('Edited Title', text)
                self.assertIn(self.app.current.body, text)

    def test_restore_selection_survives_language_and_preserves_other_mutations(self):
        dialog = open_growth(self.app)
        self.assertIsNone(dialog.session.direction)
        self.assertEqual(dialog.regrow_button.cget('state'), 'disabled')
        dialog.choose_direction('technology')
        dialog.inputs['forest'].set('machine')
        dialog.inputs['river'].set('network')
        dialog.regrow()
        dialog.next_generation()
        dialog.choose_direction('surreal')
        dialog.inputs['machine'].set('robot')
        dialog.regrow()
        dialog.next_generation()
        dialog.begin_restore()
        for key, value in dialog.restore_vars.items():
            if key[:2] == ('forest', 'robot'):
                value.set(True)
        state = dialog.session
        for language in ('en', 'zh', 'en'):
            self.app.set_language(language)
            self.assertIs(dialog.session, state)
            self.assertIsNone(state.direction)
            self.assertEqual(state.action, 'restore')
            self.assertTrue(all(value.get() for key, value in dialog.restore_vars.items() if key[:2] == ('forest', 'robot')))
            self.assertTrue(all(not value.get() for key, value in dialog.restore_vars.items() if key[:2] == ('river', 'network')))
        dialog.regrow()
        self.assertEqual(state.current_generation, 'Forest network forest city.')
        self.assertEqual(state.words_restored, 2)
        self.assertIn('Final Outcome:', dialog.stats.get())
        self.assertIn('Generation 1: Technology', dialog.stats.get())
        self.assertIn('Generation 2: Surreal', dialog.stats.get())
        self.assertIn('Generation 3: Regrow Back', dialog.stats.get())
        self.assertNotRegex(dialog.stats.get(), '[\u4e00-\u9fff]')
        self.app.set_language('zh')
        self.assertIn('最终形态：', dialog.stats.get())
        self.assertNotIn('Growth Path', dialog.stats.get())
        dialog.window.destroy()

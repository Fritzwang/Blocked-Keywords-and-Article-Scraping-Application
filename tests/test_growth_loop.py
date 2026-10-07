"""Gameplay diversity, detailed history and independent restoration regressions."""
import random
import unittest
from unittest.mock import patch

from clipdesk.i18n import STRINGS
from clipdesk.twisted import TwistedSession, DIRECTIONS
from clipdesk.wordbank import DIRECTION_BANKS

STORY = 'forest river city fire garden ocean mountain flower engine island bird castle dream robot'


class GrowthLoopTests(unittest.TestCase):
    def test_four_targets_use_all_fresh_words_before_repeats(self):
        for seed in range(30):
            session = TwistedSession(STORY, random.Random(seed))
            for generation in range(3):
                self.assertEqual(len(session.targets), 4)
                self.assertEqual(set(session.targets) & {'the', 'and', 'after'}, set())
                self.assertEqual(session.used_target_words, set().union(*map(set, session.target_history)))
                if generation:
                    self.assertFalse(set(session.targets) & set(session.target_history[-2]))
                    self.assertFalse(set(session.targets) & set().union(*map(set, session.target_history[:-1])))
                session.set_direction('nature')
                session.regrow()
                if generation < 2:
                    session.next_generation()

    def test_seven_candidates_guarantee_three_of_four_new_targets(self):
        for seed in range(30):
            session = TwistedSession('forest river city fire garden ocean mountain', random.Random(seed))
            first = set(session.targets)
            session.set_direction('technology')
            session.regrow()
            session.next_generation()
            self.assertEqual(len(set(session.targets) - first), 3)

    def test_new_spellings_are_not_treated_as_fresh_source_positions(self):
        for seed in range(30):
            session = TwistedSession('forest river city fire garden ocean mountain flower', random.Random(seed))
            first_positions = set(session.previous_target_positions)
            session.set_direction('technology')
            session.regrow(dict(zip(session.targets, ('machine', 'network', 'robot', 'sensor'))))
            session.next_generation()
            self.assertFalse(session.previous_target_positions & first_positions)
            self.assertEqual(len(session.used_target_positions), 8)
            self.assertFalse(set(session.targets) & {'machine', 'network', 'robot', 'sensor'})

    def test_short_candidates_repeat_safely_without_manufactured_words(self):
        for text in ('', 'the and to', 'forest', 'forest river city', '森林河流'):
            session = TwistedSession(text, random.Random(8))
            first = session.targets
            for generation in range(3):
                self.assertLessEqual(len(session.targets), 4)
                self.assertEqual(session.targets, first)
                session.set_direction('surreal')
                session.regrow()
                if generation < 2:
                    session.next_generation()
            self.assertEqual(session.current_generation, text)

    def test_three_separate_banks_and_suggestion_history(self):
        for language, target in (('en', 'forest'), ('zh', '森林')):
            session = TwistedSession(target, random.Random(7))
            seen = set()
            for direction in DIRECTIONS:
                session.set_direction(direction)
                choices = session.suggestions[target]
                self.assertEqual(len(choices), 5)
                self.assertTrue(set(choices) <= set(DIRECTION_BANKS[language][direction]))
                self.assertFalse(set(choices) & seen)
                seen.update(choices)
                self.assertTrue(set(choices) <= session.used_suggestions)
                self.assertIn(frozenset(choices), session.suggestion_history)

    def test_unused_suggestions_first_then_different_sets_after_exhaustion(self):
        session = TwistedSession('forest', random.Random(2))
        session.set_direction('technology')
        offered = set(session.suggestions['forest'])
        for _ in range(3):
            choices = session.refresh_suggestions('forest')
            self.assertFalse(set(choices) & offered)
            offered.update(choices)
        self.assertEqual(offered, set(DIRECTION_BANKS['en']['technology']))
        for _ in range(6):
            choices = session.refresh_suggestions('forest')
            self.assertEqual(len(choices), 5)
            self.assertNotIn(frozenset(choices), session.suggestion_history[:-1])

    def test_small_bank_can_reuse_without_empty_suggestions(self):
        with patch.dict(DIRECTION_BANKS['en'], {'technology': ('robot',)}):
            session = TwistedSession('forest')
            session.set_direction('technology')
            self.assertEqual(session.refresh_suggestions('forest'), ('robot',))
            self.assertEqual(session.used_suggestions, {'robot'})

    def test_restore_is_independent_and_preserves_direction(self):
        session = TwistedSession('forest river')
        for invalid in ('human', 'restore'):
            with self.assertRaises(ValueError):
                session.set_direction(invalid)
        session.set_direction('technology')
        session.regrow({'forest': 'machine', 'river': 'sensor'})
        session.next_generation()
        session.set_direction('surreal')
        suggestions = dict(session.suggestions)
        session.begin_restore()
        self.assertEqual(session.direction, 'surreal')
        self.assertEqual(session.suggestions, suggestions)
        session.regrow(restore=[('forest', 'machine')])
        self.assertEqual(session.current_generation, 'forest sensor')
        self.assertEqual(session.words_restored, 1)
        session.next_generation()
        session.set_direction('nature')
        session.regrow({'sensor': 'flower'})
        self.assertEqual(session.current_generation, 'forest flower')
        self.assertEqual([r.direction for r in session.generation_records], ['technology', 'restore', 'nature'])

    def test_history_records_actual_occurrences_including_origin_and_restores(self):
        session = TwistedSession('Forest river forest')
        session.set_direction('technology')
        session.regrow({'forest': 'machine', 'river': ''})
        first = session.generation_records[0]
        self.assertEqual(first.mutated, 2)
        self.assertEqual([(c.original, c.before, c.after) for c in first.mutations_applied],
                         [('Forest', 'Forest', 'Machine'), ('forest', 'forest', 'machine')])
        self.assertNotEqual(first.mutations_applied[0].start, first.mutations_applied[1].start)
        session.next_generation()
        session.set_direction('surreal')
        session.regrow({'machine': 'robot'})
        session.next_generation()
        session.begin_restore()
        session.regrow(restore=[('forest', 'robot')])
        third = session.generation_records[2]
        self.assertEqual(third.mutations_applied, ())
        self.assertEqual([(c.before, c.after) for c in third.restores_applied], [('Robot', 'Forest'), ('robot', 'forest')])
        self.assertEqual(session.words_restored, 2)
        self.assertEqual(len(session.lineage[0].history), 3)
        self.assertEqual(session.lineage[0].generation, 3)

    def test_custom_word_and_sentence_validation_remain_atomic(self):
        session = TwistedSession('forest river')
        session.set_direction('technology')
        with self.assertRaises(ValueError):
            session.regrow({'forest': 'spaceship', 'river': 'two words'})
        self.assertEqual(session.current_generation, session.original_text)
        session.regrow({'forest': 'spaceship'})
        self.assertEqual(session.current_generation, 'spaceship river')

    def test_all_required_game_labels_are_bilingual(self):
        for key in ('生长方向', '自然', '科技', '超现实', '自定义替换', '随机候选', '再生回来',
                    '选择要恢复的词', '再生', '下一代', '生长路径', '原始故事', '最终故事',
                    '修改词数', '恢复词数', '最终形态', '恢复', '重定向生长', '野性生长',
                    '碎片化生长', '选择这一代的生长方向'):
            self.assertIn(key, STRINGS['zh'])
            self.assertNotEqual(STRINGS['zh'][key], STRINGS['en'][key])

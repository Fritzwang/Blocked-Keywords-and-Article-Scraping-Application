import copy
import random
import unittest
from unittest.mock import patch

from clipdesk.blind import (CATEGORIES, WILD_PHRASES, WildSuggestions,
                            select_funny_slots, FunnySlot, clean_answer)
from clipdesk.models import Article
from clipdesk.twisted import TwistedSession

STORY = ('The Prime Minister met business leaders in Sydney. '
         'A penguin carried a telescope through the ancient garden. '
         'Scientists launched a rocket while residents watched the mysterious sky.')
ANSWERS = dict(zip(CATEGORIES, ('three suspicious ducks', 'an angry penguin', 'arguing with pigeons',
                               'on the Moon', 'a haunted microwave', 'an unpaid wizard', 'suspiciously sparkly')))


def fill_seed(session):
    return session.reveal_seed({slot.id: ANSWERS[slot.category] for slot in session.blind_slots})


class BlindSlotTests(unittest.TestCase):
    def test_normal_english_meaningful_slots(self):
        slots = select_funny_slots(STORY)
        self.assertEqual(len(slots), 5)
        self.assertGreaterEqual(len({s.category for s in slots}), 4)
        self.assertIn('The Prime Minister', [s.original for s in slots])
        self.assertTrue({'animal', 'place'} & {s.category for s in slots})

    def test_stopwords_never_selected_alone(self):
        self.assertEqual(select_funny_slots('the a an of and in is are 的了和在是'), ())
        slots = select_funny_slots('the a an of and in is are ' + STORY)
        self.assertFalse({'the', 'a', 'an', 'of', 'and', 'in', 'is', 'are'} & {s.original.lower() for s in slots})

    def test_categories_original_and_source_offsets(self):
        for slot in select_funny_slots(STORY):
            self.assertIn(slot.category, CATEGORIES)
            self.assertEqual(STORY[slot.start:slot.end], slot.original)
            self.assertGreater(slot.end, slot.start)

    def test_nonoverlap_longest_phrase_and_no_replacement_drift(self):
        slots = select_funny_slots(STORY)
        self.assertTrue(all(a.end <= b.start for a, b in zip(slots, slots[1:])))
        self.assertNotIn('Minister', [s.original for s in slots])
        s = TwistedSession(STORY, blind=True)
        result = fill_seed(s)
        for change in s.seed_record.mutations_applied:
            self.assertEqual(STORY[change.start:change.end], change.original)
            self.assertIn(change.after, result)

    def test_short_empty_and_punctuation_safe(self):
        for text in ('', '!!!', 'the and', 'forest', '的了和在是', '猫'):
            self.assertLessEqual(len(select_funny_slots(text)), 1)
            session = TwistedSession(text, blind=True)
            if not session.blind_slots:
                with self.assertRaises(ValueError):
                    session.reveal_seed({})

    def test_count_clamped_to_four_through_six(self):
        for count in (1, 4, 5, 6, 100):
            self.assertEqual(len(select_funny_slots(STORY, count)), max(4, min(6, count)))

    def test_chinese_slots_and_positions(self):
        text = '市长访问北京，科学家发现神秘的机器。居民保护森林，学生使用图书。'
        slots = select_funny_slots(text)
        self.assertEqual(len(slots), 5)
        self.assertGreaterEqual(len({slot.category for slot in slots}), 4)
        self.assertTrue(all(text[s.start:s.end] == s.original for s in slots))

    def test_technical_article_keeps_determiners_and_excludes_noun_uses_of_verbs(self):
        text = ('Python is an interpreted, object-oriented, high-level programming language with dynamic semantics. '
                'Its high-level built in data structures make it very attractive for use as a scripting or glue language '
                'to connect existing components together. Often, programmers fall in love with Python.')
        slots = select_funny_slots(text)
        self.assertNotIn('built', [s.original for s in slots if s.category == 'action'])
        self.assertNotIn('use', [s.original for s in slots if s.category == 'action'])
        self.assertNotIn('make', [s.original for s in slots if s.category == 'action'])
        self.assertIn('an interpreted, object-oriented, high-level programming language', [s.original for s in slots])


class BlindMutationTests(unittest.TestCase):
    def test_five_answers_seed_generation_zero_and_source_isolation(self):
        article = Article(title='News', body=STORY)
        before = copy.deepcopy(article.to_dict())
        s = TwistedSession(article.body, blind=True)
        fill_seed(s)
        self.assertEqual(article.to_dict(), before)
        self.assertEqual(s.original_text, STORY)
        self.assertEqual(s.generation, 0)
        self.assertEqual(len(s.seed_record.mutations_applied), 5)
        self.assertEqual(s.generation_records, [])
        self.assertEqual(s.phase, 'reveal')

    def test_phrase_readability_articles_prepositions_and_action_frame(self):
        s = TwistedSession('The Prime Minister met business leaders in Sydney. The telescope broke.', blind=True)
        result = fill_seed(s)
        self.assertIn('Three suspicious ducks started arguing with pigeons with an unpaid wizard on the Moon.', result)
        self.assertNotIn('The three', result)
        self.assertNotIn('in on the Moon', result)
        self.assertNotIn('a a haunted', result)

    def test_place_custom_phrase_keeps_source_preposition(self):
        s = TwistedSession('The mayor worked in London. The scientist met students at the school.', blind=True)
        s.reveal_seed({slot.id: 'my university library' if slot.category == 'place' else ANSWERS[slot.category] for slot in s.blind_slots})
        self.assertIn('in my university library', s.current_generation)

    def test_lineage_seed_history_then_partial_restore(self):
        s = TwistedSession(STORY, blind=True)
        fill_seed(s)
        changed = [item for item in s.lineage if item.history]
        self.assertEqual(len(changed), 5)
        self.assertTrue(all(item.history[0][0] == 0 for item in changed))
        key = s.restore_options[0]
        other = changed[1].current_word
        s.continue_seed()
        s.begin_restore()
        s.regrow(restore=[key])
        self.assertIn('The Prime Minister', s.current_generation)
        self.assertIn(other, s.current_generation)
        self.assertEqual(s.words_restored, 1)

    def test_identical_blind_phrases_restore_individual_occurrence(self):
        s = TwistedSession('The minister met the minister in Sydney. The minister visited London.', blind=True)
        s.reveal_seed({slot.id: 'a confused astronaut' for slot in s.blind_slots})
        s.continue_seed()
        key = s.restore_options[0]
        s.begin_restore()
        s.regrow(restore=[key])
        self.assertEqual(s.words_restored, 1)
        self.assertIn('a confused astronaut', s.current_generation.lower())

    def test_empty_missing_invalid_and_extreme_input_are_atomic(self):
        for bad in ('', '   ', 'x' * 101, '!!!', 'hello\nworld'):
            s = TwistedSession(STORY, blind=True)
            answers = {slot.id: ANSWERS[slot.category] for slot in s.blind_slots}
            answers[s.blind_slots[-1].id] = bad
            before = copy.deepcopy(s.lineage)
            with self.assertRaises(ValueError):
                s.reveal_seed(answers)
            self.assertEqual(s.lineage, before)
            self.assertEqual(s.current_generation, STORY)
            self.assertIsNone(s.seed_record)
        with self.assertRaises(ValueError):
            s.reveal_seed({})

    def test_trim_and_custom_names(self):
        self.assertEqual(clean_answer('  Batman  '), 'Batman')
        s = TwistedSession(STORY, blind=True)
        s.reveal_seed({slot.id: '  Batman  ' for slot in s.blind_slots})
        self.assertTrue(all(v == 'Batman' for v in s.blind_inputs.values()))

    def test_cannot_skip_blind_or_commit_seed_twice(self):
        s = TwistedSession(STORY, blind=True)
        for action in (s.continue_seed, s.begin_restore, lambda: s.set_direction('nature')):
            with self.assertRaises(ValueError):
                action()
        fill_seed(s)
        with self.assertRaises(ValueError):
            fill_seed(s)

    def test_three_generations_and_seed_remain_distinct(self):
        s = TwistedSession(STORY, random.Random(11), blind=True)
        fill_seed(s)
        s.continue_seed()
        seed_key = s.restore_options[0]
        for direction in ('technology', 'surreal'):
            s.set_direction(direction)
            s.regrow({s.targets[0]: s.suggestions[s.targets[0]][0]})
            s.next_generation()
        # Source identity is stable even if the target changed again.
        key = next(k for k in s.restore_options if len(k) == 3 and k[2] == seed_key[2])
        s.begin_restore()
        s.regrow(restore=[key])
        self.assertTrue(s.finished)
        self.assertEqual(len(s.generation_history), 4)
        self.assertEqual([r.direction for r in s.generation_records], ['technology', 'surreal', 'restore'])
        self.assertEqual(s.seed_record.number, 0)
        self.assertIn(s.outcome, ('restoration', 'redirected', 'wild', 'fragmented'))

    def test_blind_phrase_can_mutate_again_and_restore_to_source(self):
        s = TwistedSession('The minister visited Sydney.', random.Random(4), blind=True)
        fill_seed(s)
        s.continue_seed()
        person = next(item for item in s.lineage if item.original_word == 'The minister')
        self.assertIn(person.current_word.casefold(), s.targets)
        s.set_direction('technology')
        s.regrow({person.current_word.casefold(): 'robot'})
        s.next_generation()
        s.begin_restore()
        s.regrow(restore=[s.restore_key(person)])
        self.assertEqual(person.current_word, 'The minister')
        self.assertEqual([h[0] for h in person.history], [0, 1, 2])

    def test_bad_future_selector_cannot_corrupt_lineage(self):
        class Overlap:
            def select_funny_slots(self, text):
                return (FunnySlot(0, 8, text[:8], 'person'), FunnySlot(4, 12, text[4:12], 'object'))
        s = TwistedSession(STORY, blind=True, slot_selector=Overlap())
        with self.assertRaises(ValueError):
            s.reveal_seed({slot.id: 'ducks' for slot in s.blind_slots})
        self.assertEqual(s.current_generation, STORY)


class WildTests(unittest.TestCase):
    def test_every_category_nonempty_phrase_pools_in_both_languages(self):
        for language in ('en', 'zh'):
            self.assertEqual(set(WILD_PHRASES[language]), set(CATEGORIES))
            for values in WILD_PHRASES[language].values():
                self.assertGreaterEqual(len(values), 6)
                self.assertTrue(all(clean_answer(v) for v in values))

    def test_no_repeats_before_exhaustion_then_no_immediate_repeat(self):
        bank = WildSuggestions(random.Random(5))
        for language in ('en', 'zh'):
            for category in CATEGORIES:
                pool = WILD_PHRASES[language][category]
                choices = [bank.suggest(category, language) for _ in pool]
                self.assertEqual(len(set(choices)), len(pool))
                for _ in range(20):
                    choice = bank.suggest(category, language)
                    self.assertIn(choice, pool)
                    self.assertNotEqual(choice, choices[-1])
                    choices.append(choice)

    def test_language_uses_ui_language_without_resetting_session(self):
        s = TwistedSession(STORY, blind=True)
        slot = s.blind_slots[0]
        english = s.wild_suggestion(slot.id, 'en')
        chinese = s.wild_suggestion(slot.id, 'zh')
        self.assertTrue(english.isascii())
        self.assertRegex(chinese, '[\u4e00-\u9fff]')
        self.assertEqual(len(s.wild.used_wild_suggestions), 2)

    def test_all_blind_gameplay_runs_with_network_disabled(self):
        with patch('socket.socket', side_effect=AssertionError('Network used')):
            s = TwistedSession(STORY, blind=True)
            answers = {slot.id: s.wild_suggestion(slot.id, 'en') for slot in s.blind_slots}
            s.reveal_seed(answers)
            s.continue_seed()
            for i in range(3):
                s.set_direction('nature')
                s.regrow()
                if i < 2:
                    s.next_generation()
            self.assertTrue(s.finished)

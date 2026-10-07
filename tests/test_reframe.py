from collections import Counter
import random
import unittest

from clipdesk.models import Article
from clipdesk.reframe import ReframeSession, select_sections, split_fragments, GOALS, WORDS

STORY = (
    'The city council approved the new project after several months of public debate despite strong local opposition and concerns about the woodland.\n\n'
    'Residents welcomed the new gardens because children needed a safe place to play while volunteers planted flowers and opened paths beside the river.\n\n'
    'The mayor promised to protect the forest after heavy floods damaged nearby roads but local families asked for stronger plans before winter arrived.'
)


class FragmentTests(unittest.TestCase):
    def test_english_phrase_fragments_and_exact_source_reconstruction(self):
        for section in select_sections(STORY):
            pieces = split_fragments(section)
            self.assertGreaterEqual(len(pieces.fragments), 5)
            self.assertLessEqual(len(pieces.fragments), 7)
            self.assertEqual(pieces.render([f.id for f in pieces.fragments]), section.text)
            for fragment in pieces.fragments:
                self.assertGreaterEqual(len(WORDS.findall(fragment.text)), 2)
                self.assertEqual(STORY[fragment.start:fragment.end], fragment.text)
                self.assertEqual(fragment.paragraph, section.paragraph)

    def test_chinese_clauses_keep_source_characters_and_punctuation(self):
        text = '城市议会通过了新的公园计划，居民欢迎更多的绿色空间，但是邻近森林需要继续保护，因此工人调整了建设路线，志愿者种下鲜花并邀请孩子参加活动。'
        sections = select_sections(text)
        self.assertEqual(len(sections), 1)
        pieces = split_fragments(sections[0])
        self.assertTrue(5 <= len(pieces.fragments) <= 7)
        self.assertEqual(pieces.render([f.id for f in pieces.fragments]), text)
        self.assertTrue(all(len(f.text) >= 4 for f in pieces.fragments))

    def test_url_metadata_very_short_and_oversized_sections_are_excluded(self):
        text = 'https://example.com/news\nPublished: 2026-10-01\nHome\nHi.\n' + 'word ' * 150 + '.\n' + STORY
        sections = select_sections(text)
        self.assertEqual(len(sections), 3)
        self.assertTrue(all(len(section.text) <= 420 for section in sections))
        self.assertTrue(all('http' not in section.text for section in sections))
        self.assertTrue(all(text[section.start:section.end] == section.text for section in sections))

    def test_short_and_empty_input_is_safe(self):
        for text in ('', 'the', '你好', '!!!', 'https://example.com'):
            session = ReframeSession(text)
            self.assertEqual(session.working_copy, text)
            with self.assertRaises(ValueError):
                session.start('pure')
            self.assertIsNone(session.method)
        session = ReframeSession('The forest grows.')
        session.start('editorial')
        for round_number in range(3):
            self.assertEqual(session.minimum_kept, 1)
            session.lock()
            if round_number < 2:
                session.next_round()
        self.assertEqual(session.working_copy, 'The forest grows.')


class ReframeTests(unittest.TestCase):
    def session(self, method='pure', text=STORY):
        session = ReframeSession(text, random.Random(4))
        session.start(method)
        return session

    def test_entry_requires_method_and_does_not_start_immediately(self):
        session = ReframeSession(STORY)
        self.assertIsNone(session.current_round)
        self.assertIsNone(session.method)
        with self.assertRaises(ValueError):
            session.start('mode5')
        session.start('pure')
        with self.assertRaises(ValueError):
            session.start('editorial')

    def test_three_distinct_sections_and_local_goals(self):
        for seed in range(15):
            session = ReframeSession(STORY, random.Random(seed))
            session.start('pure')
            for number in range(1, 4):
                self.assertEqual(session.current_round.number, number)
                self.assertIn(session.current_round.goal, GOALS)
                session.lock()
                if number < 3:
                    session.next_round()
            self.assertEqual(len(session.used_section_ranges), 3)
            self.assertEqual(len({r.goal for r in session.history}), 3)
            self.assertEqual(session.sections_reframed, 3)
            self.assertTrue(session.finished)
            self.assertEqual(session.working_copy, STORY)

    def test_pure_reorders_but_never_removes_or_adds_source_characters(self):
        session = self.session()
        for number in range(3):
            current = session.current_round
            first = current.order[0]
            with self.assertRaises(ValueError):
                session.remove(first)
            session.move(first, 1)
            session.move(first, 1)
            expected = session.preview()
            session.lock()
            self.assertEqual(session.history[-1].reframed_section, expected)
            self.assertIn(expected, session.working_copy)
            if number < 2:
                session.next_round()
        self.assertNotEqual(session.working_copy, STORY)
        self.assertEqual(Counter(session.working_copy), Counter(STORY))
        self.assertEqual(session.fragments_removed, 0)
        self.assertEqual(session.fragments_moved, 9)
        self.assertEqual(session.outcome, 'context')

    def test_lock_rejects_duplicates_additions_and_missing_fragments_atomically(self):
        for fault in ('duplicate', 'addition', 'missing'):
            session = self.session()
            current = session.current_round
            if fault == 'duplicate':
                current.order.append(current.order[0])
            elif fault == 'addition':
                current.order.append('made-up-text')
            else:
                current.order.pop()
            with self.assertRaises(ValueError):
                session.lock()
            self.assertEqual(session.history, [])
            self.assertEqual(session.working_copy, STORY)
            self.assertFalse(current.locked)

    def test_pure_cannot_bypass_removal_by_direct_state_edit(self):
        session = self.session()
        current = session.current_round
        current.removed.append(current.order.pop())
        with self.assertRaises(ValueError):
            session.lock()

    def test_editorial_deletion_limits_zero_one_two(self):
        session = self.session('editorial')
        for number, limit in enumerate((0, 1, 2), 1):
            current = session.current_round
            self.assertEqual(session.removal_limit, limit)
            for _ in range(limit):
                session.remove(current.order[-1])
            before = list(current.order)
            with self.assertRaises(ValueError):
                session.remove(current.order[-1])
            self.assertEqual(current.order, before)
            self.assertEqual(len(current.removed), limit)
            session.lock()
            self.assertEqual(len(session.history[-1].removed_fragments), limit)
            if number < 3:
                session.next_round()
        self.assertEqual(session.fragments_removed, 3)
        self.assertTrue(Counter(session.working_copy) <= Counter(STORY))
        self.assertEqual(session.outcome, 'selective')
        # Removing a fragment shifts positions but is not itself a reorder.
        self.assertEqual(session.fragments_moved, 0)

    def test_restore_before_lock_recovers_exact_order_and_budget(self):
        session = self.session('editorial')
        session.lock()
        session.next_round()
        current = session.current_round
        original = list(current.order)
        selected = original[2]
        session.remove(selected)
        self.assertNotIn(selected, current.order)
        session.restore(selected)
        self.assertEqual(current.order, original)
        self.assertEqual(current.removed, [])
        session.remove(original[-1])
        session.lock()
        with self.assertRaises(ValueError):
            session.restore(original[-1])

    def test_minimum_three_kept_and_locked_removals_do_not_reappear_on_reuse(self):
        # Four fragments initially; the only section must be reused three times.
        text = 'The forest council approved new gardens after local residents discussed the project.'
        session = self.session('editorial', text)
        self.assertEqual(len(session.current_round.order), 4)
        session.lock()
        session.next_round()
        removed = session.current_round.order[-1]
        session.remove(removed)
        session.lock()
        session.next_round()
        self.assertNotIn(removed, session.current_round.order)
        self.assertEqual(len(session.current_round.order), 3)
        with self.assertRaisesRegex(ValueError, '至少 3'):
            session.remove(session.current_round.order[-1])
        session.lock()
        self.assertEqual(session.sections_reframed, 1)
        self.assertEqual(session.fragments_removed, 1)

    def test_history_contains_all_source_order_removed_goal_and_text_fields(self):
        session = self.session('editorial')
        for number in range(1, 4):
            current = session.current_round
            original_section = current.original_section
            fragments = current.pieces.fragments
            session.move(current.order[0], 1)
            if number > 1:
                session.remove(current.order[-1])
            order, removed = tuple(current.order), tuple(current.removed)
            preview = session.preview()
            session.lock()
            record = session.history[-1]
            self.assertEqual(record.number, number)
            self.assertEqual(record.original_section, original_section)
            self.assertEqual(record.fragments, fragments)
            self.assertEqual(record.final_order, order)
            self.assertEqual(tuple(f.id for f in record.removed_fragments), removed)
            self.assertEqual(record.goal, current.goal)
            self.assertEqual(record.reframed_section, preview)
            if number < 3:
                session.next_round()

    def test_four_outcomes_from_actual_operations_are_deterministic(self):
        for expected in ('close', 'context', 'selective', 'strong'):
            session = self.session('editorial' if expected in ('selective', 'strong') else 'pure')
            for number in range(1, 4):
                current = session.current_round
                if expected != 'close':
                    first = current.order[0]
                    for _ in range(len(current.order) - 1):
                        session.move(first, 1)
                if expected in ('selective', 'strong') and number > 1:
                    for _ in range((number - 1) if expected == 'strong' else (1 if number == 2 else 0)):
                        session.remove(current.order[0] if expected == 'strong' else current.order[-1])
                session.lock()
                if number < 3:
                    session.next_round()
            self.assertEqual(session.outcome, expected)
            self.assertEqual([session.outcome for _ in range(5)], [expected] * 5)

    def test_round_progression_is_fixed_and_source_article_is_unchanged(self):
        article = Article(title='Story', body=STORY, original_body=STORY)
        before = article.to_dict()
        session = self.session(text=article.body)
        with self.assertRaises(ValueError):
            session.next_round()
        for number in range(3):
            session.move(session.current_round.order[0], 1)
            session.lock()
            with self.assertRaises(ValueError):
                session.lock()
            if number < 2:
                session.next_round()
        with self.assertRaises(ValueError):
            session.next_round()
        self.assertEqual(article.to_dict(), before)

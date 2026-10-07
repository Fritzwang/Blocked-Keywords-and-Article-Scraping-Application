import random
import unittest

from clipdesk.models import Article
from clipdesk.twisted import TwistedSession, Scores, classify_outcome
from clipdesk.wordbank import DIRECTION_BANKS


class RedirectTests(unittest.TestCase):
    def test_player_must_choose_direction_and_banks_differ(self):
        session = TwistedSession('Forest fire city.', random.Random(3))
        self.assertIsNone(session.direction)
        with self.assertRaises(ValueError):
            session.regrow({})
        self.assertEqual(session.generation, 0)
        session.set_direction('nature')
        nature = session.suggestions['forest']
        session.set_direction('technology')
        tech = session.suggestions['forest']
        self.assertNotEqual(nature, tech)
        self.assertTrue(set(nature) <= set(DIRECTION_BANKS['en']['nature']))
        self.assertTrue(set(tech) <= set(DIRECTION_BANKS['en']['technology']))

    def test_lineage_chain_partial_restoration_and_history(self):
        article = Article(title='Test', body='Forest recovered after fire. forest city.')
        before = article.to_dict()
        session = TwistedSession(article.body)
        session.set_direction('technology')
        session.regrow({'forest': 'machine', 'fire': 'wedding'})
        session.next_generation()
        session.set_direction('surreal')
        session.regrow({'machine': 'robot', 'city': 'dragon'})
        session.next_generation()
        session.begin_restore()
        self.assertIn(('forest', 'robot'), session.restore_options)
        session.regrow(restore=[('forest', 'robot')])
        self.assertEqual(session.current_generation, 'Forest recovered after wedding. forest dragon.')
        self.assertEqual(session.words_restored, 2)
        self.assertEqual([record.direction for record in session.generation_records], ['technology', 'surreal', 'restore'])
        self.assertEqual([record.text for record in session.generation_records], session.generation_history[1:])
        forest = session.lineage[0]
        self.assertEqual(forest.original_word, 'Forest')
        self.assertEqual(forest.current_word, 'Forest')
        self.assertEqual([step[2] for step in forest.history], ['Machine', 'Robot', 'Forest'])
        self.assertEqual(article.to_dict(), before)

    def test_collision_restores_only_selected_origin(self):
        session = TwistedSession('forest city machine forest')
        session.set_direction('technology')
        session.regrow({'forest': 'machine', 'city': 'machine'})
        session.next_generation()
        session.begin_restore()
        self.assertEqual(set(session.restore_options), {('forest', 'machine'), ('city', 'machine')})
        session.regrow(restore=[('forest', 'machine')])
        self.assertEqual(session.current_generation, 'forest machine machine forest')
        session.next_generation()
        session.set_direction('technology')
        session.regrow({'machine': 'teacher'})
        self.assertEqual(session.current_generation, 'forest teacher teacher forest')

    def test_restore_does_nothing_without_checking(self):
        session = TwistedSession('forest river')
        session.set_direction('surreal')
        session.regrow({'forest': 'dragon'})
        session.next_generation()
        session.begin_restore()
        session.regrow()
        self.assertEqual(session.current_generation, 'dragon river')
        self.assertEqual(session.words_restored, 0)

    def test_chinese_lineage_and_direction(self):
        session = TwistedSession('森林恢复，森林保护河流。')
        session.set_direction('technology')
        self.assertTrue(set(session.suggestions['森林']) <= set(DIRECTION_BANKS['zh']['technology']))
        session.regrow({'森林': '机器', '河流': '网络'})
        session.next_generation()
        session.begin_restore()
        session.regrow(restore=[('森林', '机器')])
        self.assertEqual(session.current_generation, '森林恢复，森林保护网络。')

    def test_outcome_rules_are_deterministic(self):
        cases = [
            (Scores(15, 90, 13.5), ['technology', 'surreal', 'restore'], 0, 'restoration'),
            (Scores(60, 90, 54), ['technology', 'technology', 'nature'], 0, 'redirected'),
            (Scores(80, 70, 56), ['surreal', 'nature', 'technology'], 0, 'wild'),
            (Scores(95, 20, 19), ['surreal'] * 3, 0, 'fragmented'),
            (Scores(45, 80, 36), ['technology', 'restore', 'restore'], .8, 'restoration'),
        ]
        for score, directions, ratio, expected in cases:
            for _ in range(3):
                self.assertEqual(classify_outcome(score, directions, ratio), expected)

    def test_final_outcome_comes_from_session_and_reset_clears_path(self):
        session = TwistedSession('forest city fire')
        for direction in ('technology', 'surreal', 'restore'):
            session.begin_restore() if direction == 'restore' else session.set_direction(direction)
            session.regrow()
            if not session.finished:
                session.next_generation()
        self.assertEqual(session.outcome, 'restoration')
        fresh = TwistedSession(session.original_text)
        self.assertEqual(fresh.generation_records, [])
        self.assertEqual(fresh.words_restored, 0)
        self.assertIsNone(fresh.direction)

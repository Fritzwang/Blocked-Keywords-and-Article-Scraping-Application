import random
import unittest

from clipdesk.models import Article
from clipdesk.twisted import (TwistedSession, apply_replacements, random_suggestions,
                              text_language, distortion, coherence, score_text)


class TwistedTests(unittest.TestCase):
    def test_three_generations_history_and_source_isolation(self):
        article = Article(title='Story', body='The forest slowly recovered after the fire. Forest!')
        before = article.to_dict()
        session = TwistedSession(article.body, random.Random(3))
        session.set_direction('technology')
        session.regrow({'forest': 'machine', 'recovered': 'celebrated', 'fire': 'wedding'})
        self.assertEqual(session.generation, 1)
        self.assertEqual(session.current_generation, 'The machine slowly celebrated after the wedding. Machine!')
        with self.assertRaises(ValueError):
            session.regrow({})
        session.next_generation()
        self.assertIn('machine', session.targets)
        session.set_direction('surreal')
        session.regrow({'machine': 'dragon'})
        self.assertIn('dragon', session.current_generation)
        session.next_generation()
        session.set_direction('nature')
        session.regrow({'dragon': 'garden'})
        self.assertTrue(session.finished)
        self.assertEqual(len(session.generation_history), 4)
        self.assertEqual(session.generation_history[0], article.body)
        self.assertEqual(session.generation_history[-1], session.current_generation)
        self.assertEqual(session.words_mutated, 8)
        with self.assertRaises(ValueError):
            session.next_generation()
        with self.assertRaises(ValueError):
            session.regrow({})
        self.assertEqual(article.to_dict(), before)

    def test_target_limit_stop_words_and_short_input(self):
        session = TwistedSession('the a an of and is are to forest river city orange purple flowers castles mountains machines engines islands dragons', random.Random(1))
        self.assertEqual(len(session.targets), 4)
        self.assertEqual(len(set(session.targets)), 4)
        self.assertFalse(set(session.targets) & {'the', 'and', 'are'})
        for text in ('', 'the and', '的了和是在', 'forest'):
            short = TwistedSession(text)
            for index in range(3):
                short.set_direction('nature')
                short.regrow({})
                if index < 2:
                    short.next_generation()
            self.assertEqual(short.current_generation, text)

    def test_simultaneous_repeated_whole_words_preserve_order(self):
        text, count = apply_replacements('Art article art artist FOREST forest.', {'art': 'forest', 'forest': 'city'})
        self.assertEqual(text, 'Forest article forest artist CITY city.')
        self.assertEqual(count, 4)

    def test_chinese_and_blank_replacements(self):
        text, count = apply_replacements('森林恢复，森林保护河流。', {'森林': '机器', '河流': ''})
        self.assertEqual(text, '机器恢复，机器保护河流。')
        self.assertEqual(count, 2)

    def test_invalid_replacement_is_atomic(self):
        session = TwistedSession('forest river')
        session.set_direction('technology')
        with self.assertRaises(ValueError):
            session.regrow({'forest': 'machine', 'river': '!!!'})
        self.assertEqual(session.generation, 0)
        self.assertEqual(session.generation_history, ['forest river'])
        with self.assertRaises(ValueError):
            session.regrow({'missing': 'word'})

    def test_suggestions_language_and_application(self):
        self.assertEqual(text_language('森林恢复，河流回到城市。'), 'zh')
        self.assertEqual(text_language('The forest slowly recovered.'), 'en')
        for language, word in [('en', 'forest'), ('zh', '森林')]:
            choices = random_suggestions(word, language, random.Random(0))
            self.assertEqual(len(choices), 10)
            self.assertEqual(len(set(choices)), 10)
            self.assertNotIn(word, choices)
            self.assertTrue(all(value.isascii() == (language == 'en') for value in choices))
            session = TwistedSession(word)
            session.set_direction('nature')
            session.regrow({word: choices[0]})
            self.assertEqual(session.current_generation, choices[0])

    def test_next_round_draws_again_and_new_session_resets(self):
        text = 'forest river city orange purple flowers castles mountains machines engines islands dragons'
        session = TwistedSession(text, random.Random(4))
        before = session.targets
        session.set_direction('nature')
        session.regrow({})
        session.next_generation()
        self.assertNotEqual(set(session.targets), set(before))
        fresh = TwistedSession(session.original_text)
        self.assertEqual(fresh.generation, 0)
        self.assertEqual(fresh.generation_history, [text])
        self.assertEqual(fresh.words_mutated, 0)

    def test_distortion_bounds_identity_and_changes(self):
        original = 'The forest slowly recovered after the fire.'
        changed = 'The machine slowly celebrated after the wedding.'
        self.assertEqual(distortion(original, original), 0)
        self.assertGreater(distortion(original, changed), 0)
        # Replacing one token earns the same distortion regardless of length.
        self.assertEqual(distortion('cat river', 'civilization river'), distortion('cat river', 'dog river'))
        self.assertEqual(distortion('cat!', 'cat...'), 0)
        for final in ('', '!!!', changed, '香蕉森林', 'banana ' * 100):
            score = score_text(original, final)
            for value in (score.distortion, score.coherence, score.regrowth):
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 100)

    def test_coherence_penalizes_garbage_repetition_and_symbols(self):
        readable = 'The machine slowly celebrated after the wedding.'
        quality = coherence(readable)
        self.assertGreater(quality, 75)
        for garbage in ('', '!!! @@ ###', 'aaaa banana banana banana !!!', 'banana ' * 30, 'xqztr bbbbb zzzzz qqqqq'):
            self.assertLess(coherence(garbage), quality / 2)
        self.assertGreater(coherence('森林慢慢恢复，河流回到城市。'), 70)

    def test_score_rewards_both_not_only_distortion(self):
        original = 'Forest river city mountain castle.'
        readable = 'Machine ocean garden island kingdom.'
        good = score_text(original, readable)
        bad = score_text(original, 'aaaa banana banana banana !!!')
        self.assertGreater(good.regrowth, 70)
        self.assertLess(bad.regrowth, 30)
        self.assertEqual(good.regrowth, round(good.distortion * good.coherence / 100, 2))

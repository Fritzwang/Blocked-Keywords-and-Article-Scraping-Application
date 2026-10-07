import random
import unittest

from clipdesk.challenge import Challenge, candidate_words, answer_matches
from clipdesk.models import Article


class ChallengeTests(unittest.TestCase):
    def test_candidates_and_stop_words(self):
        words = candidate_words('The forest and river are in a city. Forest is alive.')
        self.assertEqual(words, ['forest', 'river', 'city', 'alive'])

    def test_at_most_five_unique_casefolded(self):
        game = Challenge.create('Forest forest city river apple orange purple yellow flowers.')
        self.assertEqual(len(game.targets), 5)
        self.assertEqual(len(set(game.targets)), 5)

    def test_short_empty_and_stop_only(self):
        for source in ('', 'a', 'the and is are', '的了和是在', '123 !'):
            game = Challenge.create(source)
            self.assertEqual(game.targets, ())
            self.assertEqual(game.test([]), [])
            game.reveal()
            self.assertEqual(game.render(), source)
        self.assertEqual(Challenge.create('Forest').targets, ('forest',))

    def test_answers_case_spaces_and_typos(self):
        self.assertTrue(answer_matches(' Forest ', 'forest'))
        self.assertTrue(answer_matches(' 森林 ', '森林'))
        self.assertFalse(answer_matches('forrest', 'forest'))
        self.assertFalse(answer_matches('forest.', 'forest'))
        self.assertFalse(answer_matches('', 'forest'))

    def test_whole_word_art(self):
        game = Challenge.create('art article art artist', targets=['art'])
        self.assertEqual(game.render(), '***** article ***** artist')
        self.assertEqual(game.targets, ('art',))

    def test_repeated_case_and_punctuation_regrow_together(self):
        source = 'Forest, forest. FOREST! forestry river.'
        game = Challenge.create(source, targets=['forest', 'river'])
        self.assertEqual(game.render(), '*****, *****. *****! forestry *****.')
        self.assertEqual(game.targets.count('forest'), 1)
        game.test([' Forest ', 'wrong'])
        self.assertEqual(game.results, ['correct', 'incorrect'])
        self.assertEqual(game.render(), 'Forest, forest. FOREST! forestry *****.')
        self.assertEqual(game.source, source)

    def test_results_are_independent(self):
        game = Challenge.create('forest river city', targets=['forest', 'river', 'city'])
        self.assertEqual(game.test(['FOREST', 'cat', ' ']), ['correct', 'incorrect', 'unanswered'])
        self.assertEqual(game.score, 1)

    def test_reveal_is_not_correct_and_never_mutates_article(self):
        article = Article(title='Title', body='Forest river forest city.')
        before = article.to_dict()
        game = Challenge.create(article.body)
        game.test(['Forest', 'wrong', ''])
        results = game.results.copy()
        score = game.score
        game.reveal()
        self.assertEqual(game.render(), article.body)
        self.assertEqual(game.results, results)
        self.assertEqual(game.score, score)
        self.assertEqual(game.test(game.targets), results)
        self.assertEqual(article.to_dict(), before)

    def test_new_challenge_resets_and_avoids_same_set_when_possible(self):
        source = 'forest river city purple orange yellow apple'
        first = Challenge.create(source, rng=random.Random(9))
        first.test(first.targets)
        first.reveal()
        second = Challenge.create(source, previous=first.targets, rng=random.Random(9))
        self.assertNotEqual(set(first.targets), set(second.targets))
        self.assertFalse(second.revealed)
        self.assertEqual(second.results, ['pending'] * 5)
        self.assertEqual(second.score, 0)
        self.assertIn('*****', second.render())

    def test_chinese_repeated_complete_words(self):
        source = '森林慢慢恢复，森林保护河流。森林和河流。'
        game = Challenge.create(source, targets=['森林', '河流'])
        self.assertEqual(game.render(), '*****慢慢恢复，*****保护*****。*****和*****。')
        self.assertEqual(len(game.targets), 2)
        game.test([' 森林 ', ''])
        self.assertEqual(game.render(), '森林慢慢恢复，森林保护*****。森林和*****。')

    def test_longer_chinese_words_are_not_substring_masked(self):
        game = Challenge.create('新闻。新闻报道。新闻。', targets=['新闻'])
        self.assertEqual(game.render(), '*****。新闻报道。*****。')

    def test_mask_length_and_recovery_statistics(self):
        game = Challenge.create('cat forest civilization cat', targets=['cat', 'forest', 'civilization'])
        self.assertEqual(game.render(), '***** ***** ***** *****')
        game.test(['cat', 'wrong', ''])
        self.assertEqual(game.render(), 'cat ***** ***** cat')
        self.assertEqual(game.restoration, 33)
        game.reveal()
        self.assertEqual(game.score, 1)
        self.assertEqual(game.revealed_count, 2)
        self.assertEqual(game.restoration, 100)

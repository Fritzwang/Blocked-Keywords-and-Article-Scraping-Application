from dataclasses import asdict
from pathlib import Path
import json
import random
import sqlite3
import string
import tempfile
import unittest
from unittest.mock import patch

from clipdesk.cipher import CipherGame, CipherRule, Puzzle, RULES

ARTICLE = '  The Forest has a SECRET.\n\nAnother paragraph: River, river! 中文 123.\n'


def undo_substitutions(puzzle):
    inverse = {b: a for a, b in puzzle.substitutions.items()}
    inverse.update({b.lower(): a.lower() for a, b in puzzle.substitutions.items()})
    return puzzle.ciphertext.translate(str.maketrans(inverse))

class CipherTests(unittest.TestCase):
    def setUp(self):
        self.game = CipherGame(source=ARTICLE, rng=random.Random(27))

    def tearDown(self):
        self.game.close()

    def solve(self):
        rule = self.game.state.puzzle.rule
        return self.game.submit(rule.multiplier, rule.addend)

    def test_known_letter_numbering_and_wraparound(self):
        self.assertEqual(CipherRule(1, 1).encrypt('Abc XYZ! 中文123'), 'Bcd YZA! 中文123')
        self.assertEqual(CipherRule(1, 3).encrypt('XYZ'), 'ABC')
        self.assertEqual(CipherRule(2, 1).encrypt('ABMZ'), 'CEAA')
        self.assertEqual(CipherRule(2, 0).encrypt('ANZ'), 'BBZ')

    def test_rule_bounds_and_type_validation(self):
        for values in ((0, 1), (3, 0), (1, -1), (2, 4), (True, 2), (1.0, 1), (2, '1')):
            with self.subTest(values=values), self.assertRaises(ValueError):
                CipherRule(*values)

    def test_random_rules_and_three_reversible_cipher_substitutions(self):
        seen = set()
        seen_substitutions = set()
        previous = None
        for _ in range(100):
            puzzle = self.game.state.puzzle
            pair = (puzzle.rule.multiplier, puzzle.rule.addend)
            self.assertIn(pair, RULES)
            self.assertNotEqual(pair, previous)
            seen.add(pair)
            mapping = puzzle.substitutions
            base = puzzle.rule.encrypt(puzzle.plaintext)
            alphabet = {letter.upper() for letter in base if letter in string.ascii_letters}
            self.assertEqual(len(mapping), 3)
            self.assertEqual(len(set(mapping.values())), 3)
            self.assertTrue(set(mapping) <= alphabet)
            self.assertFalse(set(mapping.values()) & (alphabet - set(mapping)))
            self.assertTrue(all(a != b for a, b in mapping.items()))
            self.assertNotEqual(puzzle.ciphertext, base)
            self.assertEqual(undo_substitutions(puzzle), base)
            seen_substitutions.add(tuple(mapping.items()))
            previous = pair
            self.game.next_puzzle()
            self.assertEqual(self.game.state.puzzle.plaintext, ARTICLE)
        self.assertEqual(seen, set(RULES))
        self.assertGreater(len(seen_substitutions), 80)
        self.game.next_puzzle('Alpha bravo Alpha!')
        self.assertEqual(self.game.state.puzzle.plaintext, 'Alpha bravo Alpha!')

    def test_entire_long_article_is_preserved_without_truncation(self):
        source = ARTICLE * 2500
        self.game.next_puzzle(source)
        puzzle = self.game.state.puzzle
        self.assertEqual(puzzle.plaintext, source)
        self.assertEqual(len(puzzle.ciphertext), len(source))
        self.assertEqual(puzzle.ciphertext.count('\n'), source.count('\n'))
        self.assertIn('中文 123.', puzzle.ciphertext)
        self.assertEqual(undo_substitutions(puzzle)[-len(ARTICLE):], puzzle.rule.encrypt(ARTICLE))

    def test_second_layer_uses_cipher_letters_and_preserves_case(self):
        puzzle = Puzzle(1, 'Aa Bb Uu! 中文123\n', CipherRule(1, 1),
                        {'B': 'U', 'C': 'X', 'V': 'Q'})
        self.assertEqual(puzzle.ciphertext, 'Uu Xx Qq! 中文123\n')
        self.assertEqual(undo_substitutions(puzzle), 'Bb Cc Vv! 中文123\n')

    def test_substitutions_are_simultaneous_not_cascading(self):
        puzzle = Puzzle(1, 'A a T t C c', CipherRule(1, 1), {'B': 'U', 'U': 'D', 'D': 'B'})
        self.assertEqual(puzzle.ciphertext, 'U u D d B b')
        self.assertEqual(undo_substitutions(puzzle), 'B b U u D d')

    def test_dense_and_small_alphabets_always_change_existing_letters(self):
        for source in ('Aaa', 'Abab', string.ascii_letters):
            for _ in range(20):
                self.game.next_puzzle(source)
                puzzle = self.game.state.puzzle
                base = puzzle.rule.encrypt(source)
                count = len({letter.upper() for letter in base})
                self.assertEqual(len(puzzle.substitutions), min(3, count))
                self.assertEqual(undo_substitutions(puzzle), base)
                self.assertNotEqual(puzzle.ciphertext, base)

    def test_empty_or_nonletter_articles_never_fall_back_to_short_words(self):
        before = asdict(self.game.state)
        for source in ('', '  \n ', '纯中文 123 !!!'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.game.next_puzzle(source)
            self.assertEqual(asdict(self.game.state), before)
            with self.assertRaises(ValueError):
                CipherGame(source=source)

    def test_reward_once_wrong_and_invalid_guesses_are_free(self):
        state = self.game.state
        wrong = next(pair for pair in RULES if pair != (state.puzzle.rule.multiplier, state.puzzle.rule.addend))
        self.assertFalse(self.game.submit(*wrong))
        self.assertEqual(self.game.state.coins, 20)
        self.assertEqual(self.game.state.puzzle.attempts, 1)
        with self.assertRaises(ValueError):
            self.game.submit(2, 5)
        self.assertEqual(self.game.state.puzzle.attempts, 1)
        self.assertTrue(self.solve())
        self.assertFalse(self.solve())
        self.assertEqual((self.game.state.coins, self.game.state.wins), (30, 1))
        self.assertEqual(self.game.state.puzzle.attempts, 2)

    def test_full_team_guarantees_both_values_without_guaranteeing_a_complete_rule(self):
        self.game.set_mode('command')
        saw_noise = saw_split = False
        for _ in range(150):
            rule = self.game.state.puzzle.rule
            before = self.game.state.coins
            hints = self.game.act()
            self.assertEqual(len(hints), 5)
            self.assertEqual(self.game.state.coins, before - 5)
            self.assertIn(rule.multiplier, [hint[0] for hint in hints.values()])
            self.assertIn(rule.addend, [hint[1] for hint in hints.values()])
            for hint in hints.values():
                self.assertEqual(len(hint), 2)
                self.assertIn(hint[0], (1, 2))
                self.assertIn(hint[1], range(6))
            saw_noise |= any(hint[1] > 3 for hint in hints.values())
            saw_split |= [rule.multiplier, rule.addend] not in hints.values()
            self.solve()
            self.game.next_puzzle()
        self.assertTrue(saw_noise)
        self.assertTrue(saw_split)

    def test_single_action_only_charges_and_updates_selected_robot(self):
        self.game.set_mode('command')
        self.assertEqual(list(self.game.act(2)), [2])
        self.assertEqual(self.game.state.coins, 19)
        self.assertEqual([bot.actions for bot in self.game.state.robots], [0, 0, 1, 0, 0])
        self.assertTrue(all(bot.hint is None for i, bot in enumerate(self.game.state.robots) if i != 2))

    def test_staff_costs_capacity_partial_team_and_unique_recruits(self):
        self.game.set_mode('command')
        self.game.dismiss(2)
        self.assertEqual(self.game.state.coins, 15)
        self.assertIsNone(self.game.state.robots[2])
        hints = self.game.act()
        self.assertEqual(set(hints), {0, 1, 3, 4})
        self.assertEqual(self.game.state.coins, 11)
        self.game.recruit(2)
        self.assertEqual(self.game.state.coins, 6)
        self.assertEqual(self.game.state.robots[2].number, 6)
        self.assertIsNone(self.game.state.robots[2].hint)
        with self.assertRaises(ValueError):
            self.game.recruit(2)
        self.assertEqual(self.game.state.coins, 6)
        with self.assertRaises(ValueError):
            self.game.dismiss(-1)

    def test_insufficient_funds_are_atomic_and_player_can_recover(self):
        self.game.set_mode('command')
        for _ in range(4):
            self.game.act()
        self.assertEqual(self.game.state.coins, 0)
        before = asdict(self.game.state)
        for action in (self.game.act, lambda: self.game.act(0), lambda: self.game.dismiss(0)):
            with self.assertRaises(ValueError):
                action()
            self.assertEqual(asdict(self.game.state), before)
        self.solve()
        self.assertEqual(self.game.state.coins, 10)
        self.game.next_puzzle()
        self.game.act()
        self.assertEqual(self.game.state.coins, 5)

    def test_full_team_with_only_four_coins_cannot_charge_any_robot(self):
        self.game.set_mode('command')
        for _ in range(16):
            self.game.act(0)
        before = asdict(self.game.state)
        with self.assertRaises(ValueError):
            self.game.act()
        self.assertEqual(asdict(self.game.state), before)
        self.game.act(1)
        self.assertEqual(self.game.state.coins, 3)

    def test_game_phase_and_empty_seat_guards(self):
        with self.assertRaises(ValueError):
            self.game.act()
        self.game.set_mode('command')
        self.game.dismiss(0)
        before = self.game.state.coins
        for action in (lambda: self.game.act(0), lambda: self.game.dismiss(0)):
            with self.assertRaises(ValueError):
                action()
        self.assertEqual(self.game.state.coins, before)
        self.solve()
        with self.assertRaises(ValueError):
            self.game.act(1)

    def test_empty_team_and_free_next_puzzle_clear_hints_keep_wallet(self):
        self.solve()
        self.game.next_puzzle()
        self.game.set_mode('command')
        for i in range(5):
            self.game.dismiss(i)
        with self.assertRaises(ValueError):
            self.game.act()
        self.game.recruit(3)
        self.assertEqual(self.game.state.coins, 0)
        self.solve()
        self.game.next_puzzle()
        self.game.act(3)
        before = self.game.state.coins
        self.game.next_puzzle()
        self.assertEqual(self.game.state.coins, before)
        self.assertIsNone(self.game.state.robots[3].hint)
        self.assertEqual(self.game.state.robots[3].actions, 1)
        self.assertFalse(self.game.state.puzzle.solved)

    def test_failed_save_rolls_back_rewards_staff_and_rng(self):
        self.game.set_mode('command')
        before = asdict(self.game.state)
        rng_before = self.game.rng.getstate()
        with patch.object(self.game, '_save', side_effect=sqlite3.OperationalError('disk full')):
            for action in (self.solve, self.game.act, lambda: self.game.dismiss(0)):
                with self.assertRaises(sqlite3.Error):
                    action()
                self.assertEqual(asdict(self.game.state), before)
                self.assertEqual(self.game.rng.getstate(), rng_before)


class CipherPersistenceTests(unittest.TestCase):
    def test_legacy_clues_migrate_once_without_resetting_progress_or_reward(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cipher.db'
            game = CipherGame(path, source=ARTICLE)
            game.set_mode('command')
            game.act()
            game.dismiss(1)
            rule = game.state.puzzle.rule
            game.submit(rule.multiplier, rule.addend)
            old = asdict(game.state)
            old['puzzle'].pop('substitutions')
            old['puzzle']['clue_letters'] = 'ABC'
            with game.db:
                game.db.execute('UPDATE game SET payload=? WHERE id=1', (json.dumps(old),))
            game.close()
            game = CipherGame(path, source=ARTICLE)
            try:
                self.assertEqual((game.state.coins, game.state.wins), (20, 1))
                self.assertEqual(game.state.puzzle.number, 1)
                self.assertEqual(game.state.puzzle.attempts, 1)
                self.assertTrue(game.state.puzzle.solved)
                self.assertIsNone(game.state.robots[1])
                self.assertEqual(len(game.state.puzzle.substitutions), 3)
                self.assertNotIn('clue_letters', asdict(game.state.puzzle))
                self.assertFalse(game.submit(rule.multiplier, rule.addend))
                migrated = asdict(game.state)
            finally:
                game.close()
            game = CipherGame(path, source=ARTICLE)
            try:
                self.assertEqual(asdict(game.state), migrated)
            finally:
                game.close()

    def test_restart_and_two_instances_cannot_reset_or_double_award(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cipher.db'
            first = CipherGame(path, source=ARTICLE, rng=random.Random(7))
            first.set_mode('command')
            first.act()
            first.dismiss(0)
            expected = asdict(first.state)
            first.close()
            first = CipherGame(path)
            second = CipherGame(path)
            try:
                self.assertEqual(asdict(first.state), expected)
                rule = first.state.puzzle.rule
                self.assertTrue(first.submit(rule.multiplier, rule.addend))
                self.assertFalse(second.submit(rule.multiplier, rule.addend))
                self.assertEqual(second.state.coins, 20)
                self.assertEqual(second.state.wins, 1)
                second.recruit(0)
                first.next_puzzle()
                self.assertEqual(first.state.coins, 15)
                self.assertEqual(first.state.robots[0].number, 6)
            finally:
                first.close()
                second.close()

    def test_import_current_article_replaces_old_short_puzzle_without_losing_economy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cipher.db'
            game = CipherGame(path, source='OLD WORDS')
            game.set_mode('command')
            game.act()
            game.dismiss(2)
            game.close()
            game = CipherGame(path, source=ARTICLE)
            try:
                self.assertEqual(game.state.puzzle.plaintext, ARTICLE)
                self.assertEqual(game.state.puzzle.number, 2)
                self.assertEqual(game.state.coins, 10)
                self.assertEqual(game.state.mode, 'command')
                self.assertIsNone(game.state.robots[2])
                self.assertTrue(all(bot.hint is None for bot in game.state.robots if bot))
                rule = game.state.puzzle.rule
                game.submit(rule.multiplier, rule.addend)
                expected = asdict(game.state)
            finally:
                game.close()
            game = CipherGame(path, source=ARTICLE)
            try:
                self.assertEqual(asdict(game.state), expected)
                self.assertFalse(game.submit(rule.multiplier, rule.addend))
            finally:
                game.close()

"""Letter-rule puzzles and a persistent, transactional robot economy."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import random
import sqlite3
import string

START_COINS = 20
SOLVE_REWARD = 10
ACTION_COST = 1
STAFF_COST = 5
TEAM_SIZE = 5
RULES = tuple((m, b) for m in (1, 2) for b in range(4) if (m, b) != (1, 0))


@dataclass(frozen=True)
class CipherRule:
    multiplier: int
    addend: int

    def __post_init__(self):
        if (type(self.multiplier) is not int or type(self.addend) is not int
                or self.multiplier not in (1, 2) or self.addend not in range(4)):
            raise ValueError('乘数只能填 1 或 2，加数只能填 0、1、2、3。')

    def encrypt(self, text: str) -> str:
        """A=1 ... Z=26; wrap to 1..26, preserving case and nonletters."""
        result = []
        for char in text:
            if char in string.ascii_letters:
                base = ord('A' if char.isupper() else 'a')
                number = ord(char) - base + 1
                result.append(chr(base + (number * self.multiplier + self.addend - 1) % 26))
            else:
                result.append(char)
        return ''.join(result)


@dataclass
class Robot:
    number: int
    hint: list[int] | None = None
    actions: int = 0


@dataclass
class Puzzle:
    number: int
    plaintext: str
    rule: CipherRule
    substitutions: dict[str, str] | None = None
    solved: bool = False
    attempts: int = 0
    last_guess: list[int] | None = None

    @property
    def ciphertext(self):
        mapping = self.substitutions or {}
        table = str.maketrans({**mapping, **{a.lower(): b.lower() for a, b in mapping.items()}})
        # One pass: B→U and U→D must not turn the original B into D.
        return self.rule.encrypt(self.plaintext).translate(table)


@dataclass
class GameState:
    puzzle: Puzzle
    coins: int = START_COINS
    wins: int = 0
    mode: str = 'solo'
    robots: list[Robot | None] = field(default_factory=lambda: [Robot(i + 1) for i in range(TEAM_SIZE)])
    next_robot: int = TEAM_SIZE + 1

    @classmethod
    def from_json(cls, payload):
        values = json.loads(payload)
        puzzle = values.pop('puzzle')
        puzzle.pop('clue_letters', None)  # Older saves used plaintext clues.
        puzzle['rule'] = CipherRule(**puzzle['rule'])
        values['robots'] = [Robot(**robot) if robot else None for robot in values['robots']]
        return cls(puzzle=Puzzle(**puzzle), **values)


class CipherGame:
    def __init__(self, path: Path | None = None, source=None, rng=None):
        self.rng = rng if rng is not None else random.Random()
        if source is not None:
            self.validate_source(source)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path if path is not None else ':memory:')
        try:
            self.db.execute('CREATE TABLE IF NOT EXISTS game (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                row = self.db.execute('SELECT payload FROM game WHERE id=1').fetchone()
                if row:
                    self.state = GameState.from_json(row[0])
                    if source is not None and source != self.state.puzzle.plaintext:
                        self._replace_puzzle(source)
                        self._save()
                    elif self.state.puzzle.substitutions is None:
                        self.state.puzzle.substitutions = self._make_substitutions(
                            self.state.puzzle.rule.encrypt(self.state.puzzle.plaintext))
                        self._save()
                else:
                    self.state = GameState(self._make_puzzle(1, source))
                    self._save()
        except Exception:
            self.db.close()
            raise

    def _save(self):
        self.db.execute('INSERT OR REPLACE INTO game VALUES (1, ?)',
                        (json.dumps(asdict(self.state), ensure_ascii=False),))

    @contextmanager
    def _change(self):
        """Reload under a write lock: two windows/processes cannot double-award."""
        before = None
        rng_before = self.rng.getstate()
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                before = self.db.execute('SELECT payload FROM game WHERE id=1').fetchone()[0]
                self.state = GameState.from_json(before)
                yield
                self._save()
        except Exception:
            if before is not None:
                self.state = GameState.from_json(before)
            self.rng.setstate(rng_before)
            raise

    @staticmethod
    def validate_source(source):
        if not isinstance(source, str) or not source.strip():
            raise ValueError('请先导入或填写文章正文，再开始密码破译。')
        if not any(char in string.ascii_letters for char in source):
            raise ValueError('当前正文没有 A–Z 英文字母，无法使用字母密码。请导入含英文字母的文章。')

    def _make_puzzle(self, number, source, previous=None):
        self.validate_source(source)
        rule = CipherRule(*self.rng.choice([pair for pair in RULES if pair != previous]))
        return Puzzle(number, source, rule, self._make_substitutions(rule.encrypt(source)))

    def _make_substitutions(self, ciphertext):
        alphabet = sorted({char.upper() for char in ciphertext if char in string.ascii_letters})
        selected = self.rng.sample(alphabet, min(3, len(alphabet)))
        unchanged = set(alphabet) - set(selected)
        # Keep the second layer reversible: do not merge an unchanged letter
        # with a replacement, and do not replace any letter with itself.
        candidates = [letter for letter in string.ascii_uppercase if letter not in unchanged]
        while True:
            targets = self.rng.sample(candidates, len(selected))
            if all(before != after for before, after in zip(selected, targets)):
                return dict(zip(selected, targets))

    def _replace_puzzle(self, source):
        old = self.state.puzzle
        self.state.puzzle = self._make_puzzle(old.number + 1, source,
                                             (old.rule.multiplier, old.rule.addend))
        for robot in self.state.robots:
            if robot:
                robot.hint = None

    def next_puzzle(self, source=None):
        with self._change():
            self._replace_puzzle(self.state.puzzle.plaintext if source is None else source)

    def set_mode(self, mode):
        if mode not in ('solo', 'command'):
            raise ValueError('无效的密码模式。')
        with self._change():
            self.state.mode = mode

    def submit(self, multiplier, addend):
        guess = CipherRule(multiplier, addend)
        with self._change():
            puzzle = self.state.puzzle
            if puzzle.solved:
                return False
            puzzle.attempts += 1
            puzzle.last_guess = [guess.multiplier, guess.addend]
            if guess == puzzle.rule:
                puzzle.solved = True
                self.state.wins += 1
                self.state.coins += SOLVE_REWARD
                return True
            return False

    def _spend(self, cost):
        if self.state.coins < cost:
            raise ValueError('金币不足，请先自己解题赚币。')
        self.state.coins -= cost

    def _slot(self, slot):
        if type(slot) is not int or slot not in range(TEAM_SIZE):
            raise ValueError('无效的机器人席位。')
        return self.state.robots[slot]

    def act(self, slot=None):
        """Single hints are random. A full-team dispatch covers both true values."""
        with self._change():
            if self.state.mode != 'command':
                raise ValueError('请先切换到指挥模式。')
            if self.state.puzzle.solved:
                raise ValueError('本题已破解，请先生成下一题。')
            if slot is not None:
                robot = self._slot(slot)
                if robot is None:
                    raise ValueError('该席位没有机器人。')
                slots = [slot]
            else:
                slots = [i for i, robot in enumerate(self.state.robots) if robot]
            if not slots:
                raise ValueError('没有在队机器人，请先招募。')
            self._spend(len(slots) * ACTION_COST)
            guesses = {i: [self.rng.randint(1, 2), self.rng.randint(0, 5)] for i in slots}
            if len(slots) == TEAM_SIZE:
                multiply_slot, add_slot = self.rng.sample(slots, 2)
                guesses[multiply_slot][0] = self.state.puzzle.rule.multiplier
                guesses[add_slot][1] = self.state.puzzle.rule.addend
            for i, hint in guesses.items():
                self.state.robots[i].hint = hint
                self.state.robots[i].actions += 1
            return guesses

    def dismiss(self, slot):
        with self._change():
            if self._slot(slot) is None:
                raise ValueError('该席位没有机器人。')
            self._spend(STAFF_COST)
            self.state.robots[slot] = None

    def recruit(self, slot):
        with self._change():
            if self._slot(slot) is not None:
                raise ValueError('请先解雇该席位的机器人。')
            self._spend(STAFF_COST)
            self.state.robots[slot] = Robot(self.state.next_robot)
            self.state.next_robot += 1

    def close(self):
        self.db.close()

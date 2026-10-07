"""Three-generation, offline textual mutation and deterministic heuristic scores."""
from collections import Counter
from dataclasses import dataclass, field
import random
import re

from .challenge import candidate_words, tokens, STOP_WORDS
from .wordbank import BANKS, DIRECTION_BANKS
from .blind import RuleBasedFunnySlotSelector, WildSuggestions, clean_answer, fit_answer

MAX_GENERATIONS = 3
TARGET_COUNT = 4
DIRECTIONS = ('nature', 'technology', 'surreal')
SCORE_TOKENS = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*|[\u4e00-\u9fff]|\d+")
REPLACEMENT = re.compile(r"(?:[A-Za-z]+(?:['’-][A-Za-z]+)*|[\u4e00-\u9fff]{1,12})\Z")


def text_language(text):
    han = len(re.findall(r'[\u4e00-\u9fff]', text))
    latin = len(re.findall(r'[A-Za-z]', text))
    return 'zh' if han * 2 > latin else 'en'


def choose_targets(text, rng, previous=(), used=()):
    candidates = candidate_words(text)
    return _choose_candidates(candidates, rng, previous, used)


def _choose_candidates(candidates, rng, previous, used):
    # Prefer words outside the last round, then words never offered this session.
    # With at least three alternatives, a four-word round has >=75% new targets.
    previous, used = set(previous), set(used)
    selected = []
    for repeated, seen in ((False, False), (False, True), (True, False), (True, True)):
        pool = [word for word in candidates if (word in previous) == repeated and (word in used) == seen]
        selected.extend(rng.sample(pool, min(TARGET_COUNT - len(selected), len(pool))))
    return tuple(word for word in candidates if word in selected)


def random_suggestions(target, language, rng=None, direction=None, used=(), seen_sets=(), limit=10):
    rng = rng or random.SystemRandom()
    bank = BANKS.get(language, BANKS['en'])
    category = next((kind for kind, words in bank.items() if target.casefold() in words), None)
    pool = list(bank[category]) if category else [word for words in bank.values() for word in words]
    if direction in DIRECTION_BANKS.get(language, DIRECTION_BANKS['en']):
        pool = list(DIRECTION_BANKS.get(language, DIRECTION_BANKS['en'])[direction])
    pool = list(dict.fromkeys(word for word in pool if word.casefold() != target.casefold()))
    unused = [word for word in pool if word not in used]
    selected = rng.sample(unused, min(limit, len(unused)))
    reused = [word for word in pool if word not in selected]
    selected.extend(rng.sample(reused, min(limit - len(selected), len(reused))))
    # Even after exhausting a finite bank, avoid returning an identical set
    # when another set is possible. A tiny bank may legitimately repeat.
    if frozenset(selected) in seen_sets:
        alternatives = [word for word in pool if word not in selected]
        rng.shuffle(alternatives)
        for word in alternatives:
            variant = selected[:-1] + [word]
            if frozenset(variant) not in seen_sets:
                selected = variant
                break
    rng.shuffle(selected)
    return tuple(selected)


def apply_replacements(text, replacements):
    """Simultaneous whole-token replacement; inserted text is never reprocessed."""
    cleaned = {}
    for target, value in replacements.items():
        value = value.strip()
        if not value:
            continue  # A blank field deliberately keeps this word unchanged.
        if len(value) > 40 or not REPLACEMENT.fullmatch(value):
            raise ValueError('替换内容须为单个英文词或不超过 12 字的中文词语，不能包含空格、数字或符号。')
        cleaned[target.casefold()] = value
    pieces, cursor, changed = [], 0, 0
    for span in tokens(text):
        if span.word not in cleaned:
            continue
        value = cleaned[span.word]
        original = text[span.start:span.end]
        if original.isupper():
            value = value.upper()
        elif original.istitle():
            value = value[:1].upper() + value[1:]
        pieces.extend((text[cursor:span.start], value))
        cursor = span.end
        changed += value != original
    pieces.append(text[cursor:])
    return ''.join(pieces), changed


def _score_tokens(text):
    return [word.casefold() for word in SCORE_TOKENS.findall(text)]


def distortion(original, final):
    """Mean of multiset token loss and positional token change, in percent.

    English words / Chinese characters are score tokens. O(n), deterministic,
    independent of spelling length; punctuation-only changes earn no distortion.
    """
    a, b = _score_tokens(original), _score_tokens(final)
    size = max(len(a), len(b))
    if not size:
        return 0.0
    overlap = sum((Counter(a) & Counter(b)).values()) / size
    positional = sum(left == right for left, right in zip(a, b)) / size
    return round(100 * (1 - (overlap + positional) / 2), 2)


def coherence(text):
    """Readability guard, not a semantic or grammar model.

    Multiply lexical plausibility, character cleanliness, token diversity and
    dominance penalties. Blank / symbol-only, repeated or obvious garbage text
    receives a low score without network services or dictionary dependencies.
    """
    words = _score_tokens(text)
    if not words:
        return 0.0
    known = set(STOP_WORDS) | {w for group in BANKS['en'].values() for w in group}
    plausible = 0.0
    for word in words:
        if re.fullmatch(r'[\u4e00-\u9fff]', word) or word in known:
            plausible += 1
        elif word.isdigit():
            plausible += 0.5
        elif len(word) > 24 or re.search(r'(.)\1{3,}', word) or not re.search('[aeiouy]', word):
            continue
        elif re.search(r'[^aeiouy\W]{6,}', word):
            continue
        else:
            plausible += 0.85
    nonspace = [char for char in text if not char.isspace()]
    lexical_chars = sum(char.isalnum() for char in nonspace)
    cleanliness = lexical_chars / len(nonspace) if nonspace else 0
    diversity = min(1.0, len(set(words)) / max(1, len(words) * 0.5))
    most_common = Counter(words).most_common(1)[0][1] / len(words)
    dominance = min(1.0, max(0.0, (1 - most_common) / 0.65)) if len(words) >= 4 else 1.0
    return round(100 * (plausible / len(words)) * cleanliness * diversity * dominance, 2)


@dataclass(frozen=True)
class Scores:
    distortion: float
    coherence: float
    regrowth: float


def score_text(original, final):
    d, c = distortion(original, final), coherence(final)
    return Scores(d, c, round(d * c / 100, 2))


@dataclass
class Lineage:
    original_word: str
    current_word: str
    start: int
    end: int
    generation: int = 0
    history: list = field(default_factory=list)


@dataclass(frozen=True)
class Change:
    start: int
    end: int
    original: str
    before: str
    after: str


@dataclass(frozen=True)
class Generation:
    number: int
    text: str
    direction: str
    mutated: int
    restored: int
    mutations_applied: tuple = ()
    restores_applied: tuple = ()


def classify_outcome(scores, directions, restore_ratio=0.0):
    """Descriptions, not a ranking. Rules are ordered and deterministic."""
    if scores.coherence < 40:
        return 'fragmented'
    if scores.distortion < 30 or restore_ratio >= 0.6:
        return 'restoration'
    growth = [direction for direction in directions if direction != 'restore']
    if scores.distortion >= 65 and ('surreal' in growth or len(set(growth)) >= 3):
        return 'wild'
    if scores.coherence >= 60 and growth:
        return 'redirected'
    return 'wild' if scores.distortion >= 65 else 'redirected'


class TwistedSession:
    def __init__(self, original_text, rng=None, *, blind=False, slot_selector=None):
        self.original_text = original_text
        self.current_generation = original_text
        self.generation_history = [original_text]
        self.generation = 0
        self.words_mutated = 0
        self.mutation_history = []
        self.direction = None
        self.action = None
        self.generation_records = []
        self.words_restored = 0
        self.lineage = [Lineage(original_text[span.start:span.end], original_text[span.start:span.end],
                                span.start, span.end) for span in tokens(original_text)]
        self.round_complete = False
        self.rng = rng or random.SystemRandom()
        self.language = text_language(original_text)
        self.targets = ()
        self.suggestions = {}
        self.used_target_words = set()
        self.used_target_positions = set()
        self.previous_target_positions = set()
        self.target_history = []
        self.used_suggestions = set()
        self.suggestion_history = []
        self.phase = 'blind' if blind else 'growth'
        self.blind_slots = tuple((slot_selector or RuleBasedFunnySlotSelector()).select_funny_slots(original_text)) if blind else ()
        self.blind_inputs = {slot.id: '' for slot in self.blind_slots}
        self.wild = WildSuggestions(self.rng)
        self.seed_record = None
        self.growth_awarded = False
        if not blind:
            self._select()

    def wild_suggestion(self, slot_id, language):
        if self.phase != 'blind':
            raise ValueError('请先完成盲填并揭晓故事。')
        slot = next(slot for slot in self.blind_slots if slot.id == slot_id)
        value = self.wild.suggest(slot.category, language)
        self.blind_inputs[slot_id] = value
        return value

    def validate_blind(self, answers):
        if self.phase != 'blind' or not self.blind_slots or set(answers) != set(self.blind_inputs):
            raise ValueError('请填写每一项，使用 1–100 字的词或短语。')
        return {key: clean_answer(value) for key, value in answers.items()}

    def reveal_seed(self, answers):
        cleaned = self.validate_blind(answers)
        # A selector (including a future optional model) must return trustworthy
        # non-overlapping source spans. Validate before touching session state.
        slots = sorted(self.blind_slots, key=lambda slot: slot.start)
        cursor = 0
        for slot in slots:
            if not (cursor <= slot.start < slot.end <= len(self.original_text)) or self.original_text[slot.start:slot.end] != slot.original:
                raise ValueError('盲填位置无效，请重新开始。')
            cursor = slot.end
        lineage = [item for item in self.lineage if not any(item.start < slot.end and slot.start < item.end for slot in slots)]
        changes = []
        for index, slot in enumerate(slots):
            following = slots[index + 1] if index + 1 < len(slots) else None
            if following and self.original_text[slot.end:following.start].strip():
                following = None
            value = fit_answer(slot, cleaned[slot.id], following, cleaned[following.id] if following else '')
            item = Lineage(slot.original, value, slot.start, slot.end)
            if value != slot.original:
                item.history.append((0, slot.original, value, False))
                changes.append(Change(slot.start, slot.end, slot.original, slot.original, value))
            lineage.append(item)
        self.lineage = sorted(lineage, key=lambda item: item.start)
        self.blind_inputs = cleaned
        self.current_generation = self._render()
        self.seed_record = Generation(0, self.current_generation, 'seed', len(changes), 0, tuple(changes))
        self.words_mutated += len(changes)
        self.used_target_positions.update(slot.start for slot in slots)
        self.previous_target_positions = {slot.start for slot in slots}
        self.used_target_words.update(slot.original.casefold() for slot in slots)
        self.mutation_history.append(dict(cleaned))
        self.phase = 'reveal'
        return self.current_generation

    def continue_seed(self):
        if self.phase != 'reveal':
            raise ValueError('请先完成盲填并揭晓故事。')
        self.phase = 'growth'
        self._select()

    def _require_growth(self):
        if self.phase != 'growth':
            raise ValueError('请先完成盲填并揭晓故事。')

    def _select(self):
        # Occurrence identities remain anchored in the original text even when
        # multiple source words mutate into the same spelling.
        candidates = list(dict.fromkeys(item.current_word.casefold() for item in self.lineage
                          if item.current_word.casefold() in candidate_words(item.current_word)
                          or item.history or item.start in {slot.start for slot in self.blind_slots}))
        # A newly spelled mutation (forest -> machine) is still the same source
        # position. Prefer genuinely fresh positions, but allow chains when
        # alternatives run out rather than banning previously mutated words.
        previous = set(self.targets) | {item.current_word.casefold() for item in self.lineage
                                       if item.start in self.previous_target_positions}
        used = self.used_target_words | {item.current_word.casefold() for item in self.lineage
                                        if item.start in self.used_target_positions}
        self.targets = _choose_candidates(candidates, self.rng, previous, used)
        self.previous_target_positions = {item.start for item in self.lineage
                                          if item.current_word.casefold() in self.targets}
        self.used_target_positions.update(self.previous_target_positions)
        self.used_target_words.update(self.targets)
        self.target_history.append(self.targets)
        self.suggestions = {word: () for word in self.targets}

    def set_direction(self, direction):
        self._require_growth()
        if direction not in DIRECTIONS:
            raise ValueError('请选择这一代的生长方向。')
        if self.round_complete or self.finished:
            raise ValueError('本代已完成，请进入下一代或再次扭曲。')
        self.direction = direction
        self.action = 'mutate'
        for word in self.targets:
            self.refresh_suggestions(word)

    def refresh_suggestions(self, target):
        if self.round_complete or self.finished or self.action != 'mutate' or target not in self.targets:
            raise ValueError('只能替换本代选中的目标词。')
        choices = random_suggestions(target, self.language, self.rng, self.direction,
                                     self.used_suggestions, self.suggestion_history, limit=5)
        self.suggestions[target] = choices
        self.used_suggestions.update(choices)
        self.suggestion_history.append(frozenset(choices))
        return choices

    def begin_restore(self):
        self._require_growth()
        if self.round_complete or self.finished:
            raise ValueError('本代已完成，请进入下一代或再次扭曲。')
        # Restoration is an action, independent of the three growth directions.
        self.action = 'restore'

    @property
    def restore_options(self):
        return tuple(dict.fromkeys(self.restore_key(item) for item in self.lineage
                                   if item.current_word != item.original_word))

    def restore_key(self, item):
        key = (item.original_word.casefold(), item.current_word.casefold())
        # Blind slots restore one occurrence, even when two answers coincide.
        return key + (item.start,) if item.start in {slot.start for slot in self.blind_slots} else key

    def _render(self):
        pieces, cursor = [], 0
        for item in self.lineage:
            pieces.extend((self.original_text[cursor:item.start], item.current_word))
            cursor = item.end
        pieces.append(self.original_text[cursor:])
        return ''.join(pieces)

    @property
    def restoration_ratio(self):
        changed = [item for item in self.lineage if item.history]
        return sum(item.current_word == item.original_word for item in changed) / len(changed) if changed else 0

    @property
    def outcome(self):
        return classify_outcome(self.scores, [record.direction for record in self.generation_records], self.restoration_ratio)

    @property
    def finished(self):
        return self.generation == MAX_GENERATIONS

    @property
    def scores(self):
        return score_text(self.original_text, self.current_generation)

    def regrow(self, replacements=None, restore=()):
        self._require_growth()
        replacements = replacements or {}
        if self.finished or self.round_complete:
            raise ValueError('本代已完成，请进入下一代或再次扭曲。')
        if not set(replacements) <= set(self.targets):
            raise ValueError('只能替换本代选中的目标词。')
        if self.action is None:
            raise ValueError('请选择这一代的生长方向。')
        restore = set(restore)
        if not restore <= set(self.restore_options):
            raise ValueError('只能恢复当前列表中选中的变异词。')
        if (self.action == 'restore' and replacements) or (self.action != 'restore' and restore):
            raise ValueError('再生回来仅使用勾选项；生长方向使用自定义替换。')
        # Validate every input before modifying any lineage or session state.
        apply_replacements('', replacements)
        pending = []
        for item in self.lineage:
            original, current = item.original_word, item.current_word
            restoring = self.restore_key(item) in restore
            value = original if restoring else replacements.get(current.casefold(), '').strip() or current
            if not restoring:
                if current.isupper():
                    value = value.upper()
                elif current.istitle():
                    value = value[:1].upper() + value[1:]
            if value != current:
                pending.append((item, value, restoring))
        count = sum(not restoring for _, _, restoring in pending)
        restored = sum(restoring for _, _, restoring in pending)
        mutations_applied, restores_applied = [], []
        for item, value, restoring in pending:
            change = Change(item.start, item.end, item.original_word, item.current_word, value)
            (restores_applied if restoring else mutations_applied).append(change)
            item.history.append((self.generation + 1, item.current_word, value, restoring))
            item.current_word = value
            item.generation = self.generation + 1
        self.current_generation = self._render()
        self.generation += 1
        self.words_mutated += count
        self.words_restored += restored
        self.generation_history.append(self.current_generation)
        self.generation_records.append(Generation(self.generation, self.current_generation,
            'restore' if self.action == 'restore' else self.direction, count, restored,
            tuple(mutations_applied), tuple(restores_applied)))
        self.mutation_history.append(dict(replacements))
        self.round_complete = True
        return self.current_generation

    def next_generation(self):
        if self.finished or not self.round_complete:
            raise ValueError('请先完成本代；最多进行 3 代。')
        self._select()
        self.round_complete = False
        self.direction = None
        self.action = None

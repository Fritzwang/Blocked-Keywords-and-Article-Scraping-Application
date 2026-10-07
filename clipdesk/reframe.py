"""Offline, source-only narrative reframing. No Article, Store or scoring writes."""
from dataclasses import dataclass, field
import random
import re

MAX_ROUNDS = 3
METHODS = ('pure', 'editorial')
GOALS = (
    '让这段内容听起来更积极。', '让事件显得更有争议。', '改变这段内容最重要的重点。',
    '让某个角色显得更需要负责。', '让结果听起来更严重。', '创造一个仍然可读但最意外的版本。',
)
WORDS = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
HAN = re.compile(r'[\u4e00-\u9fff]')
BOUNDARY = re.compile(r'[,;，；：:]\s*|[。！？.!?]\s+|\s+(?=(?:and|but|while|because|although|despite|after|before|during|when|with|without|through|including|instead)\b)', re.I)
META = re.compile(r'^(?:https?://|www\.|copyright\b|all rights reserved\b|home\s*$|privacy\s*$|published\s*:|updated\s*:|作者[:：]|来源[:：]|责任编辑[:：]|首页\s*$|导航\s*$)', re.I)


@dataclass(frozen=True)
class Section:
    id: int
    start: int
    end: int
    paragraph: int
    text: str


@dataclass(frozen=True)
class Fragment:
    id: str
    text: str
    start: int
    end: int
    paragraph: int


@dataclass(frozen=True)
class Pieces:
    fragments: tuple
    gaps: tuple
    suffix: str

    def render(self, order):
        by_id = {fragment.id: fragment for fragment in self.fragments}
        # Reuse source whitespace separators and source terminal punctuation.
        # No words or punctuation are generated, even when pieces are removed.
        parts = []
        for index, fragment_id in enumerate(order):
            if index:
                parts.append(self.gaps[index - 1])
            parts.append(by_id[fragment_id].text)
        return ''.join(parts) + self.suffix


def select_sections(text):
    """Non-overlapping source ranges: one sentence or adjacent short sentences."""
    sections = []
    for paragraph, match in enumerate(re.finditer(r'[^\r\n]+', text), 1):
        line = match.group()
        if META.match(line.strip()):
            continue
        spans = list(re.finditer(r'[^.!?。！？]+(?:[.!?。！？]+[”"’\)\]]*|$)', line))
        index = 0
        while index < len(spans):
            first = spans[index]
            start, end = first.start(), first.end()
            index += 1
            content = line[start:end].strip()
            limit = 190 if HAN.search(content) else 420
            # Pair short adjacent sentences; never take a whole long paragraph.
            if len(WORDS.findall(content)) < 18 and len(HAN.findall(content)) < 32 and index < len(spans):
                paired = line[start:spans[index].end()].strip()
                if len(paired) <= limit:
                    end = spans[index].end()
                    content = paired
                    index += 1
            if 'http://' in content or 'https://' in content or META.match(content):
                continue
            meaningful = len(WORDS.findall(content)) >= 3 or len(HAN.findall(content)) >= 8
            if not meaningful or len(content) > limit:
                continue
            raw = line[start:end]
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw) - len(raw.rstrip())
            absolute = match.start() + start + leading
            finish = match.start() + end - trailing
            sections.append(Section(len(sections), absolute, finish, paragraph, text[absolute:finish]))
    return tuple(sections)


def split_fragments(section):
    """Aim for 5–7 readable phrase pieces; retain exact source character spans."""
    text = section.text
    terminal = re.search(r'[.!?。！？]+[”"’\)\]]*$', text)
    body_end = terminal.start() if terminal else len(text)
    body = text[:body_end]
    latin = len(WORDS.findall(body))
    chinese = len(HAN.findall(body)) > latin * 2
    def weight(part):
        return len(HAN.findall(part)) if chinese else len(WORDS.findall(part))
    minimum = 4 if chinese else 2
    desired = min(6, max(1, weight(body) // (6 if chinese else 3)))
    boundaries = [match.end() for match in BOUNDARY.finditer(body)]
    cuts = [0]
    for boundary in boundaries:
        if weight(body[cuts[-1]:boundary]) >= minimum and weight(body[boundary:]) >= minimum:
            cuts.append(boundary)
    cuts.append(len(body))
    spans = list(zip(cuts, cuts[1:]))
    # A punctuation-free clause can still be divided into balanced phrases,
    # never into a row of single English tokens or single Chinese characters.
    while len(spans) < desired:
        eligible = [(weight(body[a:b]), i, a, b) for i, (a, b) in enumerate(spans)
                    if weight(body[a:b]) >= minimum * 2]
        if not eligible:
            break
        _, index, start, end = max(eligible)
        units = list(HAN.finditer(body[start:end])) if chinese else list(WORDS.finditer(body[start:end]))
        middle = len(units) // 2
        if not chinese:
            glue = {'a', 'an', 'the', 'to', 'of', 'for', 'in', 'with', 'and', 'or', 'but', 'by', 'at'}
            while middle > minimum and units[middle - 1].group().casefold() in glue:
                middle -= 1
        midpoint = start + units[middle].start()
        spans[index:index + 1] = [(start, midpoint), (midpoint, end)]
    while len(spans) > 7:
        index = min(range(len(spans) - 1), key=lambda i: weight(body[spans[i][0]:spans[i + 1][1]]))
        spans[index:index + 2] = [(spans[index][0], spans[index + 1][1])]
    fragments = []
    for start, end in spans:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            fragments.append(Fragment(f'{section.id}:{len(fragments)}', text[start:end],
                                      section.start + start, section.start + end, section.paragraph))
    gaps = tuple(section.text[left.end - section.start:right.start - section.start]
                 for left, right in zip(fragments, fragments[1:]))
    suffix = text[fragments[-1].end - section.start:] if fragments else text
    return Pieces(tuple(fragments), gaps, suffix)


@dataclass
class Round:
    number: int
    section: Section
    pieces: Pieces
    goal: str
    original_section: str
    order: list
    removed: list = field(default_factory=list)
    removed_positions: dict = field(default_factory=dict)
    locked: bool = False


@dataclass(frozen=True)
class RoundRecord:
    number: int
    source_range: tuple
    original_section: str
    fragments: tuple
    final_order: tuple
    removed_fragments: tuple
    goal: str
    reframed_section: str
    moved: int
    inversions: int
    possible_pairs: int


def classify_outcome(history):
    """Describe operations, never infer whether a semantic goal was achieved."""
    removed = sum(len(record.removed_fragments) for record in history)
    moved = sum(record.moved for record in history)
    inversions = sum(record.inversions for record in history)
    pairs = sum(record.possible_pairs for record in history)
    changed_rounds = sum(record.moved > 0 or bool(record.removed_fragments) for record in history)
    if removed == 0:
        return 'close' if inversions <= max(1, pairs * .1) else 'context'
    if removed >= 2 and moved >= 6 and changed_rounds >= 2 and pairs and inversions / pairs >= .35:
        return 'strong'
    return 'selective'


class ReframeSession:
    def __init__(self, original_text, rng=None):
        self.original_text = original_text
        self.working_copy = original_text
        self.sections = select_sections(original_text)
        self.method = None
        self.current_round = None
        self.history = []
        self.used_section_ranges = set()
        self.rng = rng or random.SystemRandom()
        self.goals = self.rng.sample(GOALS, MAX_ROUNDS)
        self._pieces = {section.id: split_fragments(section) for section in self.sections}
        self._orders = {key: tuple(fragment.id for fragment in pieces.fragments) for key, pieces in self._pieces.items()}
        self._versions = {}

    def start(self, method):
        if method not in METHODS or self.method is not None:
            raise ValueError('请先选择纯重排或编辑重构。')
        if not self.sections:
            raise ValueError('正文太短或没有适合重构的片段。')
        self.method = method
        self._select_round()

    def _select_round(self):
        unused = [section for section in self.sections if (section.start, section.end) not in self.used_section_ranges]
        alternatives = [section for section in self.sections
                        if self.current_round is None or section.id != self.current_round.section.id]
        pool = unused or alternatives or list(self.sections)
        preferred = [section for section in pool if len(self._orders[section.id]) >= 5]
        section = self.rng.choice(preferred or pool)
        self.used_section_ranges.add((section.start, section.end))
        source_pieces = self._pieces[section.id]
        order = list(self._orders[section.id])
        by_id = {fragment.id: fragment for fragment in source_pieces.fragments}
        # Reused short sections inherit the current pieces, so locked removals
        # do not reappear and a new round cannot silently add source material.
        current = Pieces(tuple(by_id[key] for key in order), source_pieces.gaps[:max(0, len(order) - 1)], source_pieces.suffix)
        self.current_round = Round(len(self.history) + 1, section, current,
                                   self.goals[len(self.history)], current.render(order), order)

    @property
    def removal_limit(self):
        return self.current_round.number - 1 if self.method == 'editorial' and self.current_round else 0

    @property
    def minimum_kept(self):
        return min(3, len(self.current_round.pieces.fragments))

    @property
    def finished(self):
        return len(self.history) == MAX_ROUNDS

    @property
    def outcome(self):
        return classify_outcome(self.history)

    @property
    def fragments_moved(self):
        return sum(record.moved for record in self.history)

    @property
    def fragments_removed(self):
        return sum(len(record.removed_fragments) for record in self.history)

    @property
    def sections_reframed(self):
        return len({record.source_range for record in self.history})

    def _editable(self):
        if not self.current_round or self.current_round.locked or self.finished:
            raise ValueError('本轮已锁定，请进入下一轮。')
        return self.current_round

    def move(self, fragment_id, step):
        current = self._editable()
        if fragment_id not in current.order or step not in (-1, 1):
            raise ValueError('请选择当前列表中的信息碎片。')
        index = current.order.index(fragment_id)
        destination = index + step
        if 0 <= destination < len(current.order):
            current.order[index], current.order[destination] = current.order[destination], current.order[index]

    def remove(self, fragment_id):
        current = self._editable()
        if self.method == 'pure':
            raise ValueError('纯重排必须保留所有信息碎片。')
        if fragment_id not in current.order:
            raise ValueError('请选择当前列表中的信息碎片。')
        if len(current.removed) >= self.removal_limit:
            raise ValueError(f'本轮最多删除 {self.removal_limit} 个碎片。')
        if len(current.order) <= self.minimum_kept:
            raise ValueError('需要保留至少 3 个信息碎片。')
        current.removed_positions[fragment_id] = current.order.index(fragment_id)
        current.order.remove(fragment_id)
        current.removed.append(fragment_id)

    def restore(self, fragment_id):
        current = self._editable()
        if fragment_id not in current.removed:
            raise ValueError('请选择已移除的信息碎片。')
        current.order.insert(min(current.removed_positions.pop(fragment_id), len(current.order)), fragment_id)
        current.removed.remove(fragment_id)

    def preview(self):
        return self.current_round.pieces.render(self.current_round.order)

    def lock(self):
        current = self._editable()
        original_ids = [fragment.id for fragment in current.pieces.fragments]
        all_ids = current.order + current.removed
        if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(original_ids):
            raise ValueError('只能重排原始碎片，不能新增、复制或丢失碎片。')
        if self.method == 'pure' and current.removed:
            raise ValueError('纯重排必须保留所有信息碎片。')
        if len(current.removed) > self.removal_limit:
            raise ValueError(f'本轮最多删除 {self.removal_limit} 个碎片。')
        if len(current.order) < self.minimum_kept:
            raise ValueError('需要保留至少 3 个信息碎片。')
        baseline = [key for key in original_ids if key not in current.removed]
        ranks = [baseline.index(key) for key in current.order]
        inversions = sum(left > right for index, left in enumerate(ranks) for right in ranks[index + 1:])
        moved = sum(left != right for left, right in zip(baseline, current.order))
        text = self.preview()
        by_id = {fragment.id: fragment for fragment in current.pieces.fragments}
        record = RoundRecord(current.number, (current.section.start, current.section.end), current.original_section,
            current.pieces.fragments, tuple(current.order), tuple(by_id[key] for key in current.removed),
            current.goal, text, moved, inversions, len(ranks) * (len(ranks) - 1) // 2)
        self._versions[current.section.id] = text
        self._orders[current.section.id] = tuple(current.order)
        self.working_copy = self._render_story()
        self.history.append(record)
        current.locked = True
        return text

    def _render_story(self):
        parts, cursor = [], 0
        for section in self.sections:
            parts.extend((self.original_text[cursor:section.start], self._versions.get(section.id, section.text)))
            cursor = section.end
        parts.append(self.original_text[cursor:])
        return ''.join(parts)

    def next_round(self):
        if self.finished or not self.current_round or not self.current_round.locked:
            raise ValueError('请先锁定本轮；每局共 3 轮。')
        self._select_round()

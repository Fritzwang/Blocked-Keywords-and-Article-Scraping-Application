"""Offline Mad Libs slots, keyed to immutable source character ranges.

FunnySlotSelector is the extension point for a future optional selector. The
default uses only local phrase lists, word shapes and neighbouring words.
"""
from dataclasses import dataclass
import random
import re
from typing import Protocol

from .challenge import STOP_WORDS, ZH_STOP, tokens

CATEGORIES = ('person', 'animal', 'action', 'place', 'object', 'group', 'description')
MAX_INPUT_LENGTH = 100
WORD = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")

# Noun phrases include roles and everyday news/science vocabulary. Longest
# matches win over nested words; unknown content words remain a last resort.
PHRASES = {
    'person': 'prime minister|president|minister|mayor|scientist|astronaut|teacher|doctor|reporter|researcher|engineer|student|wizard|grandma|intern|首相|总理|总统|部长|市长|科学家|宇航员|老师|医生|记者|学生|巫师',
    'animal': 'kangaroo|penguin|elephant|dinosaur|pigeon|goose|duck|cat|dog|bird|horse|whale|turtle|袋鼠|企鹅|大象|恐龙|鸽子|小猫|小狗|动物',
    'place': 'Sydney|London|Beijing|Melbourne|Paris|Australia|China|Moon|Mars|New York|supermarket|university library|school|office|forest|city|garden|river|ocean|island|castle|mountain|悉尼|伦敦|北京|月球|火星|超市|学校|办公室|森林|城市|花园|河流|海洋|场馆',
    'object': 'programming language|data structures|standard library|source code|space station|rubber duck|microwave|spaceship|sandwich|computer|printer|machine|robot|telescope|satellite|package|module|program|language|software|system|book|flower|food|lunch|project|experiment|rocket|代码|图书|电脑|打印机|机器|飞船|三明治|微波炉|软件|系统|程序|装置|项目|实验|火箭',
    'group': 'business leaders|city council|research team|local families|space agency|volunteers|residents|children|programmers|researchers|scientists|engineers|students|leaders|government|company|committee|team|工作人员|科学家们|研究团队|志愿者|居民|儿童|政府|公司|集团',
    'description': 'confused|nervous|exhausted|angry|quiet|ancient|mysterious|dramatic|strange|tiny|golden|powerful|simple|dynamic|attractive|important|popular|beautiful|happy|sad|安静|神秘|奇怪|紧张|愤怒|古老|美丽|重要|舒适',
}
VERBS = {
    'meet': 'met', 'visit': 'visited', 'greet': 'greeted', 'watch': 'watched',
    'discover': 'discovered', 'protect': 'protected', 'announce': 'announced',
    'build': 'built', 'open': 'opened', 'carry': 'carried', 'launch': 'launched',
    'support': 'supported', 'create': 'created', 'find': 'found', 'use': 'used',
    'make': 'made', 'welcome': 'welcomed', 'plant': 'planted', 'explore': 'explored',
    'recover': 'recovered', 'dance': 'danced', 'argue': 'argued', 'work': 'worked',
    'arrive': 'arrived', 'return': 'returned', 'walk': 'walked', 'travel': 'travelled',
    'say': 'said', 'provide': 'provided', 'allow': 'allowed', 'print': 'printed',
    'raise': 'raised', 'encourage': 'encouraged', 'reduce': 'reduced', 'connect': 'connected',
    'emphasize': 'emphasized', 'promise': 'promised', 'report': 'reported',
}
ACTION_FORMS = {}
for base, past in VERBS.items():
    ACTION_FORMS[base] = 'base'
    ACTION_FORMS[past] = 'past'
    ACTION_FORMS[base[:-1] + 'ies' if base.endswith('y') else base + ('es' if base.endswith(('ch', 'sh')) else 's')] = 'present'
    ACTION_FORMS[(base[:-1] if base.endswith('e') else base) + 'ing'] = 'gerund'
ZH_ACTIONS = '访问 会见 发现 保护 恢复 建造 开放 提供 举办 参加 研究 使用 制造 完成 介绍 发射 宣布'.split()


@dataclass(frozen=True)
class FunnySlot:
    start: int
    end: int
    original: str
    category: str
    form: str = ''
    connector: str = ''
    prefix: str = ''
    sentence_start: bool = False

    @property
    def id(self):
        return f'{self.start}:{self.end}'


class FunnySlotSelector(Protocol):
    def select_funny_slots(self, text: str, count: int = 5) -> tuple[FunnySlot, ...]: ...


class RuleBasedFunnySlotSelector:
    def select_funny_slots(self, text, count=5):
        count = max(4, min(6, count))
        candidates = []

        def add(start, end, category, priority, form=''):
            prefix = ''
            if category in ('person', 'animal', 'object', 'group', 'place'):
                # Include an attached article and adjective list as a unit:
                # "an interpreted, object-oriented, high-level language" must
                # not become "an interpreted ... a haunted microwave".
                lead = re.search(r'\b(the|a|an)\s+(?:[A-Za-z]+(?:-[A-Za-z]+)*,?\s+){0,5}$', text[:start], re.I)
                if lead and any(word.lower() in ACTION_FORMS or word.lower() in STOP_WORDS - {'and', 'or'}
                                for word in WORD.findall(lead.group())[1:]):
                    lead = re.search(r'\b(the|a|an)\s+$', text[:start], re.I)
                if lead:
                    start = lead.start()
                if category == 'place':
                    lead = re.search(r'\b(in|at|on|inside|under|near|to|from)\s+$', text[:start], re.I)
                    if lead:
                        prefix, start = lead.group(1).lower(), lead.start()
                    elif start and text[start - 1] in '在到从':
                        prefix, start = text[start - 1], start - 1
            original = text[start:end]
            sentence_start = not text[:start].strip() or bool(re.search(r'[.!?。！？\n]\s*$', text[:start]))
            connector = ''
            if category == 'action' and form:
                before = WORD.findall(text[:start])
                if before and before[-1].lower() in ('to', 'can', 'could', 'will', 'would', 'may', 'must', 'should'):
                    form = 'base'
                tail = text[end:]
                next_word = re.match(r'\s+([A-Za-z]+)', tail)
                if next_word and next_word[1].lower() not in STOP_WORDS | {'while', 'during', 'despite'}:
                    connector = ' with'
                elif re.match(r'\s+(?:the|a|an|his|her|their|our)\s+', tail, re.I):
                    connector = ' with'
            candidates.append((priority, FunnySlot(start, end, original, category, form, connector, prefix, sentence_start)))

        for category, words in PHRASES.items():
            for phrase in sorted(words.split('|'), key=len, reverse=True):
                pattern = re.escape(phrase)
                if phrase.isascii():
                    pattern = r'(?<![\w’\'])' + pattern + (r's?' if ' ' not in phrase and not phrase.endswith('s') and phrase.islower() else '') + r'(?![\w’\'])'
                for match in re.finditer(pattern, text, re.I):
                    add(match.start(), match.end(), category, 100 + len(phrase) / 3)
        for match in WORD.finditer(text):
            word = match.group().lower()
            if word in ACTION_FORMS:
                # Adjectival participles such as "built in data structures"
                # and "an abandoned office" do not act as sentence verbs.
                before = WORD.findall(text[:match.start()])
                previous = before[-1].lower() if before else ''
                if previous in {'a', 'an', 'the', 'for', 'of', 'as', 'with', 'in'}:
                    continue
                if word in {'make', 'makes', 'made'} and re.match(r'\s+(?:it|them|me|us|him|her)\b', text[match.end():], re.I):
                    continue
                if ACTION_FORMS[word] == 'past' and (previous in {'a', 'an', 'the'} or
                        '-' in previous or re.match(r'\s+in\b', text[match.end():], re.I) and word == 'built'):
                    continue
                add(match.start(), match.end(), 'action', 108, ACTION_FORMS[word])
        for phrase in ZH_ACTIONS:
            for match in re.finditer(phrase, text):
                add(match.start(), match.end(), 'action', 108)
        # Capitalized names: contextual place after a preposition, person as
        # subject before a known verb. Acronyms/technical names default to object.
        for match in re.finditer(r'\b[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){0,2}\b', text):
            if match.group().lower() in STOP_WORDS:
                continue
            before, after = text[:match.start()], text[match.end():]
            following = re.match(r'\s+([A-Za-z]+)', after)
            category = 'place' if re.search(r'\b(?:in|at|from|near|to)\s+$', before, re.I) else (
                'person' if following and following[1].lower() in ACTION_FORMS else 'object')
            if match.group() in {'Python', 'Java', 'Linux', 'Windows', 'JavaScript'}:
                category = 'object'
            add(match.start(), match.end(), category, 60)
        # Low confidence fallback still excludes function words, adverbs,
        # possessives and known verb forms. It never creates fake locations.
        for span in tokens(text):
            word = text[span.start:span.end]
            if word.lower() in STOP_WORDS or word in ZH_STOP or word.lower() in ACTION_FORMS:
                continue
            if word.lower().endswith(('ly', "'s", '’s')):
                continue
            add(span.start, span.end, 'object', 10)

        chosen = []
        used_categories = set()
        while candidates and len(chosen) < count:
            candidates.sort(key=lambda entry: (entry[0] + (90 if entry[1].category not in used_categories else
                                               (-25 if entry[1].category == 'action' else 0))
                                              - (18 if any(old.category == entry[1].category and
                                                   abs(old.start - entry[1].start) < 220 for old in chosen) else 0)
                                              - min(entry[1].start / 100, 35), -entry[1].start), reverse=True)
            _, slot = candidates.pop(0)
            if any(slot.start < old.end and old.start < slot.end for old in chosen):
                continue
            chosen.append(slot)
            used_categories.add(slot.category)
        # Source order is kept internally; the UI uses category order instead.
        return tuple(sorted(chosen, key=lambda item: item.start))


def select_funny_slots(text, count=5):
    return RuleBasedFunnySlotSelector().select_funny_slots(text, count)


WILD_PHRASES = {
    'en': {
        'person': ('an exhausted wizard', 'a confused astronaut', 'an angry grandma', 'three suspicious ducks', 'a very nervous billionaire', 'an unpaid intern', 'a retired superhero in slippers', 'a pirate with stage fright'),
        'animal': ('a dramatic penguin', 'an angry goose', 'a suspicious cat', 'a tiny dinosaur', 'a confused kangaroo', 'a pigeon wearing a crown'),
        'place': ('on the Moon', 'inside a haunted supermarket', "under someone's bed", 'in an abandoned office', 'inside a giant toaster', "at the world's worst theme park"),
        'action': ('arguing with pigeons', 'dancing badly', "stealing everyone's lunch", 'pretending to be a printer', 'screaming at the Wi-Fi', 'starting a revolution', 'negotiating with a sandwich', 'auditioning for a potato commercial'),
        'object': ('a haunted microwave', 'a golden toilet', 'seventeen rubber ducks', 'a broken spaceship', 'an illegal sandwich', 'a mysterious USB stick', 'a self-important teapot', 'a tiny emergency disco'),
        'group': ('a committee of sleepy dragons', 'an unpaid wizard union', 'a choir of angry accountants', 'three raccoons in a trench coat', 'the intergalactic lunch inspectors', 'a council of suspicious grandmas'),
        'description': ('suspiciously sparkly', 'emotionally unavailable', 'dramatically undercooked', 'unreasonably majestic', 'secretly made of cheese', 'allergic to Mondays'),
    },
    'zh': {
        'person': ('一个筋疲力尽的巫师', '一个迷路的宇航员', '一位暴躁的奶奶', '三只可疑的鸭子', '一个非常紧张的亿万富翁', '一个没拿工资的实习生', '一位穿拖鞋的退休超人', '一个怯场的海盗'),
        'animal': ('一只戏很多的企鹅', '一只愤怒的大鹅', '一只可疑的猫', '一只迷你恐龙', '一只困惑的袋鼠', '一只戴王冠的鸽子'),
        'place': ('在月球上', '在闹鬼的超市里', '在某个人的床底下', '在废弃的办公室里', '在巨型烤面包机里', '在全世界最糟糕的主题公园里'),
        'action': ('和鸽子争论', '跳一段蹩脚的舞', '偷走所有人的午餐', '假装自己是打印机', '对着无线网络尖叫', '发动一场革命', '与三明治谈判', '参加土豆广告试镜'),
        'object': ('一台闹鬼的微波炉', '一个黄金马桶', '十七只橡皮鸭', '一艘坏掉的飞船', '一个违法的三明治', '一个神秘的优盘', '一把自命不凡的茶壶', '一个袖珍应急迪厅'),
        'group': ('一个瞌睡龙委员会', '一个欠薪巫师工会', '一个暴躁会计合唱团', '三只穿风衣的浣熊', '一队星际午餐检查员', '一个可疑奶奶理事会'),
        'description': ('闪亮得很可疑', '极其不情愿', '半生不熟', '威风得毫无道理', '偷偷用奶酪做成', '对星期一过敏'),
    },
}


class WildSuggestions:
    def __init__(self, rng=None):
        self.rng = rng or random.SystemRandom()
        self.used_wild_suggestions = set()
        self.last = {}

    def suggest(self, category, language='en'):
        pool = WILD_PHRASES[language][category]
        unused = [phrase for phrase in pool if (language, category, phrase) not in self.used_wild_suggestions]
        choices = unused or [phrase for phrase in pool if phrase != self.last.get((language, category))] or list(pool)
        value = self.rng.choice(choices)
        self.used_wild_suggestions.add((language, category, value))
        self.last[language, category] = value
        return value


def clean_answer(value):
    value = value.strip()
    if not value or len(value) > MAX_INPUT_LENGTH or not any(char.isalnum() for char in value) or any(ord(char) < 32 for char in value):
        raise ValueError('请填写每一项，使用 1–100 字的词或短语。')
    return value


def fit_answer(slot, answer, following_slot=None, following_answer=''):
    """Small, transparent repairs; never rewrite the rest of the article."""
    value = clean_answer(answer)
    english = bool(re.search('[A-Za-z]', value)) and not re.search('[\u4e00-\u9fff]', value)
    if slot.category == 'place':
        if english and slot.prefix and not re.match(r'(?:on|in|at|inside|under|near|to|from|outside)\b', value, re.I):
            value = (slot.prefix if slot.prefix.isascii() else 'in') + ' ' + value
        elif not english and slot.prefix and not value.startswith(('在', '到', '从')):
            value = '在' + value
    if slot.category == 'action' and english and re.match(r'[A-Za-z]+ing\b', value):
        auxiliary = {'base': 'start ', 'past': 'started ', 'present': 'keeps ', 'gerund': ''}.get(slot.form, '')
        connector = slot.connector
        if following_slot and following_slot.category == 'place':
            connector = '' if following_slot.prefix or re.match(r'(?:on|in|at|inside|under|near|to|from|outside)\b', following_answer, re.I) else ' in'
        value = auxiliary + value + connector
    if slot.sentence_start and english:
        value = value[:1].upper() + value[1:]
    return value

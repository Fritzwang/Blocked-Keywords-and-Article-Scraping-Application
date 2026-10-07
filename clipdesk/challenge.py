"""Offline, temporary text puzzles. No Article or database mutation."""
from dataclasses import dataclass, field
import random
import re

STOP_WORDS = frozenset('''the a an of and is are to in on at for from with by as
it its this that these those be been being was were has have had do does did
not but or if then than so into out up down can could would should will may
might must we you they he she them his her our their who which what when
where why how all any some each every very also only just more most much
such there here about after before because through over under again'''.split())

# Conservative longest-match vocabulary, with short standalone unknown phrases
# as a fallback. This is intentionally not a general-purpose Chinese segmenter.
ZH_WORDS = frozenset('''森林 城市 河流 河水 河岸 土地 天空 海洋 自然 环境 生态
保护 恢复 生长 植物 动物 树木 花朵 草地 阳光 空气 水源 雨水 土壤
阅读 空间 开放 居民 提供 安静 舒适 设置 图书 阅览 交流 儿童 活动
方便 年龄 读者 使用 工作人员 介绍 场馆 定期 举办 读书 文化 讲座
通过 公开 渠道 了解 安排 时间 报名 参加 阶段 持续 收集 意见
完善 设施 服务 更多 享受 便利 公共 资源 今天 明天 昨天 世界 中国
科学 技术 研究 学习 学生 学校 教育 知识 文章 正文 标题 内容 信息
数据 网络 系统 软件 程序 开发 测试 保存 修改 删除 文本 规则
人工 智能 太阳 核心 部件 批量 交付 紧凑型 聚变能 实验 装置
燃烧 等离子体 超导 托卡马克 线圈 完工 发运 仪式 集团 公司
股份 有限 德阳 基地 举行 研制 全部 完成 制造 总装 顺利 可控
核聚变 人类 终极 能源 原理 模拟 内部 反应 科学院 物理 主导
设计 承建 项目 建设 发展 经济 社会 生活 健康 医疗 安全 食物
农业 工业 生产 产品 市场 企业 新闻 新闻报道 报道 记者 发现
问题 方法 结果 重要 成功 未来 故事 朋友 家庭 孩子 再生 挑战
慢慢 逐渐 回到 返回 存活 破坏 损坏'''.split())
ZH_STOP = frozenset('的了和是在与及或把被将让向从到为以于也都就而着过吗呢啊地得')
LEXEMES = re.compile(r"(?<!\w)[A-Za-z]+(?:['’-][A-Za-z]+)*(?!\w)|[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class Token:
    start: int
    end: int
    word: str


def tokens(text):
    """Return eligible whole-token spans; never perform substring substitution."""
    found = []
    for match in LEXEMES.finditer(text):
        value = match.group()
        if value.isascii() or value[0].isascii():
            word = value.casefold()
            if len(word) >= 3 and word not in STOP_WORDS:
                found.append(Token(match.start(), match.end(), word))
            continue
        index = 0
        while index < len(value):
            if value[index] in ZH_STOP:
                index += 1
                continue
            known = next((value[index:index + size] for size in range(5, 1, -1)
                          if value[index:index + size] in ZH_WORDS), None)
            if known:
                end = index + len(known)
            else:
                end = index + 1
                while end < len(value) and value[end] not in ZH_STOP and not any(
                        value[end:end + size] in ZH_WORDS for size in range(5, 1, -1)):
                    end += 1
            word = value[index:end]
            if known or 2 <= len(word) <= 4:
                found.append(Token(match.start() + index, match.start() + end, word))
            index = end
    return found


def candidate_words(text):
    return list(dict.fromkeys(token.word for token in tokens(text)))


def answer_matches(answer, target):
    return answer.strip().casefold() == target.casefold()


@dataclass
class Challenge:
    source: str
    targets: tuple[str, ...]
    spans: tuple[Token, ...]
    results: list[str] = field(default_factory=list)
    revealed: bool = False

    @classmethod
    def create(cls, source, previous=(), rng=None, targets=None):
        rng = rng or random.SystemRandom()
        spans = tuple(tokens(source))
        candidates = list(dict.fromkeys(span.word for span in spans))
        if targets is None:
            selected = rng.sample(candidates, min(5, len(candidates)))
            if set(selected) == set(previous) and len(candidates) > len(selected):
                selected[-1] = rng.choice([word for word in candidates if word not in selected])
        else:
            selected = list(dict.fromkeys(word.casefold() for word in targets))[:5]
            if not set(selected) <= set(candidates):
                raise ValueError('Targets must be complete eligible tokens from the source.')
        # Inputs follow the order of first appearance in the article.
        selected = tuple(word for word in candidates if word in selected)
        return cls(source, selected, spans, ['pending'] * len(selected))

    def test(self, answers):
        if not self.revealed:
            self.results = [
                'unanswered' if not answer.strip() else
                'correct' if answer_matches(answer, target) else 'incorrect'
                for target, answer in zip(self.targets, list(answers) + [''] * len(self.targets))
            ]
        return self.results.copy()

    @property
    def score(self):
        return self.results.count('correct')

    def reveal(self):
        self.revealed = True

    @property
    def revealed_count(self):
        return len(self.targets) - self.score if self.revealed else 0

    @property
    def restoration(self):
        total = len(self.targets)
        return round(100 * (self.score + self.revealed_count) / total) if total else 100

    def hidden_spans(self):
        hidden = {word for word, result in zip(self.targets, self.results)
                  if result != 'correct' and not self.revealed}
        return [span for span in self.spans if span.word in hidden]

    def render(self):
        pieces, cursor = [], 0
        for span in self.hidden_spans():
            pieces.extend((self.source[cursor:span.start], '*****'))
            cursor = span.end
        pieces.append(self.source[cursor:])
        return ''.join(pieces)

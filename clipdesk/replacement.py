"""批量替换扩展入口：规则顺序执行，仅修改标题和正文，不修改原文。"""
from dataclasses import dataclass, replace
import re

from .models import Article


@dataclass(frozen=True)
class Rule:
    find: str
    replacement: str = ""
    scope: str = "both"
    case_sensitive: bool = True

    def __post_init__(self):
        if not isinstance(self.find, str) or not self.find:
            raise ValueError("查找内容不能为空。")
        if not isinstance(self.replacement, str):
            raise ValueError("替换内容必须是文本。")
        if self.scope not in ("both", "title", "body"):
            raise ValueError("规则范围必须是 both、title 或 body。")
        if not isinstance(self.case_sensitive, bool):
            raise ValueError("case_sensitive 必须为 true 或 false。")


@dataclass
class Change:
    before: Article
    after: Article
    matches: int


def preview(articles: list[Article], rules: list[Rule]) -> list[Change]:
    changes = []
    for article in articles:
        updated = replace(article)
        matches = 0
        for rule in rules:
            pattern = re.compile(re.escape(rule.find), 0 if rule.case_sensitive else re.IGNORECASE)
            for field in ("title", "body"):
                if rule.scope in ("both", field):
                    value, count = pattern.subn(lambda _: rule.replacement, getattr(updated, field))
                    setattr(updated, field, value)
                    matches += count
        if (article.title, article.body) != (updated.title, updated.body):
            changes.append(Change(article, updated, matches))
    return changes

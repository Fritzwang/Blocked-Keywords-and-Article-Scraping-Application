from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass
class Article:
    title: str
    body: str
    url: str = ""
    author: str = ""
    published: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created: str = field(default_factory=now)
    updated: str = field(default_factory=now)
    original_title: str = ""
    original_body: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

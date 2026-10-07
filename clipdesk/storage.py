import json
import sqlite3
from pathlib import Path

from .models import Article, now
from .replacement import Change


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL)")
        self.db.commit()

    def _write(self, article: Article):
        self.db.execute("INSERT OR REPLACE INTO articles VALUES (?, ?, ?)", (article.id, json.dumps(article.to_dict(), ensure_ascii=False), article.updated))

    def save(self, article: Article):
        article.updated = now()
        with self.db:
            self._write(article)

    def get(self, article_id: str) -> Article | None:
        row = self.db.execute("SELECT payload FROM articles WHERE id=?", (article_id,)).fetchone()
        return Article(**json.loads(row[0])) if row else None

    def all(self) -> list[Article]:
        return [Article(**json.loads(row[0])) for row in self.db.execute("SELECT payload FROM articles ORDER BY updated DESC")]

    def delete(self, article_id: str):
        with self.db:
            self.db.execute("DELETE FROM articles WHERE id=?", (article_id,))

    def delete_all(self):
        # Article snapshots in undo history must not retain deleted drafts.
        # Both statements commit or roll back together.
        with self.db:
            self.db.execute("DELETE FROM articles")
            self.db.execute("DELETE FROM history")

    def apply(self, changes: list[Change]):
        if not changes:
            return
        with self.db:
            # 预览后若数据变化，不覆盖用户的新编辑。
            for change in changes:
                current = self.get(change.before.id)
                if not current or current.to_dict() != change.before.to_dict():
                    raise ValueError("预览后文章已发生变化，请重新预览。")
            snapshot = []
            for change in changes:
                change.after.updated = now()
                self._write(change.after)
                snapshot.append({"before": change.before.to_dict(), "after": change.after.to_dict()})
            self.db.execute("INSERT INTO history (payload) VALUES (?)", (json.dumps(snapshot, ensure_ascii=False),))

    def undo_batch(self) -> int:
        row = self.db.execute("SELECT id, payload FROM history ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return 0
        snapshot = json.loads(row[1])
        with self.db:
            for item in snapshot:
                current = self.get(item["after"]["id"])
                if not current or (current.title, current.body) != (item["after"]["title"], item["after"]["body"]):
                    raise ValueError("替换后有文章被再次编辑或删除。为保留这些修改，无法直接撤销；可查看原始内容或先恢复替换后的文字。")
            for item in snapshot:
                restored = self.get(item["before"]["id"])
                restored.title, restored.body = item["before"]["title"], item["before"]["body"]
                restored.updated = now()
                self._write(restored)
            self.db.execute("DELETE FROM history WHERE id=?", (row[0],))
        return len(snapshot)

    def close(self):
        self.db.close()

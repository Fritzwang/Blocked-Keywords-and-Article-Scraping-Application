from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests

from clipdesk.diagnostics import SAMPLE_HTML
from clipdesk.extractor import ExtractionError, decode_html, download_html, extract_html, normalize_url
from clipdesk.models import Article
from clipdesk.replacement import Rule, preview
from clipdesk.storage import Store


class ExtractionTests(unittest.TestCase):
    def test_normalize_and_reject_invalid_urls(self):
        self.assertEqual(normalize_url(" example.com/story?q=1#part "), "https://example.com/story?q=1")
        for value in ("", "file:///C:/file.txt", "javascript:alert(1)", "http://", "https://user:pass@example.com", "https://example.com:bad", "bad host.com"):
            with self.subTest(value=value), self.assertRaises(ExtractionError):
                normalize_url(value)

    def test_chinese_encoding(self):
        page = '<meta charset="gb2312"><h1>中文新闻与正文</h1>'
        self.assertIn("中文新闻", decode_html(page.encode("gb18030"), "text/html; charset=gb2312"))
        self.assertIn("中文新闻", decode_html(page.encode("gb18030")))
        self.assertIn("城市阅读空间", decode_html(SAMPLE_HTML.encode("utf-8")))

    def test_article_excludes_navigation_and_scripts(self):
        article = extract_html(SAMPLE_HTML + "<script>alert('恶意脚本')</script>", "https://example.com/story")
        self.assertEqual(article.title, "城市阅读空间开放")
        self.assertIn("完善设施与服务", article.body)
        self.assertNotIn("导航中心", article.body)
        self.assertNotIn("恶意脚本", article.body)
        self.assertEqual(article.body.count("工作人员介绍"), 1)
        self.assertEqual(article.original_body, article.body)

    def test_og_title_and_short_chinese_template(self):
        page = '<head><title>站点</title><meta property="og:title" content="真实文章标题"></head><div id="js_content"><p>这是一篇简短的文章内容，用于测试中文模板提取，确保短文也能正确进入本地编辑器中。</p></div>'
        article = extract_html(page, "https://example.com")
        self.assertEqual(article.title, "真实文章标题")
        self.assertIn("本地编辑器", article.body)

    def test_no_body_and_challenge_do_not_save_garbage(self):
        for page in ("<h1>空页面</h1><script>dynamic()</script>", "<title>Just a moment...</title><p>Checking your browser before accessing</p>"):
            with self.subTest(page=page), self.assertRaises(ExtractionError):
                extract_html(page, "https://example.com")

    @staticmethod
    def response(code=200, kind="text/html", chunks=None, location=None):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status_code = code
        response.is_redirect = code in (301, 302, 303, 307, 308)
        response.is_permanent_redirect = code in (301, 308)
        response.headers = {"Content-Type": kind}
        if location:
            response.headers["Location"] = location
        response.iter_content.return_value = iter(chunks or [SAMPLE_HTML.encode("utf-8")])
        return response

    def test_download_redirects_and_charset(self):
        with patch("clipdesk.extractor.requests.Session") as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = [self.response(302, location="/final"), self.response()]
            html, url = download_html("https://example.com/start")
            self.assertEqual(url, "https://example.com/final")
            self.assertIn("城市阅读空间", html)

    def test_download_rejects_status_binary_and_oversize(self):
        for response in (self.response(403), self.response(429), self.response(kind="application/pdf"), self.response(chunks=[b"x" * 32])):
            with self.subTest(response=response), patch("clipdesk.extractor.requests.Session") as session, patch("clipdesk.extractor.MAX_BYTES", 16):
                session.return_value.__enter__.return_value.get.return_value = response
                with self.assertRaises(ExtractionError):
                    download_html("https://example.com")

    def test_connection_failure_is_readable(self):
        with patch("clipdesk.extractor.requests.Session") as session:
            session.return_value.__enter__.return_value.get.side_effect = requests.ConnectionError("test")
            with self.assertRaisesRegex(ExtractionError, "无法连接"):
                download_html("https://example.com")


class ReplacementTests(unittest.TestCase):
    def test_literals_scope_case_and_order(self):
        article = Article(title="A.B a.b", body="A.B 原词", original_body="A.B 原词")
        changes = preview([article], [Rule("a.b", r"\1", "title", False), Rule("原词", "中间"), Rule("中间", "最终")])
        self.assertEqual(changes[0].after.title, r"\1 \1")
        self.assertEqual(changes[0].after.body, "A.B 最终")
        self.assertEqual(changes[0].after.original_body, "A.B 原词")
        self.assertEqual(article.body, "A.B 原词")
        self.assertEqual(changes[0].matches, 4)

    def test_empty_replacement_and_noop(self):
        article = Article(title="标题", body="正文广告")
        self.assertEqual(preview([article], [Rule("广告", "")])[0].after.body, "正文")
        self.assertEqual(preview([article], [Rule("正文", "正文")]), [])
        with self.assertRaises(ValueError):
            Rule("")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "articles.db"
        self.store = Store(self.path)
        self.article = Article(title="原始标题", body="原始正文", original_body="原始正文")
        self.store.save(self.article)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_roundtrip_and_persistent_batch_undo(self):
        self.store.apply(preview(self.store.all(), [Rule("原始", "修改")]))
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.get(self.article.id).body, "修改正文")
        self.assertEqual(self.store.undo_batch(), 1)
        self.assertEqual(self.store.get(self.article.id).body, "原始正文")
        self.assertEqual(self.store.get(self.article.id).original_body, "原始正文")
        self.assertEqual(self.store.undo_batch(), 0)

    def test_stale_preview_does_not_overwrite_edit(self):
        changes = preview(self.store.all(), [Rule("原始", "修改")])
        article = self.store.get(self.article.id)
        article.title = "用户的新编辑"
        self.store.save(article)
        with self.assertRaises(ValueError):
            self.store.apply(changes)
        self.assertEqual(self.store.get(article.id).title, "用户的新编辑")

    def test_batch_transaction_and_conflicting_undo(self):
        second = replace(self.article, id="second", title="原始标题二")
        self.store.save(second)
        changes = preview(self.store.all(), [Rule("原始", "修改")])
        self.store.apply(changes)
        edited = self.store.get(self.article.id)
        edited.body = "后续修改"
        self.store.save(edited)
        with self.assertRaises(ValueError):
            self.store.undo_batch()
        self.assertEqual(self.store.get(second.id).title, "修改标题二")
        self.assertEqual(self.store.get(edited.id).body, "后续修改")


if __name__ == "__main__":
    unittest.main()

"""下载和正文提取独立于界面，后续可添加站点适配器。"""
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit

import requests
import trafilatura
from bs4 import BeautifulSoup, UnicodeDammit
from lxml.etree import LxmlError

from .models import Article

MAX_BYTES = 8 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


class ExtractionError(ValueError):
    pass


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ExtractionError("请先输入网页地址。")
    if re.search(r"\s", value):
        raise ExtractionError("网址中不能包含空格或换行。")
    if not re.match(r"^[a-zA-Z][a-zA-Z\d+.-]*:", value):
        value = "https://" + value
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in ("http", "https"):
            raise ExtractionError("只支持 http:// 和 https:// 网页地址。")
        if not parts.hostname or parts.username or parts.password:
            raise ExtractionError("请输入完整的网址，不要在网址中附带账号密码。")
        _ = parts.port
        return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", parts.query, ""))
    except ValueError as exc:
        if isinstance(exc, ExtractionError):
            raise
        raise ExtractionError("网址格式不正确，请检查域名和端口。") from exc


def decode_html(data: bytes, content_type: str = "") -> str:
    match = re.search(r"charset\s*=\s*[\"']?([\w.-]+)", content_type, re.I)
    if match:
        encoding = match.group(1).lower()
        if encoding in ("gb2312", "gbk", "gb_2312-80"):
            encoding = "gb18030"
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeError):
            pass
    # HTTP 的默认 latin-1 不是网页实际编码；优先检查 BOM 和 HTML meta。
    decoded = UnicodeDammit(data, is_html=True)
    return decoded.unicode_markup or data.decode("utf-8", errors="replace")


def download_html(url: str) -> tuple[str, str]:
    current = normalize_url(url)
    started = time.monotonic()
    try:
        with requests.Session() as session:
            session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"})
            for _ in range(6):
                with session.get(current, timeout=(8, 12), stream=True, allow_redirects=False) as response:
                    if response.is_redirect or response.is_permanent_redirect:
                        from urllib.parse import urljoin
                        current = normalize_url(urljoin(current, response.headers.get("Location", "")))
                        continue
                    if response.status_code in (401, 403):
                        raise ExtractionError(f"网站拒绝访问（HTTP {response.status_code}），可能需要登录或人机验证。")
                    if response.status_code == 429:
                        raise ExtractionError("网站暂时限制访问频率，请稍后再试。")
                    response.raise_for_status()
                    kind = response.headers.get("Content-Type", "").lower()
                    if kind and not any(t in kind for t in ("text/html", "application/xhtml+xml", "text/plain")):
                        raise ExtractionError("该地址返回的不是 HTML 网页。请使用文章页面的网址。")
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ExtractionError("网页超过 8 MB，请换用该文章的简洁版页面。")
                        if time.monotonic() - started > 40:
                            raise ExtractionError("网页下载耗时过长，请稍后重试。")
                        chunks.append(chunk)
                    return decode_html(b"".join(chunks), kind), current
            raise ExtractionError("网页重定向次数过多，请检查网址。")
    except requests.exceptions.SSLError as exc:
        raise ExtractionError("网站的 HTTPS 证书验证失败，请检查网址和电脑时间。") from exc
    except requests.exceptions.Timeout as exc:
        raise ExtractionError("连接或读取网页超时，请稍后重试。") from exc
    except requests.exceptions.HTTPError as exc:
        raise ExtractionError(f"网页访问失败（HTTP {exc.response.status_code}）。") from exc
    except requests.exceptions.RequestException as exc:
        raise ExtractionError("无法连接网站，请检查网络、网址或系统代理设置。") from exc


def clean_text(value: str) -> str:
    lines = [re.sub(r"[\t \u00a0\u3000]+", " ", line).strip() for line in value.splitlines()]
    return "\n\n".join(line for line in lines if line)


def remove_extraction_duplicates(body: str, source: BeautifulSoup) -> str:
    """消除提取器额外产生的重复段落，保留原页面确实重复的文字。"""
    visible = re.sub(r"\s+", " ", source.get_text(" ", strip=True))
    seen = {}
    paragraphs = []
    for paragraph in body.split("\n\n"):
        key = re.sub(r"\s+", " ", paragraph).strip()
        seen[key] = seen.get(key, 0) + 1
        if len(key) >= 30 and seen[key] > max(1, visible.count(key)):
            continue
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def extract_html(html: str, url: str) -> Article:
    soup = BeautifulSoup(html, "lxml")
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if re.search(r"^(just a moment|access denied|attention required|security verification)", page_title, re.I):
        raise ExtractionError("网站返回了访问验证页面，无法取得正文。")
    metadata = {}
    try:
        result = trafilatura.extract(html, url=url, output_format="json", with_metadata=True, include_comments=False, include_tables=True, deduplicate=False)
        if result:
            metadata = json.loads(result)
    except (ValueError, TypeError, LxmlError):
        # 个别损坏的网页仍可交给结构化选择器处理。
        metadata = {}
    title_node = soup.select_one('meta[property="og:title"], meta[name="twitter:title"]')
    heading = soup.find("h1")
    title = (title_node.get("content", "") if title_node else "") or (heading.get_text(" ", strip=True) if heading else "") or metadata.get("title") or page_title
    body = clean_text(metadata.get("text") or "")

    # 为常见中文新闻模板和短文提供后备提取，不抓取脚本、导航或表单。
    for tag in soup.select("script, style, noscript, nav, header, footer, aside, form, iframe, button, [hidden], [aria-hidden='true']"):
        tag.decompose()
    if len(body) < 60:
        selectors = ("#js_content", "[itemprop='articleBody']", ".TRS_Editor", ".article-content", ".article_content", ".article-body", "#article", "#content", "article", "main")
        candidates = []
        for selector in selectors:
            for node in soup.select(selector):
                text = clean_text(node.get_text("\n", strip=True))
                link_length = sum(len(a.get_text(strip=True)) for a in node.find_all("a"))
                if text and link_length / len(text) < 0.45:
                    candidates.append(text)
        if not candidates:
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 20 and not p.find_parent(["nav", "footer"])]
            candidates = [clean_text("\n".join(paragraphs))]
        fallback = max(candidates, key=len, default="")
        if len(fallback) > len(body):
            body = fallback
    body = remove_extraction_duplicates(body, soup)
    title = re.sub(r"\s+", " ", title).strip() or "未命名文章"
    # 避免正文再出现与标题完全相同的首段。
    if body.split("\n\n", 1)[0].strip() == title:
        body = body.partition("\n\n")[2]
    if len(body.strip()) < 30:
        raise ExtractionError("没有找到可用正文。请确认这是文章详情页；需要登录、验证码或 JavaScript 动态加载的页面可能无法直接提取。")
    return Article(title=title, body=body, url=url, author=metadata.get("author") or "", published=metadata.get("date") or "", original_title=title, original_body=body)


def fetch_article(url: str) -> Article:
    html, final_url = download_html(url)
    return extract_html(html, final_url)

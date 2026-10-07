"""Visible smoke-test app using a separate D-drive test database."""
import sys
from pathlib import Path
import tkinter as tk

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from clipdesk.ui import App
from clipdesk.models import Article

root = tk.Tk()
app = App(root, PROJECT / 'work' / 'mode3-smoke-data')
if '--live' in sys.argv:
    from clipdesk.extractor import fetch_article
    fetched = fetch_article('https://www.python.org/doc/essays/blurb/')
    # Real opening sentence, labeled as an excerpt, for a compact live demo.
    sentence = next(line for line in fetched.body.splitlines() if line.startswith('Python is ')).split('. ')[0] + '.'
    demo = Article(title='What is Python? — real article excerpt', body=sentence,
                   url=fetched.url, original_title=fetched.title, original_body=sentence)
    app.store.save(demo)
if not app.store.all():
    for title, body in [
        ('English smoke test', 'The forest slowly recovered after the fire. Forest rivers surrounded the ancient city. The forest returned to the quiet garden.'),
        ('中文验收文稿', '森林慢慢恢复，森林保护河流。城市的居民来到安静的阅读空间，图书和文化活动让生活更加美好。'),
    ]:
        app.store.save(Article(title=title, body=body))
app.show_article(demo if '--live' in sys.argv else next(a for a in app.store.all() if a.title == 'English smoke test'))
root.mainloop()

"""Stage one temporary article for the final EXE; preserve all existing rows."""
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from clipdesk.models import Article
from clipdesk.storage import Store

MANIFEST = PROJECT / 'work' / 'exe-gui-fixture.json'
BODY = 'Python is an interpreted, object-oriented, high-level programming language with dynamic semantics.'


def fingerprint(articles):
    return {a.id: hashlib.sha256(json.dumps(a.to_dict(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            for a in articles}


store = Store(PROJECT / 'data' / 'articles.db')
try:
    if sys.argv[1] == 'stage':
        if MANIFEST.exists() and not json.loads(MANIFEST.read_text(encoding='utf-8')).get('cleaned'):
            raise RuntimeError('A fixture manifest already exists; clean it up before staging.')
        before = fingerprint(store.all())
        article = Article(title='GUI smoke test — real article excerpt', body=BODY,
                          url='https://www.python.org/doc/essays/blurb/',
                          original_title='What is Python? Executive Summary', original_body=BODY)
        store.save(article)
        MANIFEST.write_text(json.dumps({'id': article.id, 'title': article.title, 'body': BODY,
                                       'baseline': before}, indent=2), encoding='utf-8')
        print(f'Staged one temporary article; preserved {len(before)} existing articles.')
    elif sys.argv[1] == 'cleanup':
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        others = [a for a in store.all() if a.id != manifest['id']]
        if fingerprint(others) != manifest['baseline']:
            raise RuntimeError('Existing article data changed; leave the fixture for inspection.')
        article = store.get(manifest['id'])
        if article and (article.title != manifest['title'] or article.body != manifest['body']):
            raise RuntimeError('Fixture was edited; do not remove it automatically.')
        store.delete(manifest['id'])
        assert fingerprint(store.all()) == manifest['baseline']
        manifest['cleaned'] = True
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(f'Cleaned temporary article; {len(others)} existing articles unchanged.')
    else:
        raise ValueError('Use stage or cleanup.')
finally:
    store.close()

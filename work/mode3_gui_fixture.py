"""Stage one public article for final EXE clicks; verify all user rows on cleanup."""
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from clipdesk.models import Article
from clipdesk.storage import Store

manifest_path = PROJECT / 'work/mode3-gui-fixture.json'


def fingerprint(articles):
    return {a.id: hashlib.sha256(json.dumps(a.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            for a in articles}


store = Store(PROJECT / 'data/articles.db')
try:
    if sys.argv[1] == 'stage':
        if manifest_path.exists() and not json.loads(manifest_path.read_text(encoding='utf-8')).get('cleaned'):
            raise RuntimeError('Clean the existing test fixture first.')
        before = fingerprint(store.all())
        source = json.loads((PROJECT / 'work/mode4-real-article.json').read_text(encoding='utf-8'))
        article = Article(title='Mode 3 Blind Mad Libs — What is Python?', body=source['body'],
                          url=source['url'], original_title=source['title'], original_body=source['body'])
        store.save(article)
        manifest_path.write_text(json.dumps({'baseline': before, 'fixture': article.to_dict(), 'cleaned': False},
                                            ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Staged public article; {len(before)} existing rows preserved.')
    elif sys.argv[1] == 'cleanup':
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        fixture = manifest['fixture']
        assert fingerprint([a for a in store.all() if a.id != fixture['id']]) == manifest['baseline']
        current = store.get(fixture['id'])
        assert current and current.to_dict() == fixture, 'Test article changed; preserve for inspection.'
        store.delete(fixture['id'])
        assert fingerprint(store.all()) == manifest['baseline']
        manifest['cleaned'] = True
        manifest['all_existing_rows_unchanged'] = True
        manifest['fixture_body_unchanged'] = True
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Fixture removed; {len(manifest["baseline"])} existing rows unchanged.')
    else:
        raise ValueError('Use stage or cleanup.')
finally:
    store.close()

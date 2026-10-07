"""Fetch/stage/clean a real-article fixture; preserve every other stored row."""
import hashlib
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from clipdesk.extractor import fetch_article
from clipdesk.models import Article
from clipdesk.storage import Store
from clipdesk.reframe import ReframeSession

SOURCE = PROJECT / 'work' / 'mode4-real-article.json'
MANIFEST = PROJECT / 'work' / 'mode4-gui-fixture.json'


def fingerprint(articles):
    return {article.id: hashlib.sha256(json.dumps(article.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            for article in articles}


if sys.argv[1] == 'fetch':
    article = fetch_article('https://www.python.org/doc/essays/blurb/')
    SOURCE.write_text(json.dumps(article.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
    session = ReframeSession(article.body)
    print(json.dumps({'title': article.title, 'characters': len(article.body), 'sections': len(session.sections),
                      'fragment_counts': [len(session._orders[section.id]) for section in session.sections]}, ensure_ascii=False))
else:
    store = Store(PROJECT / 'data' / 'articles.db')
    try:
        if sys.argv[1] == 'stage':
            if MANIFEST.exists() and not json.loads(MANIFEST.read_text(encoding='utf-8')).get('cleaned'):
                raise RuntimeError('Clean the active Mode 4 fixture first.')
            baseline = fingerprint(store.all())
            source = json.loads(SOURCE.read_text(encoding='utf-8'))
            article = Article(title='Mode 4 GUI verification — What is Python?', body=source['body'], url=source['url'],
                              original_title=source['title'], original_body=source['body'])
            store.save(article)
            MANIFEST.write_text(json.dumps({'id': article.id, 'title': article.title, 'body': article.body,
                                           'baseline': baseline}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'Staged real article; {len(baseline)} existing articles preserved.')
        elif sys.argv[1] == 'cleanup':
            manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
            others = [article for article in store.all() if article.id != manifest['id']]
            if fingerprint(others) != manifest['baseline']:
                raise RuntimeError('Existing rows changed; do not remove the fixture automatically.')
            article = store.get(manifest['id'])
            if article and (article.title != manifest['title'] or article.body != manifest['body']):
                raise RuntimeError('Fixture content was edited; preserve it for inspection.')
            store.delete(manifest['id'])
            assert fingerprint(store.all()) == manifest['baseline']
            manifest['cleaned'] = True
            MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'Cleaned fixture; {len(others)} existing rows unchanged.')
        elif sys.argv[1] == 'cleanup-old':
            # The previous helper rejected an extra, later-created user row.
            # Verify every baseline row, retain extra rows, remove only its
            # identified unchanged fixture, then verify all remaining rows.
            mode4 = json.loads(MANIFEST.read_text(encoding='utf-8'))
            before = fingerprint(store.all())
            if not mode4.get('cleaned') or before != mode4['baseline']:
                raise RuntimeError('Finish Mode 4 cleanup and verify its baseline first.')
            old_path = PROJECT / 'work' / 'exe-gui-fixture.json'
            old = json.loads(old_path.read_text(encoding='utf-8'))
            if not all(before.get(key) == value for key, value in old['baseline'].items()):
                raise RuntimeError('Previous baseline rows changed; preserve the old fixture.')
            article = store.get(old['id'])
            if not article or (article.title, article.body, article.original_body) != (old['title'], old['body'], old['body']):
                raise RuntimeError('Previous fixture changed or missing; preserve it.')
            expected = {key: value for key, value in before.items() if key != old['id']}
            store.delete(old['id'])
            after = fingerprint(store.all())
            assert after == expected
            old['cleaned'] = True
            old_path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding='utf-8')
            audit = {'mode4_fixture_cleaned': True, 'four_existing_rows_unchanged_after_mode4': True,
                     'old_fixture_cleaned': True, 'remaining_rows': len(after),
                     'all_remaining_rows_unchanged': True, 'fingerprints': after}
            (PROJECT / 'work' / 'mode4-data-verification.json').write_text(
                json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'Cleaned old unchanged fixture; {len(after)} genuine articles unchanged, including the later-created article.')
        else:
            raise ValueError('Use fetch, stage, cleanup or cleanup-old.')
    finally:
        store.close()

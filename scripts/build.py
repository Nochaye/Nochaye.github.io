"""Validate the catalog and prepare a static-only Pages artifact."""
import json
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def validate(root=ROOT):
    for name in ['articles', 'links']:
        rows = json.loads((root / 'data' / (name + '.json')).read_text(encoding='utf-8'))
        ids = set()
        for row in rows:
            assert re.fullmatch(r'[a-zA-Z0-9_-]+', row['id']), 'Invalid ID'
            assert row['id'] not in ids, 'Duplicate ID'
            ids.add(row['id'])
            assert row['title'].strip(), 'Missing title'
            if name == 'articles':
                assert re.fullmatch(r'readings/[a-zA-Z0-9_-]+\.html', row['path'])
                for key in ['edition', 'updated']:
                    date.fromisoformat(row[key])
                assert (root / row['path']).is_file(), 'Missing HTML'
                html = (root / row['path']).read_text(encoding='utf-8')
                assert '<html' in html.lower() and '</html>' in html.lower(), 'Incomplete HTML'
                assert '{{TITLE}}' not in html and '{{CONTENT}}' not in html, 'Unfilled template'
            else:
                url = urlsplit(row['url'])
                assert url.scheme in ('http', 'https') or (not url.scheme and (root / row['url']).is_file()), 'Invalid website link'
    print('Catalog, dates, HTML files and navigation links verified.')


def build(root=ROOT):
    validate(root)
    dest = root / 'dist'
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()
    for name in ['index.html', 'reader.html', 'admin.html', 'style.css', 'text.html', 'text.js', 'linux_command.html', 'computer_construction.html', ' javascriptest.html', 'background.png']:
        shutil.copy2(root / name, dest / name)
    for name in ['assets', 'data', 'readings']:
        shutil.copytree(root / name, dest / name)
    (dest / '.nojekyll').touch()
    print('Static build ready: dist/ (no server code, credentials or backups).')


if __name__ == '__main__':
    build()

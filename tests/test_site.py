import http.client
import importlib.util
import json
import shutil
import tempfile
import threading
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('starcape_server', ROOT / 'scripts/server.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EditorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        (self.root / 'readings').mkdir()
        (self.root / 'data/articles.json').write_text('[]')
        (self.root / 'data/links.json').write_text('[]')
        (self.root / 'index.html').write_text('<html>Test</html>')
        self.catalog = module.Catalog(self.root)
        self.body = dict(title='测试精读', description='说明', edition='2026-11-08', updated='2026-11-11', published='2026-11-07', source='https://example.com/', html='<!doctype html><html><body>Study</body></html>')

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_edit_replace_delete_and_backup(self):
        identifier = self.catalog.save_article(self.body)['id']
        row = self.catalog.read('articles')[0]
        path = self.root / row['path']
        self.assertTrue(path.exists())
        edit = dict(self.body, id=identifier, title='新标题')
        edit.pop('html')
        self.catalog.save_article(edit)
        self.assertEqual(path.read_text(), self.body['html'])
        self.assertEqual(self.catalog.read('articles')[0]['title'], '新标题')
        self.catalog.save_article(dict(edit, html='<html>Replacement</html>'))
        self.assertIn('Replacement', path.read_text())
        self.catalog.delete_article({'id': identifier})
        self.assertEqual(self.catalog.read('articles'), [])
        self.assertFalse(path.exists())
        self.assertTrue(list((self.root / '.runtime/trash').glob('*.html')))

    def test_invalid_id_date_and_url_leave_catalog_unchanged(self):
        for change in [dict(id='../index'), dict(updated='2026-02-31'), dict(source='javascript:alert(1)'), dict(source='https://secret:password@example.com/')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.catalog.save_article(dict(self.body, **change))
        self.assertEqual(self.catalog.read('articles'), [])
        self.assertEqual(list((self.root / 'readings').iterdir()), [])

    def test_html_required_and_size_limit(self):
        body = dict(self.body)
        body.pop('html')
        with self.assertRaises(ValueError):
            self.catalog.save_article(body)
        with self.assertRaises(ValueError):
            self.catalog.save_article(dict(body, html='<html>' + 'x' * module.MAX_HTML))

    def test_corrupted_catalog_path_is_rejected(self):
        identifier = self.catalog.save_article(self.body)['id']
        rows = self.catalog.read('articles')
        rows[0]['path'] = '../index.html'
        self.catalog.write('articles', rows)
        with self.assertRaises(ValueError):
            self.catalog.delete_article({'id': identifier})
        self.assertTrue((self.root / 'index.html').exists())

    def test_symlink_cannot_replace_outside_file(self):
        identifier = self.catalog.save_article(self.body)['id']
        row = self.catalog.read('articles')[0]
        path = self.root / row['path']
        path.unlink()
        path.symlink_to(self.root / 'index.html')
        with self.assertRaises(ValueError):
            self.catalog.save_article(dict(self.body, id=identifier))
        self.assertEqual((self.root / 'index.html').read_text(), '<html>Test</html>')

    def test_bookmarks_deduplicate_and_reject_unsafe_protocols(self):
        entry = dict(url='https://example.com/', title='Example')
        result = self.catalog.import_links({'links': [entry, entry]})
        self.assertEqual(result['added'], 1)
        with self.assertRaises(ValueError):
            self.catalog.import_links({'links': [dict(url='file:///private', title='No')]})
        self.assertEqual(len(self.catalog.read('links')), 1)

    def test_http_auth_origin_hidden_files_and_save(self):
        server = module.make_server(self.root, 0, token='test-secret')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_port
        def request(method, path, body=None, headers=None):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            conn.request(method, path, json.dumps(body) if body else None, headers or {})
            res = conn.getresponse()
            data = res.read()
            conn.close()
            return res.status, data
        try:
            self.assertEqual(request('GET', '/api/status')[0], 403)
            self.assertEqual(request('GET', '/api/status', headers={'X-Starcape-Token': 'test-secret'})[0], 200)
            self.assertEqual(request('GET', '/.git/config')[0], 404)
            self.assertEqual(request('GET', '/%2e%2e/index.html')[0], 404)
            self.assertEqual(request('GET', '/', headers={'Host': 'attacker.test'})[0], 403)
            headers = {'X-Starcape-Token': 'test-secret', 'Content-Type': 'application/json'}
            self.assertEqual(request('POST', '/api/articles/save', self.body, headers)[0], 403)
            headers['Origin'] = 'https://attacker.test'
            self.assertEqual(request('POST', '/api/articles/save', self.body, headers)[0], 403)
            headers['Origin'] = f'http://127.0.0.1:{port}'
            self.assertEqual(request('POST', '/api/articles/save', self.body, headers)[0], 200)
            self.assertEqual(len(self.catalog.read('articles')), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class PublishedDataTest(unittest.TestCase):
    def test_recovered_dates_and_real_files(self):
        rows = json.loads((ROOT / 'data/articles.json').read_text())
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        for row in rows:
            self.assertTrue((ROOT / row['path']).is_file())
            self.assertNotIn('D:/', json.dumps(row))

    def test_reader_is_sandboxed(self):
        reader = (ROOT / 'reader.html').read_text()
        self.assertIn('sandbox="allow-popups allow-popups-to-escape-sandbox"', reader)
        self.assertNotIn('allow-scripts', reader)
        self.assertNotIn('allow-same-origin', reader)

    def test_build_excludes_private_and_backend_files(self):
        spec = importlib.util.spec_from_file_location('starcape_build', ROOT / 'scripts/build.py')
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / 'site'
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('.git', 'dist', '__pycache__', '.runtime'))
            build.build(copy)
            dest = copy / 'dist'
            self.assertFalse((dest / 'scripts').exists())
            self.assertFalse((dest / '.runtime').exists())
            self.assertTrue((dest / 'index.html').exists())
            self.assertEqual(len(list((dest / 'readings').glob('*.html'))), len(json.loads((dest / 'data/articles.json').read_text())))


if __name__ == '__main__':
    unittest.main()

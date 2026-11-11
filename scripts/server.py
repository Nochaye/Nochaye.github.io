#!/usr/bin/env python3
"""Loopback-only editor for a static GitHub Pages repository. No dependencies."""
import argparse
import hmac
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import uuid
from datetime import date, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.Lock()
MAX_HTML = 2 * 1024 * 1024


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Catalog:
    def __init__(self, root):
        self.root = Path(root)

    def read(self, name):
        return json.loads((self.root / 'data' / (name + '.json')).read_text(encoding='utf-8'))

    def write(self, name, rows):
        atomic_write(self.root / 'data' / (name + '.json'), json.dumps(rows, ensure_ascii=False, indent=2) + '\n')

    @staticmethod
    def text(body, key, limit, required=False):
        value = body.get(key, '')
        if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
            raise ValueError('字段无效：' + key)
        return value.strip()

    @staticmethod
    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', value):
            raise ValueError('无效的 ID')
        return value

    @staticmethod
    def url(value):
        if not value:
            return ''
        parsed = urlsplit(value)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('请填写不含账户信息的 HTTP(S) 链接')
        return value

    def backup(self, path):
        if path.exists():
            target = self.root / '.runtime' / 'trash' / (datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8] + '-' + path.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    def article_path(self, item):
        path = item['path']
        if not re.fullmatch(r'readings/[a-zA-Z0-9_-]+\.html', path):
            raise ValueError('索引中的文件路径无效')
        resolved = (self.root / path).resolve()
        if resolved.parent != (self.root / 'readings').resolve() or (self.root / path).is_symlink():
            raise ValueError('不允许符号链接')
        return resolved

    def save_article(self, body):
        rows = self.read('articles')
        supplied_id = body.get('id', '')
        identifier = self.identifier(supplied_id) if supplied_id else uuid.uuid4().hex
        existing = next((x for x in rows if x['id'] == identifier), None)
        if supplied_id and not existing:
            raise ValueError('文章已不存在，请刷新')
        item = dict(existing or {'id': identifier, 'path': 'readings/' + identifier + '.html', 'tags': ['Level 1']})
        for key, limit in [('title', 160), ('description', 500)]:
            item[key] = self.text(body, key, limit, True)
        for key in ['edition', 'updated', 'published']:
            value = self.text(body, key, 10, key != 'published')
            if value:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                    raise ValueError('日期格式应为 YYYY-MM-DD')
                date.fromisoformat(value)
            item[key] = value
        item['source'] = self.url(self.text(body, 'source', 2048))
        html = body.get('html')
        if html is None and not existing:
            raise ValueError('添加精读需要 HTML 文件')
        if html is not None:
            if not isinstance(html, str) or not html.strip() or len(html.encode('utf-8')) > MAX_HTML:
                raise ValueError('HTML 为空或超过 2 MB')
            if '\x00' in html or not re.search(r'<(?:html|!doctype\s+html)\b', html, re.I):
                raise ValueError('请上传完整的 UTF-8 HTML 文件')
        path = self.article_path(item)
        # Backup both index and content before modifying either.
        self.backup(self.root / 'data/articles.json')
        if html is not None:
            self.backup(path)
            atomic_write(path, html)
        item['provenance'] = item.get('provenance', '本机后台导入')
        updated = [item if x['id'] == identifier else x for x in rows]
        if not existing:
            updated.append(item)
        self.write('articles', updated)
        return {'id': identifier}

    def delete_article(self, body):
        identifier = self.identifier(body.get('id'))
        rows = self.read('articles')
        item = next((x for x in rows if x['id'] == identifier), None)
        if not item:
            raise ValueError('文章已不存在')
        path = self.article_path(item)
        self.backup(self.root / 'data/articles.json')
        self.backup(path)
        self.write('articles', [x for x in rows if x['id'] != identifier])
        path.unlink(missing_ok=True)
        return {'deleted': identifier}

    def import_links(self, body):
        incoming = body.get('links')
        if not isinstance(incoming, list) or not 1 <= len(incoming) <= 500:
            raise ValueError('每次导入 1 至 500 个书签')
        rows = self.read('links')
        seen = {x['url'] for x in rows}
        added = 0
        for entry in incoming:
            if not isinstance(entry, dict):
                raise ValueError('书签格式无效')
            url = self.url(self.text(entry, 'url', 2048, True))
            title = self.text(entry, 'title', 160, True)
            if url in seen:
                continue
            seen.add(url)
            rows.append(dict(id=uuid.uuid4().hex, title=title, url=url, description='从浏览器书签导入', category='探索与工具', icon=title[0], source='浏览器书签 · 手动筛选'))
            added += 1
        self.backup(self.root / 'data/links.json')
        self.write('links', rows)
        return {'added': added}

    def delete_link(self, body):
        identifier = self.identifier(body.get('id'))
        rows = self.read('links')
        if not any(x['id'] == identifier for x in rows):
            raise ValueError('网站不存在')
        self.backup(self.root / 'data/links.json')
        self.write('links', [x for x in rows if x['id'] != identifier])
        return {'deleted': identifier}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root=ROOT, **kwargs):
        self.root = Path(root)
        super().__init__(*args, directory=str(root), **kwargs)

    def log_message(self, format, *args):
        # Do not log tokens or imported content.
        pass

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        if unquote(urlsplit(self.path).path).startswith('/readings/'):
            self.send_header('Content-Security-Policy', "sandbox allow-popups; default-src 'none'; style-src 'unsafe-inline'; img-src data:")
        super().end_headers()

    def reply(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def authorized(self):
        provided = self.headers.get('X-Starcape-Token', '')
        return self.allowed_host() and hmac.compare_digest(provided.encode(), self.server.token.encode())

    def safe_static_path(self):
        raw = unquote(urlsplit(self.path).path)
        parts = Path(raw).parts
        if any(part.startswith('.') or part in ('scripts', 'tests', 'docs') for part in parts):
            return False
        full = (self.root / raw.lstrip('/')).resolve()
        return full.is_relative_to(self.root.resolve()) and (full.is_file() or raw == '/') and full.suffix not in ('.py', '.jsonl')

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, {'error': '只允许本机访问'})
        if urlsplit(self.path).path == '/api/status':
            return self.reply(200, {'mode': 'local'}) if self.authorized() else self.reply(403, {'error': '请使用终端打印的管理链接'})
        if not self.safe_static_path():
            return self.reply(404, {'error': '未找到页面'})
        super().do_GET()

    def do_HEAD(self):
        if not self.allowed_host() or not self.safe_static_path():
            self.send_response(404)
            self.end_headers()
            return
        super().do_HEAD()

    def do_POST(self):
        origin = self.headers.get('Origin')
        expected = 'http://' + self.headers.get('Host', '')
        if not self.authorized() or origin != expected:
            return self.reply(403, {'error': '管理令牌或请求来源无效'})
        if self.headers.get_content_type() != 'application/json':
            return self.reply(415, {'error': '仅支持 JSON 请求'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 6 * 1024 * 1024:
                return self.reply(413, {'error': '请求过大或为空'})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求必须为对象')
            catalog = Catalog(self.root)
            routes = {'/api/articles/save': catalog.save_article, '/api/articles/delete': catalog.delete_article, '/api/links/import': catalog.import_links, '/api/links/delete': catalog.delete_link}
            action = routes.get(urlsplit(self.path).path)
            if not action:
                return self.reply(404, {'error': '未知操作'})
            with LOCK:
                result = action(body)
            self.reply(200, result)
        except (ValueError, UnicodeError, TypeError) as e:
            self.reply(400, {'error': str(e)})
        except OSError:
            self.reply(500, {'error': '文件写入失败，请检查权限；备份保存在 .runtime/trash'})


def make_server(root=ROOT, port=8765, token=None):
    server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, root=root))
    server.token = token or secrets.token_urlsafe(32)
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = make_server(port=args.port)
    print(f'首页：http://127.0.0.1:{server.server_port}/', flush=True)
    print(f'管理：http://127.0.0.1:{server.server_port}/admin.html#token={server.token}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

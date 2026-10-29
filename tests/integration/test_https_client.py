import hashlib
import http.server
import json
import os
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse

from media_file_explorer.companion_http import PinnedHttpsClient

FIXTURES = Path(__file__).parent / 'fixtures'


class Handler(http.server.BaseHTTPRequestHandler):
    data = {'/share/a.txt': b'hello'}
    hits = 0

    def do_GET(self):
        type(self).hits += 1
        route = urlparse(self.path)
        if route.path == '/v1/list':
            self._json(
                200,
                {
                    'entries': [
                        {
                            'name': 'a.txt',
                            'isDirectory': False,
                            'size': 5,
                            'modified': 1,
                        }
                    ]
                },
            )
        elif route.path == '/v1/file':
            value = self.data.get(parse_qs(route.query).get('path', [''])[0])
            self.send_response(200 if value is not None else 404)
            self.end_headers()
            if value is not None:
                self.wfile.write(value)
        else:
            self._json(404, {'message': 'missing'})

    def do_PUT(self):
        type(self).hits += 1
        path = parse_qs(urlparse(self.path).query).get('path', [''])[0]
        self.data[path] = self.rfile.read(int(self.headers['Content-Length']))
        self._json(200, {})
    def do_POST(self):
        type(self).hits += 1
        self._json(200, {})
    def do_DELETE(self):
        type(self).hits += 1
        self.data.pop(parse_qs(urlparse(self.path).query).get('path', [''])[0], None)
        self._json(200, {})
    def _json(self, status, value):
        payload = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


class PinnedHttpsIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.hits = 0
        cls.server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            FIXTURES / 'server-cert.pem', FIXTURES / 'server-key.pem'
        )
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()
        cert = ssl.PEM_cert_to_DER_cert((FIXTURES / 'server-cert.pem').read_text())
        cls.fingerprint = hashlib.sha256(cert).hexdigest()
        cls.client = PinnedHttpsClient(
            '127.0.0.1', cls.server.server_port, cls.fingerprint, 'token'
        )
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_round_trips(self):
        self.assertEqual(
            self.client.get_json('/v1/list', {'path': '/'})['entries'][0]['name'],
            'a.txt',
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'a.txt')
            self.client.download('/share/a.txt', target)
            self.assertEqual(Path(target).read_bytes(), b'hello')
            upload = os.path.join(tmp, 'b.txt')
            Path(upload).write_bytes(b'world')
            self.client.upload(upload, '/share/b.txt')
        self.client.post_json('/v1/mkdir', {'path': '/share/folder'})
        self.client.post_json(
            '/v1/rename', {'from': '/share/a.txt', 'to': '/share/c.txt'}
        )
        self.client.delete('/v1/entry', {'path': '/share/c.txt'})
    def test_wrong_fingerprint_never_reaches_handler(self):
        before = Handler.hits
        bad = PinnedHttpsClient('127.0.0.1', self.server.server_port, '0' * 64, 'token')
        with self.assertRaises(PermissionError):
            bad.get_json('/v1/list', {})
        self.assertEqual(Handler.hits, before)


if __name__ == '__main__':
    unittest.main()

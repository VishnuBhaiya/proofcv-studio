"""Deterministic transport regression checks; no provider calls."""
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import tempfile
from pathlib import Path
import threading
import unittest
import urllib.request

from .media_http import media_response
from .http import make_handler
from .portfolio_reader import make_reader_handler


class MediaHTTPTests(unittest.TestCase):
    def test_single_closed_open_and_suffix_ranges(self):
        for header, expected, interval in [('bytes=2-4', b'234', '2-4'), ('bytes=7-', b'789', '7-9'), ('bytes=-3', b'789', '7-9'), ('bytes=8-99', b'89', '8-9')]:
            with self.subTest(header=header):
                code, body, headers = media_response(b'0123456789', 'video/mp4', header)
                self.assertEqual((code, body), (206, expected))
                self.assertEqual(headers['Content-Range'], f'bytes {interval}/10')

    def test_unsatisfiable_ranges(self):
        for header in ('bytes=10-', 'bytes=5-2', 'bytes=-0'):
            self.assertEqual(media_response(b'0123456789', 'audio/wav', header), (416, b'', {'Accept-Ranges': 'bytes', 'Content-Range': 'bytes */10'}))

    def test_invalid_multiple_and_non_media_are_not_sliced(self):
        for header in (None, 'bytes=', 'items=0-3', 'bytes=0-1,4-5'):
            self.assertEqual(media_response(b'abc', 'video/mp4', header)[:2], (200, b'abc'))
        self.assertEqual(media_response(b'abc', 'application/json', 'bytes=1-2'), (200, b'abc', {}))

    def test_owner_and_read_only_reader_preserve_headers_and_seek(self):
        raw = b'0123456789'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset = root / 'fixture' / 'media' / ('a' * 64 + '.mp4')
            asset.parent.mkdir(parents=True)
            asset.write_bytes(raw)
            owner = make_handler(SimpleNamespace(portfolio=SimpleNamespace(asset=lambda *_: (raw, 'video/mp4'))))
            reader = make_reader_handler(SimpleNamespace(root=root, public=lambda _: {}))
            for handler, route in ((owner, '/api/workspaces/fixture/portfolio-assets/video'), (reader, '/site/fixture/media/' + asset.name)):
                server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + route, headers={'Range': 'bytes=3-6'})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 206)
                        self.assertEqual(response.read(), b'3456')
                        self.assertEqual(response.headers['Content-Length'], '4')
                        self.assertEqual(response.headers['Content-Range'], 'bytes 3-6/10')
                        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
                finally:
                    server.shutdown(); server.server_close(); thread.join()

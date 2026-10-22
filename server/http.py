"""Loopback-only JSON API. Serves only dist assets, never .env or runtime files."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .service import Service, ROOT
from .gemini import GeminiError


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def trusted_host(self):
            try:
                return urlsplit('//'+self.headers.get('Host','')).hostname in ('127.0.0.1','localhost')
            except ValueError:
                return False

        def log_message(self, format, *args):
            pass  # Request bodies and personal data do not belong in access logs.

        def send(self, status, value, content_type='application/json'):
            payload = json.dumps(value).encode() if content_type == 'application/json' else value
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if not self.trusted_host():
                self.send(403, {'error': 'Only local hostnames are accepted.'})
                return
            path = urlsplit(self.path).path
            try:
                if path == '/api/status':
                    model_status = service.model.public_status() if hasattr(service.model, 'public_status') else service.model.settings.public_status()
                    self.send(200, {**model_status, 'embedding_model': service.retriever.backend_name, 'job_count': len(service.jobs)})
                elif path == '/api/workspaces':
                    self.send(200, service.store.list())
                elif path == '/api/workspace-trash':
                    self.send(200, service.store.trash_list())
                elif path.startswith('/api/workspaces/') and path.count('/') == 3:
                    self.send(200, service.store.get(path.split('/')[-1]))
                elif path.startswith('/api/'):
                    self.send(404, {'error': 'Endpoint not found.'})
                else:
                    target = (ROOT / 'dist' / (path.lstrip('/') or 'index.html')).resolve()
                    if not target.is_relative_to((ROOT / 'dist').resolve()) or not target.is_file():
                        self.send(404, {'error': 'File not found.'})
                    else:
                        self.send(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
            except ValueError as error:
                self.send(404, {'error': str(error)})

        def do_POST(self):
            # Consume bounded request bodies before rejecting headers. Closing a
            # socket with unread bytes can reset it before Windows clients receive
            # the error response. Oversized bodies are never drained into memory.
            try:
                length = int(self.headers.get('Content-Length', 0))
            except ValueError:
                self.send(400, {'error': 'Invalid content length.'})
                return
            upload = urlsplit(self.path).path.endswith('/upload-document')
            if not 0 < length <= (7500000 if upload else 200000):
                self.send(400, {'error': 'Request is empty or too large.'})
                return
            self.connection.settimeout(10)
            try:
                body = self.rfile.read(length)
            except TimeoutError:
                self.send(408, {'error': 'Request body timed out.'})
                return
            if not self.trusted_host():
                self.send(403, {'error': 'Only local hostnames are accepted.'})
                return
            # JSON plus origin validation prevents drive-by web forms writing local data.
            if self.headers.get('Origin') not in (None, 'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000', 'http://localhost:8000'):
                self.send(403, {'error': 'Origin not allowed.'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.send(415, {'error': 'JSON content required.'})
                return
            try:
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError('Request must be a JSON object.')
                path = urlsplit(self.path).path
                if path == '/api/workspaces':
                    self.send(201, service.store.create(data.get('label', '')))
                else:
                    parts = path.strip('/').split('/')
                    if len(parts) != 4 or parts[:2] != ['api', 'workspaces']:
                        raise ValueError('Endpoint not found.')
                    if parts[3] == 'pdf':
                        from .pdf import render
                        with service.store.lock:
                            state = service.store.get(parts[2])
                            if data.get('revision') != state['revision']:
                                raise ValueError('Profile revision changed.')
                            pdf = render(state)
                        self.send(200, pdf, 'application/pdf')
                    else:
                        self.send(200, service.action(parts[2], parts[3], data))
            except GeminiError as error:
                self.send(503 if error.retryable else 502, {'error': str(error), 'retryable': error.retryable, 'quota_details': error.quota_details})
            except (ValueError, KeyError, TypeError) as error:
                self.send(400, {'error': str(error) if isinstance(error, ValueError) else 'Invalid request fields.'})
            except Exception:
                self.send(500, {'error': 'Server operation failed. Your previously saved data is retained.'})
    return Handler


if __name__ == '__main__':
    # Make the labelled cross-user sample available on a completely fresh setup.
    from .seed_labelled_sample import seed
    seed()
    server = ThreadingHTTPServer(('127.0.0.1', 8000), make_handler(Service()))
    print('ProofCV Python server: http://127.0.0.1:8000', flush=True)
    server.serve_forever()

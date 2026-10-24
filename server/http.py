"""Loopback-only JSON API. Serves only dist assets, never .env or runtime files."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .service import Service, ROOT
from .gemini import GeminiError
from .media_http import media_response


def make_handler(service):
    # Same approved-only guide as the reader, with an independent bounded local
    # session pool. Never construct a model context from the owner's draft.
    from threading import Lock
    guide = None
    guide_lock = Lock()

    def preview_guide():
        nonlocal guide
        with guide_lock:
            if guide is None:
                from .portfolio_reader import Reader
                guide = Reader(service.store.path.parent / 'reader-public', service.model)
            return guide

    class Handler(BaseHTTPRequestHandler):
        def trusted_host(self):
            try:
                return urlsplit('//'+self.headers.get('Host','')).hostname in ('127.0.0.1','localhost')
            except ValueError:
                return False

        def log_message(self, format, *args):
            pass  # Request bodies and personal data do not belong in access logs.

        def send(self, status, value, content_type='application/json', cookie=None):
            payload = json.dumps(value).encode() if content_type == 'application/json' else value
            status, payload, media_headers = media_response(payload, content_type, self.headers.get('Range')) if status == 200 else (status, payload, {})
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'SAMEORIGIN' if self.path.startswith('/portfolio-preview/') else 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            if cookie:
                self.send_header('Set-Cookie', cookie)
            for key, value in media_headers.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # Browser navigation can cancel a static/media response.

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
                elif path.startswith('/api/workspaces/') and path.endswith('/portfolio') and path.count('/') == 4:
                    self.send(200, service.portfolio.get(path.split('/')[3]))
                elif path.startswith('/api/workspaces/') and '/portfolio-assets/' in path and path.count('/') == 5:
                    parts = path.split('/')
                    raw, mime = service.portfolio.asset(parts[3], parts[5])
                    self.send(200, raw, mime)
                elif path.startswith('/api/workspaces/') and '/portfolio-audio/' in path and path.count('/') == 5:
                    parts = path.split('/')
                    raw, mime = service.portfolio.audio(parts[3], parts[5])
                    self.send(200, raw, mime)
                elif path.startswith('/showcase/'):
                    import io
                    import zipfile
                    parts = path.strip('/').split('/')
                    if len(parts) < 3:
                        raise ValueError('Use the full approved snapshot link.')
                    workspace, snapshot_id = parts[1:3]
                    relative = '/'.join(parts[3:]) or 'index.html'
                    with zipfile.ZipFile(io.BytesIO(service.portfolio.archive(workspace, snapshot_id))) as archive:
                        if relative not in archive.namelist() or '..' in relative or relative == 'manifest.json':
                            raise ValueError('Public portfolio file not found.')
                        self.send(200, archive.read(relative), mimetypes.guess_type(relative)[0] or 'application/octet-stream')
                elif path.startswith('/portfolio-preview/'):
                    from .portfolio_export import public_projection, document_html
                    parts = path.strip('/').split('/')
                    if len(parts) not in (2,3):
                        raise ValueError('Preview not found.')
                    workspace = parts[1]
                    value = service.portfolio.get(workspace)
                    if not value['portfolio']:
                        raise ValueError('Create your website draft first.')
                    relative = parts[2] if len(parts)==3 else 'index.html'
                    if relative in ('portfolio.js','portfolio.css'):
                        self.send(200,(ROOT/'portfolio-runtime'/relative).read_bytes(),mimetypes.guess_type(relative)[0])
                    elif relative == 'index.html':
                        public = public_projection(value['portfolio'])
                        cookie = None
                        # Inline preview questions use only this installed,
                        # approved snapshot, never the visible unsaved draft.
                        import re
                        for snapshot in reversed(value['portfolio']['snapshots']):
                            sid = snapshot['id']
                            if re.fullmatch(r'[a-f0-9]{32}', sid) and (service.store.path.parent / 'reader-public' / sid / 'public.json').is_file():
                                public['reader_url'] = f'http://127.0.0.1:8001/site/{sid}/'
                                chat_url = f'/api/workspaces/{workspace}/portfolio-chat'
                                approved = service.portfolio.snapshot(workspace, sid)
                                public['owner_chat'] = dict(url=chat_url, snapshot_id=sid, approved_at=approved['approved_at'])
                                token = preview_guide().session(sid)
                                cookie = f'proofcv_preview_guide={token}; HttpOnly; SameSite=Strict; Path={chat_url}; Max-Age=3600'
                                break
                        for asset in public['assets']:
                            asset['url'] = f"/api/workspaces/{workspace}/portfolio-assets/{asset['id']}"
                        if public['narration']:
                            public['narration']['url'] = f'/api/workspaces/{workspace}/portfolio-audio/accepted'
                        self.send(200,document_html(public).encode(),'text/html',cookie=cookie)
                    else:
                        raise ValueError('Preview not found.')
                elif path.startswith('/api/workspaces/') and path.count('/') == 3:
                    self.send(200, service.store.get(path.split('/')[-1]))
                elif path.startswith('/api/interview/'):
                    from .interview.routes import handle_get as interview_get
                    result = interview_get(service, self.path)
                    self.send(200, result, 'application/pdf') if isinstance(result, bytes) else self.send(200, result)
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
            request_path = urlsplit(self.path).path
            upload = request_path.endswith(('/upload-document', '/answer', '/evaluation-sample'))
            portfolio_upload = request_path.endswith('/portfolio-upload')
            if not 0 < length <= (17000000 if portfolio_upload else 7500000 if upload else 200000):
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
            is_guide = request_path.endswith('/portfolio-chat')
            allowed_origins = ('http://' + self.headers.get('Host',''),) if is_guide else (None, 'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000', 'http://localhost:8000')
            if self.headers.get('Origin') not in allowed_origins:
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
                elif path.startswith('/api/interview/'):
                    from .interview.routes import handle_post as interview_post
                    result = interview_post(service, path, data)
                    self.send(200, result, 'audio/wav') if isinstance(result, bytes) else self.send(200, result)
                else:
                    parts = path.strip('/').split('/')
                    if len(parts) != 4 or parts[:2] != ['api', 'workspaces']:
                        raise ValueError('Endpoint not found.')
                    if parts[3] == 'portfolio-chat':
                        if length > 5000 or set(data) != {'question','snapshot_id'}:
                            raise ValueError('Ask a question using the approved snapshot only.')
                        sid = data.get('snapshot_id')
                        if not isinstance(sid,str):
                            raise ValueError('Approved snapshot required. Reload the preview.')
                        # Enforces active workspace ownership and refuses a
                        # different workspace's otherwise-valid snapshot.
                        service.portfolio.snapshot(parts[2],sid)
                        from http.cookies import SimpleCookie
                        cookies = SimpleCookie(self.headers.get('Cookie',''))
                        token = cookies['proofcv_preview_guide'].value if 'proofcv_preview_guide' in cookies else ''
                        self.send(200,preview_guide().chat(sid,token,data.get('question'),self.client_address[0]))
                    elif parts[3] == 'portfolio-export':
                        state = service.store.get(parts[2])
                        if data.get('revision') != state['revision']:
                            raise ValueError('Profile revision changed.')
                        self.send(200, service.portfolio.archive(parts[2], data.get('snapshot_id')), 'application/zip')
                    elif parts[3] == 'pdf':
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

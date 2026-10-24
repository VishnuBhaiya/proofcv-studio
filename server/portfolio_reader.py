"""Separate loopback-only, read-only portfolio reader. Never imports owner Store/Service.

Receives explicitly installed public ZIPs only. No credentials are shipped in them.
This is a local assessment service, NOT a production hosting/authentication system.
"""
import hashlib
import io
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
from threading import BoundedSemaphore, RLock
import time
from urllib.parse import urlsplit
import zipfile

from .gemini import GeminiFallbackModel, GeminiSettings, GeminiError
from .portfolio_prompts import CHAT
from .media_http import media_response

PUBLIC_ROOT = Path(__file__).resolve().parents[1] / 'runtime' / 'reader-public'


def guide_sources(public):
    """Citable text from approved public fields, never from the owner workspace."""
    sources = dict(public['sources'])
    sources['introduction'] = public['bio']
    skills = public.get('person', {}).get('skills', [])
    if skills:
        sources['profile-listed-skills'] = 'Profile-listed skills (not independent verification): ' + ', '.join(skills)
    for project in public['projects']:
        if project.get('technologies', '').strip():
            sources['project-tools:' + project['id']] = 'Project: ' + project['title'] + '\nListed technologies: ' + project['technologies']
    return sources


def install_snapshot(snapshot_id, raw, root=PUBLIC_ROOT):
    if not re.fullmatch(r'[a-f0-9]{32}', snapshot_id):
        raise ValueError('Invalid snapshot ID.')
    destination = Path(root) / snapshot_id
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        if manifest['snapshot_id'] != snapshot_id:
            raise ValueError('Snapshot integrity mismatch.')
        for key, digest in manifest['files'].items():
            if not re.fullmatch(r'(index\.html|portfolio\.(js|css)|README\.txt|THIRD_PARTY_NOTICES\.txt|resume\.pdf|media/[a-f0-9]{64}\.(png|mp4|wav))', key):
                raise ValueError('Unexpected public package path.')
            content = archive.read(key)
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError('Package integrity mismatch.')
            path = destination / key
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != content:
                raise ValueError('Cannot overwrite an immutable public snapshot.')
            path.write_bytes(content)
        # Only public data is extracted from the already-reviewed HTML payload.
        document = archive.read('index.html').decode()
        match = re.search(r'<script type="application/json" id="portfolio-data">(.*?)</script>', document, re.S)
        public = json.loads(match.group(1))
        (destination / 'public.json').write_text(json.dumps(public), encoding='utf-8')


class Reader:
    def __init__(self, root=PUBLIC_ROOT, model=None):
        self.root = Path(root)
        self.model = model or GeminiFallbackModel(GeminiSettings.load())
        self.sessions, self.counts, self.total = {}, {}, 0
        self.lock, self.slots = RLock(), BoundedSemaphore(1)

    def public(self, site):
        if not re.fullmatch(r'[a-f0-9]{32}', site):
            raise ValueError('Unknown site.')
        path = self.root / site / 'public.json'
        if not path.is_file():
            raise ValueError('Approved site not installed. Enable its local reader in Portfolio Studio.')
        return json.loads(path.read_text(encoding='utf-8'))

    def session(self, site):
        self.public(site)
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions = {k:v for k,v in self.sessions.items() if v[1] > time.monotonic()}
            if len(self.sessions) >= 100:
                raise ValueError('Reader session limit reached.')
            self.sessions[token] = (site, time.monotonic() + 3600)
        return token

    def chat(self, site, token, question, client):
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1200:
            raise ValueError('Ask a question of 1–1200 characters.')
        public = self.public(site)
        with self.lock:
            if token not in self.sessions or self.sessions[token][0] != site or self.sessions[token][1] < time.monotonic():
                raise ValueError('Open or reload the portfolio to start a local reader session.')
            key = (client, int(time.monotonic() // 60))
            if self.counts.get(key, 0) >= 5 or self.total >= 50:
                raise ValueError('Reader request budget reached (5/minute; 50 per server session).')
            self.counts = {k:v for k,v in self.counts.items() if k[1] >= key[1] - 1}
            self.counts[key] = self.counts.get(key, 0) + 1
            self.total += 1
        if not self.slots.acquire(blocking=False):
            raise ValueError('The reader is answering another question. Try again shortly.')
        try:
            # No conversation history, private data, model tools or owner credentials in context.
            sources = guide_sources(public)
            context = dict(sources=sources, projects=[dict(id=p['id'], title=p['title']) for p in public['projects']])
            if len(json.dumps(context)) > 100000:
                raise ValueError('This approved portfolio exceeds the reader context budget.')
            value = json.loads(self.model.decide([dict(role='system', content=CHAT), dict(role='user', content=question)], context))
            if not isinstance(value, dict) or set(value) - {'answer','sources','project_id'}:
                raise ValueError('Reader returned an invalid answer.')
            answer, cited, project = value.get('answer'), value.get('sources'), value.get('project_id','')
            if not isinstance(answer, str) or not 1 <= len(answer) <= 3000 or not isinstance(cited, list) or len(cited) > 8 or any(not isinstance(key,str) or key not in sources for key in cited):
                raise ValueError('Reader returned unsupported source references.')
            if project and project not in {p['id'] for p in public['projects']}:
                raise ValueError('Reader returned an unsupported navigation target.')
            if not cited:
                answer = 'That information is not stated in the approved portfolio. Please contact the candidate through their published links.'
                project = ''
            return dict(answer=answer, sources=[dict(id=k, text=sources[k]) for k in cited], project_id=project,
                        model=getattr(self.model,'name','unknown'))
        finally:
            self.slots.release()


def make_reader_handler(reader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, raw, mime='application/json', cookie=None):
            if mime == 'application/json':
                raw = json.dumps(raw).encode()
            code, raw, media_headers = media_response(raw, mime, self.headers.get('Range')) if code == 200 else (code, raw, {})
            self.send_response(code)
            for key, value in {'Content-Type': mime, 'Content-Length': str(len(raw)), 'Cache-Control':'no-store',
                'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer', 'X-Frame-Options':'DENY',
                'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"}.items():
                self.send_header(key, value)
            for key, value in media_headers.items():
                self.send_header(key, value)
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def trusted(self):
            try:
                return urlsplit('//' + self.headers.get('Host','')).hostname in ('127.0.0.1','localhost')
            except ValueError:
                return False

        def do_GET(self):
            if not self.trusted():
                self.send(403, {'error':'Local reader only.'}); return
            parts = urlsplit(self.path).path.strip('/').split('/')
            try:
                if len(parts) < 2 or parts[0] != 'site':
                    raise ValueError('Read-only portfolio route not found.')
                site = parts[1]; reader.public(site)
                relative = '/'.join(parts[2:]) or 'index.html'
                if not re.fullmatch(r'(index\.html|portfolio\.(js|css)|resume\.pdf|media/[a-f0-9]{64}\.(png|mp4|wav))', relative):
                    raise ValueError('Public asset not found.')
                path = reader.root / site / relative
                if not path.is_file():
                    raise ValueError('Public asset not found.')
                cookie = None
                if relative == 'index.html':
                    token = reader.session(site)
                    cookie = f'proofcv_reader={token}; HttpOnly; SameSite=Strict; Path=/site/{site}/; Max-Age=3600'
                self.send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream', cookie)
            except ValueError as error:
                self.send(404, {'error':str(error)})

        def do_POST(self):
            try:
                if not self.trusted() or self.headers.get('Origin') not in ('http://' + self.headers.get('Host',''),):
                    self.send(403, {'error':'Reader origin rejected.'}); return
                if self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ValueError('JSON required.')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 5000:
                    raise ValueError('Question too large.')
                self.connection.settimeout(10)
                parts = urlsplit(self.path).path.strip('/').split('/')
                if len(parts) != 3 or parts[0] != 'site' or parts[2] != 'chat':
                    raise ValueError('Read-only chat route not found.')
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError('Question must be a JSON object.')
                from http.cookies import SimpleCookie
                cookie = SimpleCookie(self.headers.get('Cookie',''))
                token = cookie['proofcv_reader'].value if 'proofcv_reader' in cookie else ''
                self.send(200, reader.chat(parts[1], token, body.get('question'), self.client_address[0]))
            except GeminiError as error:
                self.send(503, {'error':str(error)})
            except (ValueError, KeyError, TypeError, TimeoutError) as error:
                self.send(400, {'error':str(error)[:250]})
    return Handler


if __name__ == '__main__':
    print('Separate local portfolio reader: http://127.0.0.1:8001 (no owner routes; 50-request session budget)', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8001), make_reader_handler(Reader())).serve_forever()

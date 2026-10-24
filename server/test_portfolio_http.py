"""Real loopback HTTP checks with deterministic providers; no live AI claims."""
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import base64
import zipfile

from . import test_portfolio as fixtures
from .portfolio_reader import Reader, install_snapshot, make_reader_handler
from .test_system import SequenceModel
from .portfolio_assets import MediaStore
from .service import Service
from .http import make_handler


class PortfolioHTTPTests(fixtures.PortfolioTests):
    # Reuse setup and helpers, not inherited test methods (filtered below).
    def test_reader_has_no_owner_routes_and_enforces_origin_cookie_json(self):
        self.action('portfolio-approve',accepted=True);snap=self.p['snapshots'][-1]
        root=Path(self.temp.name)/'public';install_snapshot(snap['id'],self.service.archive(self.state['id'],snap['id']),root)
        model=SequenceModel([dict(answer='A Python API was built.',sources=['s0'],project_id='')])
        server=ThreadingHTTPServer(('127.0.0.1',0),make_reader_handler(Reader(root,model)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/site/'+snap['id']+'/') as r:
                cookie=r.headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
                self.assertIn(b'portfolio.js',r.read());self.assertIn("script-src 'self'",r.headers['Content-Security-Policy'])
            def post(body,origin=base,cookie=cookie):
                request=urllib.request.Request(base+'/site/'+snap['id']+'/chat',json.dumps(body).encode(),{'Origin':origin,'Content-Type':'application/json','Cookie':cookie})
                return urllib.request.urlopen(request)
            with self.assertRaises(urllib.error.HTTPError) as error:post({'question':'What was built?'},origin='https://evil.example')
            self.assertEqual(error.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError):post({'question':'What was built?'},cookie='')
            with self.assertRaises(urllib.error.HTTPError):post([])
            with post({'question':'What was built?'}) as r:self.assertTrue(json.load(r)['sources'])
            for path in ('/api/workspaces','/.env','/site/'+snap['id']+'/public.json','/site/'+snap['id']+'/../../.env'):
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+path)
        finally:server.shutdown();server.server_close();thread.join()

    def test_purge_removes_only_unshared_owned_media_and_installed_snapshot(self):
        asset=self.approve_media();self.action('portfolio-approve',accepted=True);snap=self.p['snapshots'][-1]
        self.action('portfolio-reader',snapshot_id=snap['id'])
        blob=self.service.media.root/asset['key'];installed=Path(self.temp.name)/'reader-public'/snap['id']
        self.assertTrue(blob.is_file());self.assertTrue(installed.is_dir())
        self.store.move_to_trash(self.state['id'],self.state['revision']);self.store.purge_trash()
        self.assertFalse(blob.exists());self.assertFalse(installed.exists())

    def test_shared_media_survives_another_workspace_purge(self):
        asset=self.upload();other=self.store.create('Other active fixture')
        p=json.loads(json.dumps(self.p));self.service._save(other['id'],p)
        self.store.move_to_trash(self.state['id'],self.state['revision']);self.store.purge_trash()
        self.assertTrue((self.service.media.root/asset['key']).is_file())

    def test_removed_private_asset_is_still_owned_for_permanent_purge(self):
        asset=self.upload();blob=self.service.media.root/asset['key']
        self.action('portfolio-remove',asset_id=asset['id'])
        self.assertEqual(self.p['assets'],[])
        self.assertIn({'key':asset['key']},self.p['retired_media'])
        self.store.move_to_trash(self.state['id'],self.state['revision']);self.store.purge_trash()
        self.assertFalse(blob.exists())

    def test_video_decoder_actual_mp4_and_rejects_corruption_without_orphans(self):
        import imageio_ffmpeg
        path=Path(self.temp.name)/'synthetic.mp4'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=green:s=320x180:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result=self.service.media.video(base64.b64encode(path.read_bytes()).decode())
        self.assertEqual(result['width'],320);self.assertGreater(result['duration'],0)
        before=set(self.service.media.root.iterdir())
        with self.assertRaises(ValueError):self.service.media.video(base64.b64encode(b'0000ftyp' + b'not-video'*20).decode())
        self.assertEqual(before,set(self.service.media.root.iterdir()))

    def test_export_without_bundled_node_runtime_references(self):
        self.action('portfolio-approve',accepted=True);snap=self.p['snapshots'][-1]
        with zipfile.ZipFile(io.BytesIO(self.service.archive(self.state['id'],snap['id']))) as archive:
            script=archive.read('portfolio.js').decode()
            self.assertNotIn('process.env.NODE_ENV',script)
            self.assertNotIn('http://localhost:5173',script)

    def test_owner_preview_is_scoped_and_separate_from_approved_export(self):
        service=Service(store=self.store,model=SequenceModel([]));service._portfolio=self.service
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/portfolio-preview/'+self.state['id']+'/') as r:
                self.assertEqual(r.headers['X-Frame-Options'],'SAMEORIGIN')
                contents=r.read().decode();self.assertIn('Test Candidate',contents);self.assertNotIn('test@example.test',contents)
                self.assertNotIn('reader_url',contents)
            self.action('portfolio-approve',accepted=True)
            installed=self.p['snapshots'][-1]['id']
            self.action('portfolio-reader',snapshot_id=installed)
            # A newer but uninstalled snapshot must not strand the draft link.
            self.action('portfolio-approve',accepted=True)
            uninstalled=self.p['snapshots'][-1]['id']
            with urllib.request.urlopen(base+'/portfolio-preview/'+self.state['id']+'/') as r:
                contents=r.read().decode()
                cookie=r.headers['Set-Cookie']
                self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
                self.assertIn('Path=/api/workspaces/'+self.state['id']+'/portfolio-chat',cookie)
                self.assertIn('owner_chat',contents)
                self.assertIn('http://127.0.0.1:8001/site/'+installed+'/',contents)
                self.assertNotIn('http://127.0.0.1:8001/site/'+uninstalled+'/',contents)
            with zipfile.ZipFile(io.BytesIO(self.service.archive(self.state['id'],installed))) as archive:
                self.assertNotIn('reader_url',archive.read('index.html').decode())
                self.assertNotIn('owner_chat',archive.read('index.html').decode())
            with urllib.request.urlopen(base+'/portfolio-preview/'+self.state['id']+'/portfolio.js') as r:
                self.assertGreater(len(r.read()),1000)
            for path in ('/portfolio-preview/'+self.state['id']+'/.env','/portfolio-preview/unknown/','/api/workspaces/'+self.state['id']+'/portfolio-assets/unknown'):
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+path)
        finally:server.shutdown();server.server_close();thread.join()

    def test_inline_preview_chat_uses_only_approved_sources_and_preserves_private_draft(self):
        self.action('portfolio-approve',accepted=True)
        sid=self.p['snapshots'][-1]['id'];self.action('portfolio-reader',snapshot_id=sid)
        before=self.service.archive(self.state['id'],sid)
        self.p['bio']='PRIVATE_DRAFT_ONLY_DO_NOT_SEND'
        self.p['projects'][0]['description']='PRIVATE_PROJECT_EDIT_DO_NOT_SEND'
        self.service._save(self.state['id'],self.p)
        class CapturingModel:
            name='approved-source-test'
            def __init__(self):self.contexts=[]
            def decide(self,messages,context):
                self.contexts.append(context)
                return json.dumps(dict(answer='Answer from approved text.',sources=['introduction'],project_id=''))
        model=CapturingModel();service=Service(store=self.store,model=model);service._portfolio=self.service
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/portfolio-preview/'+self.state['id']+'/') as r:
                cookie=r.headers['Set-Cookie'];self.assertIn(b'PRIVATE_DRAFT_ONLY',r.read())
            body=json.dumps(dict(question='What was built?',snapshot_id=sid)).encode()
            request=urllib.request.Request(base+'/api/workspaces/'+self.state['id']+'/portfolio-chat',body,{'Origin':base,'Content-Type':'application/json','Cookie':cookie})
            with urllib.request.urlopen(request) as r:
                answer=json.load(r);self.assertEqual(answer['sources'][0]['id'],'introduction')
            self.assertEqual(len(model.contexts),1)
            supplied=json.dumps(model.contexts[0])
            for private in ('PRIVATE_DRAFT_ONLY','PRIVATE_PROJECT_EDIT','test@example.test'):
                self.assertNotIn(private,supplied)
            self.assertEqual(self.service.get(self.state['id'])['portfolio']['bio'],'PRIVATE_DRAFT_ONLY_DO_NOT_SEND')
            self.assertEqual(self.service.archive(self.state['id'],sid),before)
        finally:server.shutdown();server.server_close();thread.join()

    def test_inline_preview_chat_enforces_origin_session_workspace_and_budget(self):
        self.action('portfolio-approve',accepted=True)
        sid=self.p['snapshots'][-1]['id'];self.action('portfolio-reader',snapshot_id=sid)
        other=self.store.create('Other workspace')
        model=SequenceModel([dict(answer='Approved answer.',sources=['introduction'],project_id='')]*5)
        service=Service(store=self.store,model=model);service._portfolio=self.service
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(service))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/portfolio-preview/'+self.state['id']+'/') as r:cookie=r.headers['Set-Cookie']
            def post(data=None,origin=base,session=cookie,workspace=self.state['id']):
                headers={'Content-Type':'application/json','Cookie':session}
                if origin is not None:headers['Origin']=origin
                request=urllib.request.Request(base+'/api/workspaces/'+workspace+'/portfolio-chat',json.dumps(data or dict(question='What was built?',snapshot_id=sid)).encode(),headers)
                return urllib.request.urlopen(request)
            for origin in (None,'https://evil.example'):
                with self.assertRaises(urllib.error.HTTPError) as error:post(origin=origin)
                self.assertEqual(error.exception.code,403)
            with self.assertRaises(urllib.error.HTTPError):post(session='')
            with self.assertRaises(urllib.error.HTTPError):post(workspace=other['id'])
            with self.assertRaises(urllib.error.HTTPError):post(dict(question='Ask',snapshot_id=sid,private_context='Not allowed'))
            with self.assertRaises(urllib.error.HTTPError):post(dict(question='x'*1201,snapshot_id=sid))
            self.action('portfolio-approve',accepted=True)
            with self.assertRaises(urllib.error.HTTPError):post(dict(question='Ask',snapshot_id=self.p['snapshots'][-1]['id']))
            for _ in range(5):
                with post() as r:self.assertEqual(r.status,200)
            with self.assertRaises(urllib.error.HTTPError) as error:post()
            self.assertIn('budget',error.exception.read().decode())
        finally:server.shutdown();server.server_close();thread.join()


# unittest otherwise repeats inherited PortfolioTests a second time.
for name in list(vars(fixtures.PortfolioTests)):
    if name.startswith('test_') and name not in vars(PortfolioHTTPTests):
        setattr(PortfolioHTTPTests,name,None)

if __name__=='__main__':unittest.main()

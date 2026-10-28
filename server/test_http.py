"""Real HTTP transport tests with synthetic local data and no model requests."""
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from .service import Service
from .store import Store
from .http import make_handler
from .gemini import GeminiDecisionModel, GeminiSettings


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.service=Service(store=Store(Path(self.directory.name)/'test.sqlite3'),
            model=GeminiDecisionModel(GeminiSettings('TEST_ONLY_PLACEHOLDER','gemini-test')))
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.service))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.directory.cleanup()
    def request(self,method,path,body=None,headers=None):
        connection=HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            connection.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers or {})
            response=connection.getresponse();return response.status,response.read().decode()
        finally:connection.close()
    def test_status_never_contains_key(self):
        code,body=self.request('GET','/api/status')
        self.assertEqual(code,200);self.assertNotIn('TEST_ONLY_PLACEHOLDER',body)
    def test_private_files_and_traversal_are_not_served(self):
        for path in ('/.env','/runtime/proofcv.sqlite3','/../.env','/%2e%2e/.env'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET',path)[0],404)
    def test_rebinding_host_is_rejected(self):
        self.assertEqual(self.request('GET','/api/workspaces',headers={'Host':'attacker.example'})[0],403)
    def test_wrong_origin_or_content_type_cannot_create_workspace(self):
        self.assertEqual(self.request('POST','/api/workspaces',{'label':'bad'},
            {'Content-Type':'application/json','Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.request('POST','/api/workspaces',{'label':'bad'})[0],415)
        self.assertEqual(self.service.store.list(),[])
    def test_page_served_on_another_port_can_save(self):
        own=f'http://127.0.0.1:{self.server.server_port}'
        self.assertEqual(self.request('POST','/api/workspaces',{'label':'Same origin'},
            {'Content-Type':'application/json','Origin':own})[0],201)
        self.assertEqual(self.request('POST','/api/workspaces',{'label':'Other local app'},
            {'Content-Type':'application/json','Origin':'http://127.0.0.1:9999'})[0],403)
        self.assertEqual([w['label'] for w in self.service.store.list()],['Same origin'])
    def test_json_create_and_read_workspace(self):
        code,body=self.request('POST','/api/workspaces',{'label':'Synthetic HTTP test'},
            {'Content-Type':'application/json','Origin':'http://127.0.0.1:8000'})
        self.assertEqual(code,201);state=json.loads(body)
        code,body=self.request('GET','/api/workspaces/'+state['id'])
        self.assertEqual(code,200);self.assertEqual(json.loads(body)['label'],'Synthetic HTTP test')


if __name__=='__main__':unittest.main()

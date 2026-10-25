import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import struct
import threading
import unittest
from unittest.mock import patch

from controller.local_import import local_files, import_file
from test_seed import temporary_directory


MODEL = b'GGUF' + struct.pack('<IQQ', 3, 1, 0) + b'fixture tensor data'


class LocalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / '.data/models/gguf/local-Q6.gguf'
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(MODEL)
        self.posts = []; parent = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_HEAD(self):
                blob = parent.root / '.data/models/blobs' / self.path.rsplit('/',1)[1].replace(':','-')
                self.send_response(200 if blob.is_file() else 404); self.end_headers()
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                parent.posts.append((self.path, body))
                if self.path.startswith('/api/blobs/'):
                    blob = parent.root / '.data/models/blobs' / self.path.rsplit('/',1)[1].replace(':','-')
                    blob.write_bytes(body)
                    self.send_response(201); self.end_headers(); return
                self.send_response(200); self.end_headers()
                self.wfile.write(b'{"status":"success"}\n')
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close_server)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def close_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def run_import(self):
        return import_file(self.root,self.base,self.source.relative_to(self.root).as_posix(),lambda **kw:None,threading.Event())

    def test_import_reuses_local_bytes_and_creates_a_source_bound_receipt(self):
        (self.root/'.data/local-model-imports.json').write_text('[]')
        name = self.run_import(); digest = hashlib.sha256(MODEL).hexdigest()
        self.assertEqual(self.source.read_bytes(), MODEL)
        self.assertEqual([path for path,_ in self.posts], ['/api/create'])
        body=json.loads(self.posts[0][1]);self.assertEqual(body['model'],name)
        self.assertEqual(body['files'],{self.source.name:'sha256:'+digest})
        blob=self.root/'.data/models/blobs'/('sha256-'+digest)
        self.assertTrue(self.source.samefile(blob))
        receipt=json.loads((self.root/'.data/local-model-imports.json').read_text())
        self.assertEqual(receipt[self.source.relative_to(self.root).as_posix()]['sha256'],digest)

    def test_cross_filesystem_fallback_uploads_existing_bytes_without_downloading(self):
        with patch('controller.local_import.os.link',side_effect=OSError('different filesystem')):
            self.run_import()
        self.assertTrue(self.posts[0][0].startswith('/api/blobs/'))
        self.assertEqual(self.posts[0][1],MODEL)
        self.assertEqual(self.posts[1][0],'/api/create')
        self.assertEqual(self.source.read_bytes(),MODEL)

    def test_import_rejects_undiscovered_paths_and_remote_destinations(self):
        for path,base in (('../outside.gguf',self.base),(str(self.source),self.base),
                          (self.source.relative_to(self.root).as_posix(),'https://remote.example')):
            with self.subTest(path=path,base=base),self.assertRaises(ValueError):
                import_file(self.root,base,path,lambda **kw:None,threading.Event())
        self.assertEqual(self.posts,[])

    def test_cancelled_import_preserves_the_original_file_and_runs_no_create(self):
        closed=threading.Event();closed.set()
        with self.assertRaisesRegex(ValueError,'closing'):
            import_file(self.root,self.base,self.source.relative_to(self.root).as_posix(),lambda **kw:None,closed)
        self.assertEqual(self.source.read_bytes(),MODEL);self.assertEqual(self.posts,[])

    def test_discovery_includes_old_model_caches_but_excludes_vocabs_and_adapters(self):
        cache=self.root/'.data/old-experiment/downloads';cache.mkdir(parents=True)
        (cache/'older.gguf').write_bytes(MODEL)
        (cache/'vocab.gguf').write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,0)+b'vocabulary')
        (cache/'adapter.gguf').write_bytes(MODEL+b'general.type'+struct.pack('<IQ',8,7)+b'adapter')
        self.assertEqual({item['name'] for item in local_files(self.root)}, {'local-Q6.gguf','older.gguf'})

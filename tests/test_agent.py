import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from agent47.core import Workspace, Session, command_needs_approval, run_command
from agent47 import server

# Each test gets a disposable project so tests never edit real project files.
class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.workspace = Workspace(self.root)

    def test_escape_and_secret_rejected(self):
        for name in ['../outside', '/etc/passwd', '.git/config', '.env.local', '.ssh/id_rsa']:
            with self.assertRaises(ValueError): self.workspace.path(name)
        try:
            (self.root / 'escape').symlink_to(Path(self.directory.name).parent, target_is_directory=True)
        except OSError:
            return  # Windows may require Developer Mode for symlinks.
        with self.assertRaises(ValueError): self.workspace.read('escape/passwd')

    def test_edit_has_diff_and_recoverable_original(self):
        (self.root / 'app.py').write_text('old\n')
        diff = self.workspace.write('app.py', 'new\n')
        self.assertIn('-old', diff)
        self.assertEqual((self.root / 'app.py').read_text(), 'new\n')
        backups = list((self.root / '.agent47/backups').glob('*/before.txt'))
        self.assertEqual(backups[0].read_text(), 'old\n')
        self.assertNotIn(str(backups[0].relative_to(self.root)), self.workspace.files())

    def test_deletion_requires_approval_and_has_backup(self):
        (self.root / 'old.txt').write_text('recover me')
        session = Session(self.root, 'fake')
        with self.assertRaises(ValueError): session.execute('delete_file', {'path': 'old.txt'})
        session.execute('delete_file', {'path': 'old.txt'}, approved=True)
        self.assertFalse((self.root / 'old.txt').exists())
        self.assertEqual(next((self.root / '.agent47/backups').glob('*/before.txt')).read_text(), 'recover me')

    def test_edit_requires_complete_fresh_read(self):
        path = self.root / 'app.py'
        path.write_text('original')
        session = Session(self.root, 'fake')
        args = {'path': 'app.py', 'content': 'changed'}
        with self.assertRaises(ValueError): session.execute('write_file', args)
        session.execute('read_file', {'path': 'app.py'})
        path.write_text('concurrent edit')
        with self.assertRaises(ValueError): session.execute('write_file', args)
        session.execute('read_file', {'path': 'app.py'})
        session.execute('write_file', args)
        self.assertEqual(path.read_text(), 'changed')
        path.write_text('x' * 17000)
        session.execute('read_file', {'path': 'app.py'})
        with self.assertRaises(ValueError): session.execute('write_file', args)

    def test_command_policy(self):
        self.assertFalse(command_needs_approval(['cargo', 'test']))
        for argv in [['sh','-c','rm a'], ['python3','-c','print(1)'], ['pip','install','anything'], ['git','push'], ['cargo','test','--extra']]:
            self.assertTrue(command_needs_approval(argv))
            with self.assertRaises(ValueError): run_command(self.root, argv)

    @unittest.skipUnless(Path('/usr/bin/sandbox-exec').exists(), 'macOS only')
    def test_command_sandbox(self):
        script = """from pathlib import Path
import socket
Path('inside.txt').write_text('ok')
try:
    Path('/tmp/agent47-outside-denied.txt').write_text('bad')
    print('OUTSIDE_ALLOWED')
except PermissionError:
    print('OUTSIDE_DENIED')
try:
    socket.create_connection(('127.0.0.1', 9), timeout=1)
    print('NETWORK_ALLOWED')
except PermissionError:
    print('NETWORK_DENIED')
"""
        result = run_command(self.root, ['python3', '-c', script], approved=True)
        self.assertEqual(result['exit_code'], 0, result)
        self.assertIn('OUTSIDE_DENIED', result['output'])
        self.assertIn('NETWORK_DENIED', result['output'])
        self.assertEqual((self.root / 'inside.txt').read_text(), 'ok')

    def test_local_pdf_extraction(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest('Optional PDF reader is not installed')
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(b'BT /F1 12 Tf 20 100 Td (Local document 47) Tj ET')
        page[NameObject('/Contents')] = writer._add_object(content)
        with (self.root / 'document.pdf').open('wb') as output: writer.write(output)
        self.assertIn('Local document 47', self.workspace.read('document.pdf'))

    # Fake model responses exercise the tool cycle without downloading or running an AI model.
    def test_tool_loop(self):
        session = Session(self.root, 'fake')
        replies = [{'message': {'role':'assistant','content':'','tool_calls':[{'function':{'name':'write_file','arguments':{'path':'hello.py','content':'print(47)\n'}}}]}},
                   {'message': {'role':'assistant','content':'Created hello.py.'}}]
        with patch('agent47.core.ollama', side_effect=replies): session.loop()
        self.assertEqual((self.root/'hello.py').read_text(), 'print(47)\n')
        self.assertEqual(session.status, 'idle')
        self.assertEqual(session.events[-1]['text'], 'Created hello.py.')
        self.assertEqual(session.messages[-2]['role'], 'tool')

    def test_denied_action_does_not_execute(self):
        session = Session(self.root, 'fake')
        replies = [{'message': {'role':'assistant','content':'','tool_calls':[{'function':{'name':'run_command','arguments':{'argv':['git','push']}}}]}},
                   {'message': {'role':'assistant','content':'Action denied.'}}]
        with patch('agent47.core.ollama', side_effect=replies), patch('agent47.core.run_command') as command:
            worker = threading.Thread(target=session.loop)
            worker.start()
            deadline = time.monotonic()+3
            while session.pending is None and time.monotonic()<deadline: time.sleep(.01)
            self.assertIsNotNone(session.pending)
            session.pending['decision'] = False
            worker.join(3)
            self.assertFalse(worker.is_alive())
            command.assert_not_called()
        self.assertEqual(session.status, 'idle')

# A temporary loopback server checks the browser-facing API and request protections.
class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.worker = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.worker.start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def test_ui_loads(self):
        with urlopen(self.base) as response:
            self.assertIn(b'What are we building?', response.read())
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])

    def test_cross_site_and_missing_token_rejected(self):
        for headers in [{}, {'X-Agent47-Token':server.TOKEN,'Origin':'https://example.com'}]:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.base+'/api/chat', data=b'{}',headers=headers))
            self.assertEqual(error.exception.code,403)

    def test_host_rebinding_rejected(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base,headers={'Host':'attacker.example'}))
        self.assertEqual(error.exception.code,403)

if __name__ == '__main__': unittest.main()

"""Installation tests simulate Ollama responses; no model files are downloaded."""
import io
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from agent47.model_setup import ModelInstaller
from agent47 import server


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.installer = ModelInstaller()

    def stream(self, events):
        return io.BytesIO(b'\n'.join(json.dumps(event).encode() for event in events))

    def test_approval_and_allowlist(self):
        for model, approved in [('qwen3:8b', False), ('qwen3:8b', 'yes'), ('bad:cloud', True), ('custom/unknown', True)]:
            with self.assertRaises(ValueError): self.installer.start(model, approved)
        self.assertEqual(self.installer.snapshot()['status'], 'idle')

    def test_only_one_background_install(self):
        with patch('agent47.model_setup.threading.Thread') as worker:
            self.installer.start('qwen3:4b', True)
            worker.return_value.start.assert_called_once()
            with self.assertRaises(ValueError): self.installer.start('qwen3:8b', True)

    def test_streaming_install_checks_model_before_success(self):
        events = [{'status': 'pulling manifest'}, {'status': 'pulling layer', 'digest': 'one', 'total': 100, 'completed': 50}, {'status': 'success'}]
        with patch('agent47.model_setup.urllib.request.urlopen', return_value=self.stream(events)) as pull, \
             patch('agent47.model_setup.ollama', return_value={'capabilities': ['tools']}) as show:
            self.installer.download('qwen3:4b')
            request = pull.call_args.args[0]
            self.assertEqual(request.full_url, 'http://127.0.0.1:11434/api/pull')
            self.assertEqual(json.loads(request.data), {'model': 'qwen3:4b', 'stream': True})
            show.assert_called_once_with('show', {'model': 'qwen3:4b'})
        self.assertEqual(self.installer.snapshot()['status'], 'success')

    def test_error_and_incomplete_stream_allow_retry(self):
        for events in [[{'error': 'not enough disk space'}], [{'status': 'pulling manifest'}]]:
            with patch('agent47.model_setup.urllib.request.urlopen', return_value=self.stream(events)):
                self.installer.download('qwen3:4b')
            self.assertEqual(self.installer.snapshot()['status'], 'error')
            with patch('agent47.model_setup.threading.Thread'):
                self.installer.start('qwen3:4b', True)
            self.assertEqual(self.installer.snapshot()['status'], 'downloading')

    def test_cloud_or_no_tools_not_reported_ready(self):
        for info in [{'capabilities': []}, {'capabilities': ['tools'], 'remote_host': 'cloud.example'}]:
            with patch('agent47.model_setup.urllib.request.urlopen', return_value=self.stream([{'status': 'success'}])), \
                 patch('agent47.model_setup.ollama', return_value=info):
                self.installer.download('qwen3:4b')
            self.assertEqual(self.installer.snapshot()['status'], 'error')


class SetupHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()

    def call(self, path, body=None, authenticated=True):
        headers = {'X-Agent47-Token': server.TOKEN} if authenticated else {}
        request = Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(request) as response: return json.load(response)

    def test_empty_library_and_options_available_without_workspace(self):
        with patch('agent47.server.ollama', return_value={'models': []}), patch('agent47.server.SESSION', None):
            self.assertEqual(self.call('/api/models', {})['models'], [])
            self.assertEqual(len(self.call('/api/setup')['options']), 2)

    def test_install_requires_token_and_approval(self):
        for auth, body, status in [(False, {'model': 'qwen3:4b', 'approved': True}, 403), (True, {'model': 'qwen3:4b'}, 400)]:
            with patch('agent47.server.SESSION', None), self.assertRaises(HTTPError) as error:
                self.call('/api/models/install', body, authenticated=auth)
            self.assertEqual(error.exception.code, status)

    def test_install_routes_explicit_choice(self):
        with patch('agent47.server.SESSION', None), patch.object(server.INSTALLER, 'start') as install:
            self.assertTrue(self.call('/api/models/install', {'model': 'qwen3:4b', 'approved': True})['ok'])
            install.assert_called_once_with('qwen3:4b', True)

    def test_busy_install_blocks_opening_workspace(self):
        with patch.object(server.INSTALLER, 'snapshot', return_value={'status': 'downloading'}), self.assertRaises(HTTPError) as error:
            self.call('/api/project', {'path': '/tmp', 'model': 'qwen3:8b'})
        self.assertEqual(error.exception.code, 400)

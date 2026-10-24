"""Lifecycle tests use mocks or disposable processes, never the user's live services."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agent47 import launcher


class LauncherTests(unittest.TestCase):
    def test_start_reuses_services_without_duplicates(self):
        with patch.object(Path, 'exists', return_value=True), \
             patch.object(launcher, 'listener', side_effect=[11, 22]), \
             patch.object(launcher, 'is_agent', return_value=True), \
             patch.object(launcher, 'request', return_value={}), \
             patch.object(launcher, 'spawn') as spawn, \
             patch.object(launcher.webbrowser, 'open') as browser:
            launcher.start(open_browser=False)
            spawn.assert_not_called()
            browser.assert_not_called()

    def test_start_new_services_disables_cloud_and_waits_for_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / ('.venv/Scripts/python.exe' if launcher.WINDOWS else '.venv/bin/python')
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(launcher, 'ROOT', root), \
                 patch.object(launcher, 'listener', return_value=None), \
                 patch.object(launcher, 'spawn') as spawn, \
                 patch.object(launcher, 'ollama_executable', return_value='ollama'), \
                 patch.object(launcher, 'wait_ready') as ready:
                launcher.start(open_browser=False)
                self.assertEqual(spawn.call_count, 2)
                self.assertEqual(ready.call_count, 2)
                for call in spawn.call_args_list:
                    self.assertEqual(call.args[2]['OLLAMA_NO_CLOUD'], '1')
                    self.assertEqual(call.args[2]['OLLAMA_HOST'], '127.0.0.1:11434')

    def test_stop_leaves_unrelated_server_alone(self):
        with patch.object(launcher, 'listener', side_effect=[11, 22]), \
             patch.object(launcher, 'is_agent', return_value=False), \
             patch.object(launcher, 'stop_tree') as stop:
            with self.assertRaisesRegex(RuntimeError, 'nothing was stopped'):
                launcher.stop()
            stop.assert_not_called()

    def test_stop_leaves_unknown_runtime_alone(self):
        with patch.object(launcher, 'listener', side_effect=[11, 22]), \
             patch.object(launcher, 'is_agent', return_value=True), \
             patch.object(launcher, 'is_ollama', return_value=False), \
             patch.object(launcher, 'stop_tree') as stop:
            with self.assertRaisesRegex(RuntimeError, 'nothing was stopped'):
                launcher.stop()
            stop.assert_not_called()

    def test_stop_cancels_task_then_stops_verified_services(self):
        with patch.object(launcher, 'listener', side_effect=[11, 22, None, None]), \
             patch.object(launcher, 'is_agent', return_value=True), \
             patch.object(launcher, 'is_ollama', return_value=True), \
             patch.object(launcher, 'request', return_value={'token': 'test-token'}) as request, \
             patch.object(launcher, 'stop_tree') as stop:
            launcher.stop()
            request.assert_any_call(launcher.URL + '/api/stop', {}, 'test-token')
            self.assertEqual([c.args[0] for c in stop.call_args_list], [11, 22])

    def test_process_shutdown_keeps_unrelated_process_alive(self):
        # Only these disposable sleepers can be terminated by this test.
        owned = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(61)'])
        try:
            launcher.stop_tree(owned.pid)
            owned.wait(timeout=5)
            self.assertIsNone(unrelated.poll())
        finally:
            for process in (owned, unrelated):
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)

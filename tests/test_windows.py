"""Container command construction can be checked without Docker installed."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from agent47.core import run_windows_command
from agent47 import launcher


class WindowsTests(unittest.TestCase):
    def test_container_restrictions_and_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git').mkdir()
            for approved in (False, True):
                process = Mock(returncode=0)
                with patch('agent47.core.subprocess.Popen', return_value=process) as spawn:
                    result = run_windows_command(root, ['python3', '-m', 'unittest', 'discover'], approved)
                args = spawn.call_args.args[0]
                self.assertEqual(result['exit_code'], 0)
                for flag in ['--network=none', '--read-only', '--pull=never', '--cap-drop=ALL']:
                    self.assertIn(flag, args)
                mount = next(a for a in args if 'target=/workspace' in a)
                self.assertEqual(mount.endswith(',readonly'), not approved)
                self.assertTrue(any('target=/workspace/.git,readonly' in a for a in args))
                self.assertEqual(args[-4:], ['python3', '-m', 'unittest', 'discover'])

    def test_missing_docker_fails_closed(self):
        with patch('agent47.core.subprocess.Popen', side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ValueError, 'Docker Desktop'):
                run_windows_command(Path.cwd(), ['python3'], True)

    def test_timeout_removes_container(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired('docker', 90), 0]
        with patch('agent47.core.subprocess.Popen', return_value=process), patch('agent47.core.subprocess.run') as cleanup:
            result = run_windows_command(Path.cwd(), ['python3'], False)
        self.assertIn('exceeded', result['error'])
        self.assertEqual(cleanup.call_args.args[0][:3], ['docker', 'rm', '-f'])
        process.kill.assert_called_once()

    def test_windows_identity_requires_same_checkout(self):
        process = Mock()
        process.cmdline.return_value = ['python.exe', '-m', 'agent47.server']
        process.cwd.return_value = str(launcher.ROOT)
        with patch.object(launcher, 'WINDOWS', True), patch.object(launcher, 'windows_process', return_value=process):
            self.assertTrue(launcher.is_agent(42))
            process.cwd.return_value = str(launcher.ROOT.parent)
            self.assertFalse(launcher.is_agent(42))

    def test_missing_ollama_has_setup_instructions(self):
        with patch.object(launcher, 'WINDOWS', True), patch.object(launcher.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'https://ollama.com/download/windows'):
                launcher.ollama_executable({})

    def test_ollama_standard_windows_location(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / 'Programs/Ollama/ollama.exe'
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.object(launcher, 'WINDOWS', True), patch.object(launcher.shutil, 'which', return_value=None):
                self.assertEqual(launcher.ollama_executable({'LOCALAPPDATA': directory}), str(executable))

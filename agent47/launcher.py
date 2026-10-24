"""Start and stop local services for the macOS and Windows shortcuts."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import time
import urllib.request
import webbrowser

WINDOWS = os.name == "nt"
if WINDOWS:
    import psutil
    PROCESS_ERRORS = (psutil.Error,)
else:
    PROCESS_ERRORS = ()

def windows_process(pid):
    import psutil
    return psutil.Process(pid)


ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:8747'
OLLAMA_URL = 'http://127.0.0.1:11434'


def request(url, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Agent47-Token'] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=2) as response:
        return json.load(response)


def listener(port):
    if WINDOWS:
        import psutil
        pids = {c.pid for c in psutil.net_connections(kind='tcp')
                if c.status == psutil.CONN_LISTEN and c.laddr.port == port}
        if None in pids:
            raise RuntimeError('Cannot identify the listener; no service was changed.')
        if len(pids) > 1:
            raise RuntimeError(f'More than one process listens on port {port}; stop them manually.')
        return next(iter(pids)) if pids else None
    # Find only processes listening on the service port, never every Python process.
    result = subprocess.run(['/usr/sbin/lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN', '-t'],
                            capture_output=True, text=True)
    pids = set(result.stdout.split())
    if len(pids) > 1:
        raise RuntimeError(f'More than one process listens on port {port}; stop them manually.')
    return int(next(iter(pids))) if pids else None


def command(pid):
    if WINDOWS:
        import psutil
        try:
            return subprocess.list2cmdline(windows_process(pid).cmdline())
        except psutil.NoSuchProcess:
            return ''
    result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return result.stdout.strip()


def is_agent(pid):
    if WINDOWS:
        process = windows_process(pid)
        args = process.cmdline()
        return (any(args[i:i + 2] == ['-m', 'agent47.server'] for i in range(len(args)))
                and Path(process.cwd()).resolve() == ROOT)
    args = shlex.split(command(pid))
    # Also check the working directory so another Agent47 checkout is not stopped.
    cwd = subprocess.run(['/usr/sbin/lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'],
                         capture_output=True, text=True).stdout.splitlines()
    directory = next((line[1:] for line in cwd if line.startswith('n')), '')
    return (any(args[i:i + 2] == ['-m', 'agent47.server'] for i in range(len(args)))
            and bool(directory) and Path(directory).resolve() == ROOT)


def is_ollama(pid):
    if WINDOWS:
        args = windows_process(pid).cmdline()
        return len(args) == 2 and Path(args[0]).name.lower() == 'ollama.exe' and args[1] == 'serve'
    args = shlex.split(command(pid))
    return len(args) >= 2 and Path(args[0]).name == 'ollama' and args[1] == 'serve'


def wait_ready(url, process):
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError('Service exited during startup. Check the logs in .agent47/.')
        try:
            request(url)
            return
        except (OSError, ValueError):
            time.sleep(0.5)
    raise RuntimeError('Service did not become ready within 30 seconds. Check .agent47/ logs.')


def spawn(argv, log, env):
    # Detach services from the shortcut's Terminal window. Closing that window is safe;
    # the Stop shortcut, rather than the browser or Terminal, owns service shutdown.
    with log.open('ab') as output:
        return subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=output, stderr=subprocess.STDOUT,
                                **({'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
                                   if WINDOWS else {'start_new_session': True}))


def ollama_executable(env):
    executable = shutil.which('ollama', path=env.get('PATH'))
    if executable:
        return executable
    if WINDOWS:
        local = env.get('LOCALAPPDATA')
        if local:
            candidate = Path(local) / 'Programs' / 'Ollama' / 'ollama.exe'
            if candidate.is_file():
                return str(candidate)
        raise RuntimeError(
            'Ollama is not installed or could not be found. Install Ollama for Windows '
            'from https://ollama.com/download/windows, reopen the launcher, '
            'and download a model with: ollama pull qwen3:8b')
    raise RuntimeError('Ollama was not found. Install it using the macOS setup in ReadMe.md.')


def start(open_browser=True):
    directory = ROOT / '.agent47'
    directory.mkdir(exist_ok=True)
    python = ROOT / ('.venv/Scripts/python.exe' if WINDOWS else '.venv/bin/python')
    if not python.exists():
        raise RuntimeError('Project Python environment is missing. Follow ReadMe.md first.')
    env = dict(os.environ, OLLAMA_NO_CLOUD='1', OLLAMA_HOST='127.0.0.1:11434')
    if not WINDOWS:
        env['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + env.get('PATH', '/usr/bin:/bin')
    # Reuse existing healthy services; double-clicking Start twice must not create duplicates.
    pid = listener(11434)
    if pid is None:
        runtime = spawn([ollama_executable(env), 'serve'], directory / 'ollama.log', env)
        wait_ready(OLLAMA_URL + '/api/tags', runtime)
    else:
        request(OLLAMA_URL + '/api/tags')
        print('Reusing the existing Ollama server; its environment is unchanged.')
    pid = listener(8747)
    if pid is None:
        server = spawn([str(python), '-m', 'agent47.server'], directory / 'server.log', env)
        wait_ready(URL + '/api/bootstrap', server)
    elif not is_agent(pid):
        raise RuntimeError('Port 8747 belongs to a different process or checkout. It was left running.')
    else:
        request(URL + '/api/bootstrap')
    if open_browser:
        webbrowser.open(URL)
    print(f'Agent47 is running: {URL}')
    print('You may close this Terminal window. Use the Stop-Agent47 shortcut to shut down.')


def stop_tree(pid):
    if WINDOWS:
        import psutil
        try:
            process = windows_process(pid)
            processes = process.children(recursive=True)[::-1] + [process]
        except psutil.NoSuchProcess:
            return
        # Process objects retain creation times, protecting against PID reuse.
        for target in processes:
            try:
                target.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(processes, timeout=4)
        for target in alive:
            try:
                target.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alive, timeout=4)
        return
    # Stop descendants too: a model runner or project test can outlive its parent otherwise.
    snapshot = subprocess.run(['/bin/ps', '-axo', 'pid=,ppid='], capture_output=True, text=True).stdout
    children = {}
    for line in snapshot.splitlines():
        child, parent = map(int, line.split())
        children.setdefault(parent, []).append(child)
    ordered = []

    def visit(parent):
        for child in children.get(parent, []):
            visit(child)
        ordered.append((parent, command(parent)))

    visit(pid)
    for target, original in ordered:
        if original and command(target) == original:
            try:
                os.kill(target, signal.SIGTERM)
            except ProcessLookupError:
                pass
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        if not any(original and command(target) == original for target, original in ordered):
            return
        time.sleep(0.1)
    # Escalate only for the same processes we already identified, not unrelated services.
    for target, original in ordered:
        if original and command(target) == original:
            try:
                os.kill(target, signal.SIGKILL)
            except ProcessLookupError:
                pass


def stop():
    server = listener(8747)
    runtime = listener(11434)
    # Validate identities before stopping anything. A desktop Ollama app/service may
    # manage its own runtime; in that case ask the user to quit it rather than guessing.
    if server and not is_agent(server):
        raise RuntimeError('Port 8747 belongs to a different process or checkout; nothing was stopped.')
    if runtime and not is_ollama(runtime):
        raise RuntimeError('Ollama is managed by another application. Quit it there; nothing was stopped.')
    if server:
        try:
            token = request(URL + '/api/bootstrap')['token']
            request(URL + '/api/stop', {}, token)
        except (OSError, ValueError, KeyError):
            pass
        stop_tree(server)
    if runtime:
        stop_tree(runtime)
    if listener(8747) or listener(11434):
        raise RuntimeError('A service is still listening or restarted automatically. Check its service manager.')
    print('Agent47 and Ollama are stopped. The downloaded model and project files remain installed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        start(not args.no_browser) if args.action == 'start' else stop()
    except (OSError, ValueError, RuntimeError) + PROCESS_ERRORS as exc:
        print(f'Agent47: {exc}')
        raise SystemExit(1)


if __name__ == '__main__':
    main()

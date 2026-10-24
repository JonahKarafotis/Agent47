"""User-approved local model downloads, independent of the coding agent's tools."""
import json
import threading
import urllib.request
from .core import ollama

# Keep browser installs limited to known local, tool-capable models. No cloud tags,
# arbitrary registries, shell commands, or model-selected installations are accepted.
MODELS = [
    {'name': 'qwen3:8b', 'label': 'Qwen3 8B — tested on our 16 GB M4',
     'size': 'About 5.2 GB', 'description': 'The model used for Agent47’s initial coding test. Uses more memory.',
     'source': 'https://ollama.com/library/qwen3:8b'},
    {'name': 'qwen3:4b', 'label': 'Qwen3 4B — smaller download',
     'size': 'About 2.5 GB', 'description': 'A lighter option. Coding quality and speed depend on your machine.',
     'source': 'https://ollama.com/library/qwen3:4b'},
]


class ModelInstaller:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = {'status': 'idle', 'model': None, 'message': '', 'completed': 0, 'total': 0}

    def snapshot(self):
        # Return a copy so HTTP serialization cannot observe partially updated progress.
        with self.lock:
            return dict(self.state)

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def start(self, model, approved):
        if approved is not True:
            raise ValueError('Approve the model download before installation.')
        if model not in {item['name'] for item in MODELS}:
            raise ValueError('Choose one of the offered local models.')
        with self.lock:
            if self.state['status'] == 'downloading':
                raise ValueError('A model download is already running. Wait for it to finish.')
            self.state = {'status': 'downloading', 'model': model, 'message': 'Connecting to Ollama…',
                          'completed': 0, 'total': 0}
        threading.Thread(target=self.download, args=(model,), daemon=True).start()

    def download(self, model):
        try:
            request = urllib.request.Request('http://127.0.0.1:11434/api/pull',
                data=json.dumps({'model': model, 'stream': True}).encode(),
                headers={'Content-Type': 'application/json'})
            success = False
            digest = None
            # Ollama streams one JSON object per line; each download layer has its own
            # total/completed counts. Read in a worker so the UI can keep polling.
            with urllib.request.urlopen(request, timeout=120) as response:
                for line in response:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get('error'):
                        raise ValueError(event['error'])
                    current = event.get('digest')
                    if current != digest:
                        self.update(completed=0, total=0)
                        digest = current
                    self.update(message=event.get('status', 'Downloading…'),
                                completed=event.get('completed', 0), total=event.get('total', 0))
                    if event.get('status') == 'success':
                        success = True
            if not success:
                raise ValueError('The download ended before Ollama confirmed success. Try again to resume.')
            # A completed transfer is usable only if the installed model supports tools locally.
            info = ollama('show', {'model': model})
            if info.get('remote_host') or info.get('remote_model') or 'tools' not in info.get('capabilities', []):
                raise ValueError('The downloaded model is not a supported local tool-calling model.')
            self.update(status='success', message='Model installed. Choose your project and open the workspace.')
        except Exception as exc:
            self.update(status='error', message=f'{exc} Check Ollama, internet access and free disk space, then retry. Partial downloads may resume.')


INSTALLER = ModelInstaller()

#!/bin/zsh
set -eu
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export OLLAMA_NO_CLOUD=1
export OLLAMA_HOST=127.0.0.1:11434
if ! command -v ollama >/dev/null; then
  echo 'Ollama is missing. See SETUP.md.'
  exit 1
fi
mkdir -p .agent47
runtime_pid=''
cleanup() { if [[ -n "$runtime_pid" ]]; then kill "$runtime_pid" 2>/dev/null || true; fi }
trap cleanup EXIT
if ! .venv/bin/python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=2)' >/dev/null 2>&1; then
  ollama serve >.agent47/ollama.log 2>&1 &
  runtime_pid=$!
fi
printf 'Open http://127.0.0.1:8747 in your browser. Keep this window open.\n'
.venv/bin/python -m agent47.server

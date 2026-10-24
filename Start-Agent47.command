#!/bin/zsh
# Stop on command failures or unset variables, then run from this script's directory.
set -eu
cd "${0:A:h}"
# Include common Homebrew locations, even when Finder opens a minimal shell environment.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# These settings apply to the Ollama process this launcher starts.
export OLLAMA_NO_CLOUD=1
export OLLAMA_HOST=127.0.0.1:11434
if ! command -v ollama >/dev/null; then
  echo 'Ollama is missing. See SETUP.md.'
  exit 1
fi
mkdir -p .agent47
# Track only a runtime we start ourselves; leave an existing Ollama server running.
runtime_pid=''
cleanup() { if [[ -n "$runtime_pid" ]]; then kill "$runtime_pid" 2>/dev/null || true; fi }
trap cleanup EXIT
# Probe the local API before deciding whether a new runtime is needed.
if ! .venv/bin/python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=2)' >/dev/null 2>&1; then
  ollama serve >.agent47/ollama.log 2>&1 &
  runtime_pid=$!
fi
# The server stays in the foreground; Control-C exits and runs the cleanup trap.
printf 'Open http://127.0.0.1:8747 in your browser. Keep this window open.\n'
.venv/bin/python -m agent47.server

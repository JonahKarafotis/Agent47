#!/bin/zsh
# Stop the app and the local Ollama runtime, including active child processes.
set -eu
cd "${0:A:h}"
exec .venv/bin/python -m agent47.launcher stop

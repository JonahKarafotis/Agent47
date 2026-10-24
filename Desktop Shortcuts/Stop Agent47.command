#!/bin/zsh
# This stops both Agent47 and its local Ollama server. Other Ollama clients disconnect too.
set -eu
project_dir='/Users/jonahkarafotis/Desktop/MyDev/Agent47'
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  printf 'Agent47 was not found at %s. Update project_dir in this shortcut.\n' "$project_dir"
  exit 1
fi
cd "$project_dir"
exec .venv/bin/python -m agent47.launcher stop

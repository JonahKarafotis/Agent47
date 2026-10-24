#!/bin/zsh
# Repository launcher; movable Desktop copies use the absolute repository path instead.
set -eu
cd "${0:A:h}"
exec .venv/bin/python -m agent47.launcher start

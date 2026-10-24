# Initial validation — October 23, 2026

Environment: Apple M4, 16 GB memory, macOS. Ollama 0.40.9, local qwen3:8b, Python environment with pypdf 6.21.2. Ollama was started on loopback with OLLAMA_NO_CLOUD=1 and confirmed cloud features disabled in its startup log.

- 12 automated tests passed: file boundaries and symlinks, protected paths, backups, deletion approval, fresh-read requirements, command approval, command filesystem/network isolation, PDF text extraction, mocked tool iteration, and local HTTP access protections.
- A live task went through the app's HTTP API and the real Ollama model. The model read both files in examples/demo, changed `return a - b` to `return a + b`, then ran `python3 -m unittest discover`. Both demo tests passed. The tests were not edited.
- The official model blob's SHA-256 digest was verified before registration with Ollama. Small-chunk downloading was used after the runtime's parallel download connections stalled.
- Public Bing RSS search returned real titles, snippets and URLs without a paid API key. DuckDuckGo HTML was blocked during validation and is not used.
- The browser interface was opened and inspected. The real task's tool log and final result are visible there.

Not validated: broad coding quality across all five requested languages, long tasks, hostile repositories, scanned PDFs, or Rust/.NET builds. Rust and .NET were not present on the machine and were not installed. C/C++ compiler tools were detected, but live C/C++ compilation was not part of this smoke test.

This is a first working prototype. See SETUP.md for capabilities, isolation limits and startup instructions.

## Windows live validation (2026-10-23)

- Launched Agent47 with `.venv/Scripts/python.exe -m agent47.launcher start --no-browser`, using the existing Ollama installation. A second launch reused both services successfully. The browser opened at http://127.0.0.1:8747 and rendered the interface.
- Downloaded and verified `qwen3:8b` through Ollama. The model appeared in the app dropdown and passed workspace capability validation.
- Submitted a real repair task in the browser against an isolated `.agent47/windows-smoke` project. Both tests initially failed. The model read both files and identified the bug, but initially returned prose without writing; an explicit follow-up caused `write_file` and a confirming `read_file` to execute successfully.
- Verified the saved change from subtraction to addition, a backup containing the original, and unchanged test-file SHA-256. Both repaired-project tests passed when run separately on the host. This did not validate in-app command execution.
- Application suite: 23 passed, 1 macOS-only skip (24 total). Existing demo suite: 2 passed. Live static assets returned HTTP 200; an unauthenticated state request returned HTTP 403.
- Docker Desktop was absent. Confirmed command execution reports the missing dependency and does not fall back to host execution. Live container execution remains unverified. macOS was not rerun on this Windows machine.
- Earlier sandboxed checks incorrectly suggested Ollama was absent; inspection with normal system access confirmed its existing standard Windows installation. No Ollama upgrade was needed.


## Guided model setup integrated on Windows

Merged origin/main commit 2ae14d6 into windows-support, preserving the Windows launcher, command isolation and existing macOS behavior. The combined application suite passed 32 tests with one macOS-only skip (33 total).

Restarted the local Agent47 server and verified the new Install a local model panel in the browser. Both Qwen3 8B and 4B options appeared. Clicking Approve & download for the existing qwen3:8b model exercised the real Ollama pull endpoint, progress display, local capability validation and model selection, ending in the installed state. Existing model data was reused; this check did not perform a fresh multi-gigabyte transfer. Docker execution remains unverified on this machine.

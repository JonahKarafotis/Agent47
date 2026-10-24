# Initial validation — October 23, 2026

Environment: Apple M4, 16 GB memory, macOS. Ollama 0.40.9, local qwen3:8b, Python environment with pypdf 6.21.2. Ollama was started on loopback with OLLAMA_NO_CLOUD=1 and confirmed cloud features disabled in its startup log.

- 12 automated tests passed: file boundaries and symlinks, protected paths, backups, deletion approval, fresh-read requirements, command approval, command filesystem/network isolation, PDF text extraction, mocked tool iteration, and local HTTP access protections.
- A live task went through the app's HTTP API and the real Ollama model. The model read both files in examples/demo, changed `return a - b` to `return a + b`, then ran `python3 -m unittest discover`. Both demo tests passed. The tests were not edited.
- The official model blob's SHA-256 digest was verified before registration with Ollama. Small-chunk downloading was used after the runtime's parallel download connections stalled.
- Public Bing RSS search returned real titles, snippets and URLs without a paid API key. DuckDuckGo HTML was blocked during validation and is not used.
- The browser interface was opened and inspected. The real task's tool log and final result are visible there.

Not validated: broad coding quality across all five requested languages, long tasks, hostile repositories, scanned PDFs, or Rust/.NET builds. Rust and .NET were not present on the machine and were not installed. C/C++ compiler tools were detected, but live C/C++ compilation was not part of this smoke test.

This is a first working prototype. See SETUP.md for capabilities, isolation limits and startup instructions.

# Agent47

Agent47 is a local coding assistant with a browser interface. It connects to a downloaded Ollama model, works in one explicitly selected project folder, and can inspect code, edit files, read TXT/PDF documents, run checks, and search the public web.

The current release is a working prototype, validated on an Apple M4 MacBook Pro with 16 GB memory. It is intended for personal development on trusted projects. Python, C, C++, C#, and Rust are the initial target languages; building and testing them requires their respective tools to be installed separately.

## What stays local

Inference, project files, document extraction, backups, and conversation state are processed on your computer. The app contacts Ollama at `127.0.0.1:11434` and rejects cloud model metadata. It serves its interface at `127.0.0.1:8747`, with no hosted frontend assets or paid AI API dependency.

Public web search is the exception: search terms are sent to Bing's public RSS endpoint, which returns titles, snippets, and links. The agent is instructed to use generic queries and avoid sending private project content without permission. That instruction is a model policy, not a guaranteed data-loss prevention system. Coding and document tools can work offline once the model and dependencies are downloaded; web search needs internet access.

## Requirements

- macOS with `/usr/bin/sandbox-exec` for command execution. Other operating systems are not validated, and command execution is disabled when that tool is absent.
- Python 3.11 or newer.
- Ollama and a downloaded model that supports tool calling.
- Enough disk space and memory for the model. The initial `qwen3:8b` download is about 5.2 GB, with additional memory needed during inference.
- Language tools for the projects you want to build: Python, Clang/GCC, the .NET SDK, or Rust/Cargo as appropriate. Agent47 does not install these tools for you.

The Python server uses the standard library. Its one packaged dependency, `pypdf`, provides local text extraction from PDFs. The frontend uses plain HTML, CSS, and JavaScript; there is no Node.js build step.

## First-time setup

Clone or download this repository, open a terminal in its directory, and create the project environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Install Ollama using Homebrew:

```sh
brew install ollama
```

Alternatively, install the [official macOS application](https://ollama.com/download/mac). Only one Ollama server should use port 11434 at a time.

For the Homebrew installation, start Ollama in a separate terminal with cloud features disabled:

```sh
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

Keep that terminal open. In another terminal, download the initial model:

```sh
ollama pull qwen3:8b
```

For the macOS application instead, run `launchctl setenv OLLAMA_NO_CLOUD 1`, fully quit Ollama, then reopen it before downloading the model. This changes the environment for subsequently launched applications; it does not reconfigure an already running Ollama process.

`qwen3:8b` is the initial tested model, not a promise of performance on every machine. You can select another downloaded, tool-capable local model from the interface. Smaller models may use less memory but differ in coding and tool-use reliability.

## Start Agent47

After first-time setup, double-click `Start-Agent47.command`, or run it from the repository directory:

```sh
./Start-Agent47.command
```

The launcher uses `.venv`, starts Ollama if it cannot reach an existing instance, and starts the app. It sets cloud features off for the Ollama process it launches; it does not change an existing Ollama server's environment. Runtime logs from an Ollama process started by the launcher are written to `.agent47/ollama.log`.

Open [http://127.0.0.1:8747](http://127.0.0.1:8747) yourself and keep the launcher terminal open. Use this exact address rather than `localhost`, because the server validates the Host header. To stop the app, press Control-C in that terminal. The launcher also stops the Ollama process if it started that process.

If Ollama is already running, you can start just the app:

```sh
.venv/bin/python -m agent47.server
```

## Use a workspace

1. Refresh the model list and select a local model.
2. Enter the absolute path of a trusted project folder, such as `/Users/you/projects/my-app`.
3. Click **Open workspace**. The agent can access one selected project at a time.
4. Start with a read-only task: “Inspect this project and summarize its structure. Do not change files yet.”
5. Give a small implementation task and review the tool log, file diffs, and test output.
6. Approve or deny actions when an approval card appears. Each approval applies to that action only.

Documents must be inside the selected project folder. Put TXT or text-based PDF files there and ask the agent to read or summarize them. Scanned PDFs need OCR, which is not included.

Opening a workspace again, including the same folder, starts a new conversation. Restarting the server also clears the chat and activity log. File edits and backups remain on disk.

The included `examples/demo` folder is a small Python project you can select for exploration. Its calculator and two tests are already correct following the initial live validation. Ask the agent to explain the code and run its tests before trying a change in your own project.

## Permissions and command execution

The agent may list, search, read, create, and replace project files automatically. Existing files must have been fully read and must still match that read before the file-writing tool can replace them. Common credential paths, `.env*` files, and internal folders such as `.git`, `.agents`, and `.codex` are excluded from the file tools.

File deletion always requires approval. Most commands also require approval, including compiler invocations and Git commands. Only these exact argument lists run automatically:

```text
python3 -m unittest discover
cargo check
cargo test
dotnet test --no-restore
```

Adding flags, such as `-v`, makes the command require approval. Commands run as argument lists without a shell unless you explicitly approve a shell invocation.

All commands, including approved ones, run under a macOS sandbox:

- Network access is denied.
- Writes are limited to the selected project and a temporary directory, with writes to selected internal folders blocked.
- Home-directory reads are restricted to the project, temporary directory, and common Rust/.NET toolchain locations. System files remain readable.
- Automatic commands additionally cannot unlink files, so some test/build tools may fail when they try to clean up outputs.
- Commands have a 90-second timeout; returned output is capped at 24,000 bytes.

Approval does not remove these restrictions. Dependency installation and Git pushes must currently happen outside the app. Build systems that need other caches, SDK paths, or network access may fail inside the sandbox.

The **Stop** button prevents subsequent agent steps. An in-flight model request or command must finish or time out first; model requests have a five-minute timeout.

## Backups and recovery

Before a file-tool edit or deletion, Agent47 saves the original text under the selected project's `.agent47/backups/<id>/` directory:

- `metadata.json` identifies the file and whether it existed before the action.
- `before.txt` contains its previous text.

To restore an existing file, inspect the metadata and copy `before.txt` back to that file yourself. For a newly created file, the metadata has `existed: false`; restoring the prior state means removing that new file yourself. There is no automatic undo button yet. Command-generated changes do not receive these file-tool backups, so use Git as well.

Backups can contain private source code. Keep `.agent47/` out of version control in each project you select. This repository's `.gitignore` excludes it, along with the Python environment and bytecode caches.

## How it works

```text
Browser interface (127.0.0.1:8747)
    -> Python HTTP server
    -> Session: conversation and bounded tool loop
    -> Ollama native /api/chat (127.0.0.1:11434)
    -> Model requests a tool
    -> Policy checks and approval, when required
    -> Local tool or public web search
    -> Tool result returned to the model
    -> Next step or final answer
```

The model receives tool schemas for file listing, file reading, text search, file writing, deletion, command execution, and web search. It chooses tools; Python executes them and sends their results back to the model. The browser polls session state to display messages, tool inputs/results, diffs, and approval requests. File and web content are treated as untrusted context in the system prompt.

Each task allows up to 16 model iterations. The initial model settings use an 8,192-token context window, a maximum of 3,000 generated tokens per request, and thinking disabled. A conservative 24,000-character serialized conversation budget stops long sessions before another request. Reopen the workspace to reset context when that limit is reached.

This version uses bounded file listing and plain text search for context. Embeddings, vector storage, semantic retrieval/RAG, persistent memory, and multiple specialized agents remain future work from the original project vision.

### Repository map

| Path | Purpose |
| --- | --- |
| `agent47/core.py` | Ollama client, workspace tools, command policy/sandbox, web search, and agent loop |
| `agent47/server.py` | Loopback HTTP server, model/workspace setup, chat, approvals, and stop endpoints |
| `agent47/static/` | Browser interface; no build process required |
| `Start-Agent47.command` | macOS launcher for the local runtime and app |
| `requirements.txt` | Pinned PDF extraction dependency |
| `tests/test_agent.py` | Automated tests for tools, policies, PDF extraction, and HTTP access checks |
| `examples/demo/` | Small Python project for exploration and smoke tests |
| `SETUP.md` | Troubleshooting and operational limits |
| `VALIDATION.md` | Recorded initial test environment and live model results |

## Tests and current limits

Run the application tests from the repository directory:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Run the demo tests separately:

```sh
cd examples/demo
../../.venv/bin/python -m unittest discover -v
```

The application suite includes a mocked Ollama tool cycle and does not require a running model. PDF coverage needs the installed dependency; command sandbox tests require macOS, and HTTP tests need permission to bind a local loopback port. The initial validation passed 12 application tests and a real-model repair task with two passing demo tests; see [VALIDATION.md](VALIDATION.md).

Important implementation limits:

- This is a prototype for trusted projects, not a hardened security boundary for hostile code. Filesystem race attacks are not comprehensively addressed.
- File reads are limited to 5 MB input and 16,000 returned characters. PDF extraction covers the first 100 pages. Existing files longer than the full-read limit cannot be replaced through the normal file-writing workflow.
- File listing stops at 2,000 files; text search returns up to 60 matches and searches the readable prefix of each non-PDF file. `.gitignore` patterns are not generally interpreted; exclusions are the fixed folders and protected names in `core.py`.
- Chat and activity state are in server memory, shared by browser tabs using the same server. There is no persistent chat history, OCR, web-page fetching, or browser automation.
- Public RSS search may be rate limited, blocked, or change format. Model answers and changes still need human review.

For operational help, see [SETUP.md](SETUP.md). Official references: [Ollama chat API](https://docs.ollama.com/api/chat), [Ollama configuration](https://docs.ollama.com/faq), and [the initial model](https://ollama.com/library/qwen3:8b).

## Future direction and license

The longer-term goal remains a free, local development assistant with project indexing, local semantic retrieval, persistent memory, and inspectable planning, coding, and validation workflows. These are roadmap items rather than current capabilities.

This repository has not yet been assigned a license.

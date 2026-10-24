# Agent47 operational notes

For first-time installation, startup commands, architecture, permissions, and repository layout, start with [ReadMe.md](ReadMe.md). This file covers troubleshooting and operational details.

## Ollama is unavailable or no models appear

Check that Ollama is running on `127.0.0.1:11434` and that a local model is downloaded:

```sh
ollama list
```

For a Homebrew installation, start the server in a separate terminal:

```sh
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

Then download the initial model if needed:

```sh
ollama pull qwen3:8b
```

Refresh the model list in Agent47. The app requires tool calling support and rejects cloud model metadata. If a download stalls, retry `ollama pull`; do not treat a partial download as an installed model. The initial setup needed smaller download chunks and verified the final official SHA-256 digest before model registration.

If using the Ollama macOS application, set `OLLAMA_NO_CLOUD=1` in its launch environment and restart it. The Agent47 launcher disables cloud features for an Ollama process it starts, but cannot change the environment of an existing server.

## The interface does not open

Use exactly [http://127.0.0.1:8747](http://127.0.0.1:8747). The Host-header check rejects other hostnames, including `localhost`. The shortcut launches background services, so closing its Terminal window or the browser does not shut them down. Use `Stop-Agent47.command` to stop both services. When you run `.venv/bin/python -m agent47.server` directly instead, keep that terminal open and use Control-C to stop the foreground server.

The launcher normally reuses the existing Agent47 process. If a different process or checkout occupies the port, it reports the conflict and leaves that process alone. Neither port nor runtime URL is configurable through the UI yet.

## The launcher reports a missing environment

Run these commands from the repository directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The launcher requires `.venv/bin/python`. Starting the app with another Python installation may omit the PDF dependency even if it is installed in `.venv`.

## A command fails after approval

Approval does not bypass the sandbox. Commands still cannot use the network or write outside the selected project and temporary directory. Some tools need other cache or SDK paths, and automatic checks cannot unlink files. Inspect the actual tool output before deciding whether a failure is a code bug or an execution restriction.

Install dependencies and perform Git pushes outside the app. Agent47 does not bundle Python, C/C++, Rust, or .NET project toolchains. Rust and .NET were absent during initial validation and were not installed as part of Agent47 setup.

Commands time out after 90 seconds, and only the first 24,000 output bytes are returned. Model requests time out after five minutes. Stop requests take effect between steps, after the current model call or command returns.

## A document is empty or an edit is rejected

PDF extraction works on text-based documents, not scanned pages. Inputs over 5 MB are rejected; extraction covers at most 100 PDF pages and returns up to 16,000 characters.

Existing text files must be completely read before replacement. If the file has changed since that read, read it again. If it exceeds the read limit, use a smaller file or edit it outside the current file tool. Binary files and non-UTF-8 text are not supported by the text editing tools.

## Conversation or project state was lost

Chat, activity, and approvals are held only in server memory. Restarting the server or opening a workspace again resets the conversation. A 24,000-character serialized context budget also stops long conversations; reopen the workspace to start fresh using the current project files.

File-tool backups survive under the selected project's `.agent47/backups/`. Follow the README's recovery instructions. The launcher writes service logs to this repository's `.agent47/ollama.log` and `.agent47/server.log`. Avoid committing either backups or logs.

## Public search is unavailable

Search uses Bing's public RSS endpoint without an API key. It may be blocked, rate limited, return poor matches, or change its response format. Try a simpler query or search manually. The tool retrieves titles, snippets, and links; it does not fetch full pages.

Queries leave the machine. Generic queries are encouraged by the model prompt, but that rule is not a guaranteed safeguard against private content appearing in a query. Inspect the visible search log and keep sensitive material out of search requests.

## Security scope

Use trusted projects and review generated changes. Resolved path checks and macOS command isolation reduce accidental access, but the prototype is not hardened against hostile repositories or concurrent filesystem changes. Command-generated modifications do not get file-tool backups. Use version control and keep `.agent47/` ignored in each selected project.

For recorded test results, see [VALIDATION.md](VALIDATION.md).

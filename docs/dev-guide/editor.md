# Monaco Editor

REvoDesign provides a [Monaco Editor](https://microsoft.github.io/monaco-editor/)
(the editor that powers VS Code) for editing YAML configuration files with
syntax highlighting, code completion, and intention guides. The editor is served
as a **local web app** by a FastAPI backend and opened in the system's default
web browser.

## Why Monaco?

Plain text editors lack syntax highlighting and intention guides, making YAML
config editing error-prone (indentation errors, missing quotes, invalid keys).
Monaco provides a VS Code-quality editing experience inside PyMOL without
requiring an external editor.

## Architecture

```
┌──────────────────────────────────────────┐
│  System Web Browser                      │
│  ┌────────────────────────────────────┐  │
│  │  Monaco Editor (HTML/JS)           │  │
│  │  - YAML syntax highlighting        │  │
│  │  - Code completion                 │  │
│  │  - Intention guides                │  │
│  └──────────────┬─────────────────────┘  │
│                 │ HTTP (localhost)        │
│  ┌──────────────▼─────────────────────┐  │
│  │  FastAPI Server (uvicorn)          │  │
│  │  - File read/write (whitelisted)   │  │
│  │  - Token authentication            │  │
│  │  - Rate limiting                   │  │
│  │  - Static file serving             │  │
│  └──────────────┬─────────────────────┘  │
│                 │                        │
│  ┌──────────────▼─────────────────────┐  │
│  │  ConfigStore (in-memory)           │  │
│  │  - Server config (host, port)      │  │
│  │  - File whitelist                  │  │
│  │  - Auth token                      │  │
│  │  - HTML directory path             │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Module Layout

```
src/REvoDesign/editor/
├── __init__.py
├── README.md
└── monaco/
    ├── __init__.py
    ├── monaco.py       # MonacoEditorManager — download, install, bootstrap
    ├── server.py       # FastAPI server — API endpoints, auth, rate limiting
    ├── config.py       # ConfigStore — in-memory config for editor backend
    └── static/
        └── index.html  # Monaco editor HTML template
```

## MonacoEditorManager

`MonacoEditorManager` (in `monaco.py`) handles the lifecycle of the Monaco
editor installation:

1. **Download** — Fetches a specific version of `monaco-editor` from the npm
   registry (`registry.npmjs.org`) as a `.tgz` tarball.
2. **Extract** — Unpacks into `$USER_DATA_DIR/monaco/`.
3. **Template copy** — Copies `static/index.html` into the extracted editor
   directory, customizing it for the local backend.
4. **Version management** — Supports `version="latest"` or a specific tag.
   `no_upgrade=True` skips re-download if already installed.

The manager is created and invoked by `ensure_monaco()` which is called inside
the FastAPI `lifespan` context manager (at server startup) and from
`edit_file_with_monaco()` (in `monaco.py`).

## FastAPI Server

The server (`monaco/server.py`) provides a REST API for the Monaco frontend:

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/editor` | Serve Monaco editor HTML |
| `GET` | `/load_file?file_path=...&token=...` | Read a whitelisted file |
| `POST` | `/save_file?token=...` | Write a whitelisted file (`file_path` in JSON body) |
| `GET` | `/favicon.svg` | Logo |

### Security

- **Token authentication**: A random 32-byte `SECRET_TOKEN` is generated on
  first launch, stored in `ConfigStore`. All mutating requests must include
  `token=<token>` as a query parameter.
- **Rate limiting**: 5 failed attempts per IP within a 60-second window
  triggers a 429 block.
- **File whitelist**: Only files explicitly listed in the whitelist can be
  read or written. Whitelist sources:
  - **Editable**: All config files from `application.menu.all_config_files`
    (the same list shown in the File menu).
  - **Readonly**: Log files (resolved from `logger.yaml` handlers'
    `filename` keys, which may use `"AUTO"` and resolve via `user_log_path()`).
- **`no_token` mode**: Set `editor.backend.no_token: true` in config to
  disable authentication (for local-only trusted environments).

### Lifecycle

The server uses FastAPI's `lifespan` context manager:

1. On startup: ensure Monaco is downloaded, mount static files, load
   whitelists, initialize token.
2. On shutdown: destroy token, clear whitelist from ConfigStore.

The server is managed through the `StoresWidget` server-switch system (see
[Architecture](architecture.md)). It starts/stops alongside other REvoDesign
services.

## ConfigStore

`ConfigStore` (in `config.py`) is a lightweight in-memory key-value store for
the editor backend. It holds:

- `editor.token` — authentication token
- `editor.backend.html_dir` — path to the Monaco HTML directory
- `editor.backend.no_token` — whether to skip auth
- `monaco.file_whitelist.editable` — writable file paths
- `monaco.file_whitelist.readonly` — read-only file paths

## Server Control

The editor server is controlled via `ServerControlAbstract` in
`REvoDesign.basic.server_monitor`. The server switch in the REvoDesign UI
is managed through `StoresWidget().server_switches["Editor_Backend"]` and
the `menuEditor_Backend` menu actions (`actionStartEditor`/`actionStopEditor`).

The server lifecycle is managed by `StoresWidget`, which tracks the running
`WorkerThread` and can abort/restart the server on configuration changes.

## Usage

1. Open REvoDesign in PyMOL.
2. Click **Edit > Open Config Editor** or select a config file from the
   **File** menu.
3. The Monaco editor opens in your default web browser with the selected YAML file.
4. Edit with syntax highlighting, save (`Ctrl+S`), and close.
5. Click **File > Reconfigure** to apply the changes.

# Package Manager

The REvoDesign Package Manager is a standalone PyMOL plugin that installs,
upgrades, and removes REvoDesign itself. It is **not** distributed on PyPI --
the manager script is installed as a PyMOL plugin from a GitHub Gist URL, and
it manages REvoDesign through pip under the hood.

```python
# The manager serves as both:
# 1. A PyMOL plugin entry point (when __file__ != "package_manager.py")
# 2. A runtime library within REvoDesign (when __file__ == "package_manager.py")
```

## Installation Sources

The manager supports three installation sources, selected through the UI:

| Source | Description |
|--------|-------------|
| **Repository** | Clones and installs from `https://github.com/YaoYinYing/REvoDesign`. Supports tag/commit pinning (e.g., `main`, `v1.2.0`). |
| **Local clone/directory** | Installs from a local git clone or source directory on disk. |
| **Local file** | Installs from a local `.zip` or `.tar.gz` archive. |

## Key Features

- **Upgrade** -- Reinstalls with `--upgrade` flag to update an existing installation.
- **Verbose logging** -- Adjustable verbosity level controls pip's `-v`/`-q` flags.
- **Version/commit pinning** -- Tags and branches are parsed from `source@tag` syntax by `PIPInstaller.install()`.
- **Proxy support** -- HTTP, HTTPS, SOCKS5, and SOCKS5h proxies are supported via the `ALLOWED_PROXY_PROTOCOLS` constant.
- **Mirror selection** -- An alternative PyPI index URL can be specified for regions where the main index is slow.
- **Extras selection** -- The `CheckableListView` widget displays extras groups from a remote JSON manifest. Each extra item can declare platform requirements and Python version constraints.
- **Cache control** -- Pip cache management is integrated into the installation workflow.
- **Self-upgrades** -- Right-click the manager's title bar to upgrade the manager script itself from the Gist.

## Architecture

### WorkerThread (`:::` REvoDesign.tools.package_manager.WorkerThread)

A `QThread` subclass that executes an arbitrary Python function in a background
thread. Results are returned via `result_signal`. The thread supports
interruption via `requestInterruption()` and automatic cleanup of spawned
subprocesses through `RunningProcessRegistry`.

```python
class WorkerThread(QtCore.QThread):
    result_signal = QtCore.pyqtSignal(list)
    finished_signal = QtCore.pyqtSignal()
    interrupt_signal = QtCore.pyqtSignal()
    notify_signal = QtCore.pyqtSignal(str)
    progress_val_set_signal = QtCore.pyqtSignal(int)
    progress_range_set_signal = QtCore.pyqtSignal(int, int)
```

### ThreadExecutionManager (`:::` REvoDesign.tools.package_manager.ThreadExecutionManager)

Binds a `WorkerThread` with UI affordances: abort button overlay, progress
reporting, and dashboard integration. Manages the lifecycle of abort overlays
and handles thread cleanup on finish or cancellation.

### ThreadDashboard (`:::` REvoDesign.tools.package_manager.ThreadDashboard)

A floating dialog that visualizes all active `WorkerThread` instances. It
displays task description, duration, and thread ID in a table. Right-click
offers a "Kill" action to force-terminate a thread and its subprocesses.

### AbortButtonOverlay (`:::` REvoDesign.tools.package_manager.AbortButtonOverlay)

An overlay widget that reveals a red "Abort" button when hovering over a
trigger button. It acts as a non-modal interruption mechanism: clicking it
calls `cmd.interrupt()` and requests the worker thread to stop.

### ThreadPoolRegistry (`:::` REvoDesign.tools.package_manager.ThreadPoolRegistry)

Global registry tracking running `WorkerThread` instances. Thread-safe (uses a
`threading.Lock`). Automatically syncs with `ThreadDashboard` on register and
unregister.

### RunningProcessRegistry (`:::` REvoDesign.tools.package_manager.RunningProcessRegistry)

Tracks subprocesses spawned within worker threads, enabling cancellation. Each
`subprocess.Popen` is linked to its parent worker via TLS (`_WORKER_CONTEXT`).
On termination, all tracked processes are terminated, waited, and if necessary
killed.

### REvoDesignPackageManager (`:::` REvoDesign.tools.package_manager.REvoDesignPackageManager)

The top-level orchestrator. It:
1. Self-bootstraps the UI file (`REvoDesign_installer.ui`) via retrying Gist fetches
2. Self-bootstraps the extras manifest JSON (`REvoDesignExtrasTableRich.json`) via retrying Gist fetches
3. Fetches GitHub release tags for version selection
4. Registers PyMOL menu items (Install, Reinstall, Uninstall, Manager)
5. Configures proxy, mirror, and extras in the UI
6. Delegates pip operations to `PIPInstaller`

## The UI File

The manager is expected to work as a single PyMOL startup file. It therefore
self-bootstraps its UI from the canonical Gist source generated from
`src/REvoDesign/UI/REvoDesign-PyMOL-entry.ui` into a writable runtime bootstrap
directory under the system temp directory by default. Set
`REVODESIGN_PM_BOOTSTRAP_DIR` to override that bootstrap location in tests or
special deployments. Startup re-fetches bootstrap assets with retry/backoff
instead of treating a stale local copy as the source of truth, and it never
writes runtime assets into `src/` or an installed package directory.

## Extras Registry

The canonical source file `jsons/REvoDesignExtrasTableRich.json` defines
available extras and is uploaded to Gist with `make upload-gists`. The manager
self-bootstraps the runtime copy into the same writable bootstrap directory
with retry/backoff. The Refresh button is the explicit user-triggered path for
fetching and writing a newer runtime copy from Gist. Each extras entry can
specify:

- **`name`** -- Display name
- **`extras_id`** -- The pip extras identifier (e.g., `[scatter]`)
- **`depts`** -- Category tags
- **`description`** -- Human-readable description
- **`platform`** -- Required hardware platform (`CUDA`, `MPS`)
- **`python_version`** -- Python version constraint (e.g., `>=3.8,<3.12`)

The extras groups are modeled by three dataclasses:
- `::: REvoDesign.tools.package_manager.ExtrasItem`
- `::: REvoDesign.tools.package_manager.ExtrasGroup`
- `::: REvoDesign.tools.package_manager.ExtrasGroups`

## PIPInstaller (`:::` REvoDesign.tools.package_manager.PIPInstaller)

Wraps `pip install`, `pip uninstall`, and `ensurepip` as a Python API. Key
behaviors:

- Automatically upgrades pip before any REvoDesign installation
- Supports extras via `package_name[extras1,extras2]` syntax
- Supports mirror URLs with `-i` flag
- Verbosity is controlled by an integer level (negative = silent, positive = verbose)
- Returns a `LiveProcessResult` with captured stdout/stderr

## GitSolver (`:::` REvoDesign.tools.package_manager.GitSolver)

Detects available package managers on the current system (winget, choco, scoop,
conda, mamba, brew, apt, dnf, yum, zypper, pacman, pkg, snap, port) and
attempts to install Git if it is missing. The `INSTALLERS` class variable is an
ordered tuple of `PackageManagerCommand` dataclasses that define each
platform's install command.

## Self-Upgrades

The manager can upgrade itself. A right-click context menu on the
`ThreadDashboard` table or the manager dialog triggers a fetch of the latest
manager script from the Gist, replacing the running module.

## Thread Management Flow

```
User clicks "Install"
       |
       v
REvoDesignPackageManager
  -> PIPInstaller.install()
     -> run_command()              # spawns subprocess.Popen
        -> RunningProcessRegistry tracks the process
     -> WorkerThread wraps the pip call
        -> ThreadPoolRegistry registers the thread
           -> ThreadDashboard updates its table
        -> ThreadExecutionManager provides abort overlay
  -> On completion or abort:
     -> RunningProcessRegistry clears processes
     -> ThreadPoolRegistry unregisters thread
     -> ThreadDashboard refreshes
```

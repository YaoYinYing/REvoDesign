# Thread Management in REvoDesign

## Introduction

REvoDesign runs inside a PyQt/PyMOL host where long-running design, simulation, or IO tasks would otherwise block the UI event loop. To keep the interface reactive and cancellable, REvoDesign ships a dedicated threading mechanism centered around `WorkerThread`, `ThreadExecutionManager`, and a runtime dashboard housed in `src/REvoDesign/tools/package_manager.py`. These components wrap heavy operations, protect the main thread, and provide tooling to observe or abort background jobs without corrupting PyMOL state.

## Design Goal

- Keep PyMOL + Qt responsive by moving blocking work onto managed `QThread`s while continuously pumping events via `refresh_window()` (`src/REvoDesign/tools/package_manager.py:2454`).
- Provide a uniform UX for cancellations and notifications: every worker automatically gets abort affordances, process cleanup, and message routing through `ThreadExecutionManager` (`src/REvoDesign/tools/package_manager.py:2194-2274`).
- Offer observability and governance for power users: `ThreadPoolRegistry` and the floating Thread Dashboard visualize every active worker with durations and thread IDs (`src/REvoDesign/tools/package_manager.py:1856-2018`).
- Ensure subprocesses spawned by threads can be terminated safely by tracking them inside `RunningProcessRegistry` so that an abort propagates to `subprocess.Popen` handles (`src/REvoDesign/tools/package_manager.py:2021-2080`).

## Why NOT Progressbar

Traditional progress bars assume a single, linear workload. REvoDesign workloads often fan out into joblib pools, Rosetta runs, or third-party servers where we only know that “work is happening”. For those cases the thread dashboard delivers a truer signal than an indeterminate bar. When Rosetta’s mutate/relax runner spawns parallel jobs via joblib, its author explicitly disables the built-in progress bar because multiple nested workers would make the bar inaccurate and spammy (`src/REvoDesign/sidechain/mutate_runner/RosettaMutateRelax.py:69-95`). Similar scenarios exist in installers and scoring pipelines. Instead of forcing deceptive UI, the thread system exposes cancel/notify hooks; individual tools may still opt into a domain-specific progress bar (e.g., `Evaluator` updating `progressBar` when it has discrete mutants), but no global progress widget is mandated.

## Work Model

1. **Entry point** – UI callbacks, CLI helpers, or YAML-driven shortcuts call `run_worker_thread_in_pool(fn, *args, trigger_buttons=...)` (`src/REvoDesign/tools/package_manager.py:2537-2582`). This helper creates a `WorkerThread`, registers it with the dashboard, and starts it.
2. **Thread execution** – `WorkerThread.run()` captures the previous worker in a thread-local `_WORKER_CONTEXT`, checks for early interruptions, then executes the callable. Results are stored and optionally emitted via `result_signal` (`src/REvoDesign/tools/package_manager.py:2296-2336`).
3. **Process tracking** – When the worker spawns subprocesses via `run_command`, those processes are tied back to the current worker through `_WORKER_CONTEXT` so a later abort can terminate them (`src/REvoDesign/tools/package_manager.py:437-505` combined with `2021-2080`).
4. **UI pumping** – While the worker is alive, `run_worker_thread_in_pool` keeps calling `refresh_window()` and sleeps briefly. This manual pump prevents Qt/PyMOL from freezing even though the call originated on the GUI thread.
5. **Teardown** – When the task completes or is interrupted, `ThreadExecutionManager` unregisters it, tears down abort overlays, and ensures `RunningProcessRegistry` clears any remaining subprocess handles before handing control back.

## API design

- `run_worker_thread_in_pool(func, *args, trigger_buttons=None, notify_slot=None) -> Any`: preferred surface for dispatching background work. It wires up buttons that launched the task so the user gets an Abort overlay and so the button can be disabled while the task runs.
- `WorkerThread(QtCore.QThread)`: thin wrapper that stores results, exposes signals (`result_signal`, `finished_signal`, `notify_signal`, `progress_*`), and integrates with `_WORKER_CONTEXT` for subprocess tracing (`src/REvoDesign/tools/package_manager.py:2296-2345`).
- `ThreadExecutionManager`: binds a worker to UI affordances—abort overlays, notify callbacks, and dashboard bookkeeping. It also exposes `kill_entry` so the dashboard context menu can force-quit runaway jobs (`src/REvoDesign/tools/package_manager.py:2189-2274`).
- `ThreadPoolRegistry` + `ThreadPoolEntry`: maintain metadata (description, start time, duration) for each `QThread` so the dashboard view can synchronize without scanning live threads (`src/REvoDesign/tools/package_manager.py:1856-2018`).
- `RunningProcessRegistry`: maintains a map between worker threads and `subprocess.Popen` objects launched inside them. Abort requests call `terminate()`/`kill()` as needed, guaranteeing there are no orphaned Rosetta/PyTorch helpers after a user cancellation (`src/REvoDesign/tools/package_manager.py:2021-2080`).
- `refresh_window()` and `notify_box()`: convenience helpers to keep the GUI responsive and route worker-side notifications back to the user (`src/REvoDesign/tools/package_manager.py:2454-2523`).

## Living Case (How to)

A concrete usage sits in `REvoDesign.REvoDesign` where each multi-design button simply calls into the thread pool wrapper. For example, `multi_design_initialize` is launched with:

```python
self.bus.button("multi_design_initialize").clicked.connect(
    partial(
        run_worker_thread_in_pool,
        worker_function=self.multi_mutagenesis_design_initialize,
        trigger_buttons=self.bus.button("multi_design_initialize"),
    )
)
```

(`src/REvoDesign/REvoDesign.py:506-512`)

Because the button is passed as `trigger_buttons`, the user sees a hoverable Abort overlay and cannot spam-click it. The worker can safely run Rosetta prep, filesystem IO, or API calls without freezing PyMOL. Any subprocesses spawned through `run_command` inherit the worker context, so aborting from the dashboard or overlay terminates them cleanly. Other tabs (multi-design navigate, export, auto run) reuse the same pattern, giving a consistent “click → async job → optional cancel” workflow across the UI (`src/REvoDesign/REvoDesign.py:514-559`).

## User Interface Control

- **Thread Dashboard** – a floating non-modal dialog that lists every running worker, its elapsed time, and the internal thread ID. Users can open it via the package manager header double-click or API (`ThreadDashboard.show_thread_dashboard`). Each row exposes a context menu so advanced users can kill a worker even if the originating dialog is gone (`src/REvoDesign/tools/package_manager.py:1876-1993`).
- **Abort overlays** – whenever a `trigger_button` is supplied, `ThreadExecutionManager` attaches an `AbortButtonOverlay` that reveals a red Abort button on hover, wired to `WorkerThread.interrupt()` (`src/REvoDesign/tools/package_manager.py:2106-2187`).
- **Notifications** – workers can call `worker_thread.notify_signal.emit("..." )` (or rely on defaults) and let `ThreadExecutionManager` route it to `notify_box` or any injected slot (`src/REvoDesign/tools/package_manager.py:2248-2251`).
- **Event pumping & focus** – while waiting for workers to finish, the helper loop keeps calling `QtWidgets.QApplication.processEvents()`, so dialogs stay repaintable, and buttons will re-enable as soon as jobs finish (`src/REvoDesign/tools/package_manager.py:2454-2582`).
- **Kill switch safety** – forcing a quit from the dashboard or overlay also calls `RunningProcessRegistry.terminate()` and `cmd.interrupt()` to make sure PyMOL scripting halts before the `QThread` is torn down (`src/REvoDesign/tools/package_manager.py:2228-2283`).

## Conclusion

The thread management layer provides a compromise between pure background execution and UI transparency: long tasks run inside dedicated `QThread`s, every worker is visible and cancellable, and subprocess lifetimes are tied to their parent workers. By relying on this infrastructure—rather than ad-hoc threads or misleading global progress bars—developers keep REvoDesign responsive, debuggable, and safe to operate even when heavy design algorithms are running.

# Top Design TODOs

1. **High – Harden QtSocketConnector serialization**  
   `src/REvoDesign/clients/QtSocketConnector.py:160-192` still base64-encodes arbitrary `pickle` payloads that are deserialized on receipt, so any collaborator can trigger arbitrary code execution. Replace pickle with a safe schema (msgpack/JSON) and add signature or ACL checks before calling `broadcast`/`digest_dict`.
4. **High – Module-level PyMOL imports make the library unusable outside PyMOL**  
   Modules such as `src/REvoDesign/evaluate/evaluator.py:7-18` and `src/REvoDesign/tools/mutant_tools.py:5-26` import `from pymol import cmd` at import time. Any script, CLI, or test that touches these modules without a PyMOL runtime crashes before code executes. Defer PyMOL imports to call sites or inject an abstraction so non-PyMOL contexts can still use the logic.
6. **Medium – ConfigBus is a mutable global singleton storing Qt widget handles**  
   `src/REvoDesign/driver/ui_driver.py:365-381` binds the singleton instance to the active UI and exposes widgets to every module. This leaks Qt objects across tests, prevents multiple windows, and requires manual resets (see `tests/conftest.reset_singletons`). Break ConfigBus into a pure configuration store plus scoped UI adapters so state does not persist globally.
8. **Medium – PIPPack runner calls private APIs of its dependency**  
   `src/REvoDesign/sidechain/mutate_runner/PIPPack.py:64-105` invokes `_initialize_with_a_model`, `_run_repack_single`, and `_run_repack_batch` on the third-party `PIPPack` object. These underscore-prefixed methods are not part of the public API and break whenever upstream refactors; switch to supported entrypoints or wrap the CLI.
11. **High – Importing the logger mutates user state**  
    `src/REvoDesign/logger/logger.py:1-120` configures logging, creates directories under `user_log_path`, and spins up a background `QueueListener` during import. Simply touching `REvoDesign.logger` writes to the host filesystem and leaves live threads around; lazily initialize logging from the entrypoint instead.
16. **High – RFdiffusion weight downloads block the UI**
    `src/REvoDesign/shortcuts/tools/rfdiffusion_tasks.py:90-151` fetches multi‑GB checkpoints synchronously inside `RfDiffusion.pick_model`, freezing PyMOL while `pooch` downloads. Move the download to `run_worker_thread_in_pool` and provide progress/abort hooks.
22. **High – “Background” workers busy-wait on the GUI thread**
    `src/REvoDesign/tools/package_manager.py:2635-2661` starts a `WorkerThread` but then loops on `work_thread.isFinished()` calling `refresh_window()`/`time.sleep`, so the main thread stays blocked and abort buttons can’t repaint. Switch to signal-driven completion instead of polling.
24. **High – WebSocket clients hand over the shared auth key on request**
    `src/REvoDesign/clients/QtSocketConnector.py:813-863` responds to a `RequireKey` message by sending `self.authentication_key` before the server proves its identity. A malicious host can simply ask for the key and impersonate everyone. Authenticate the server (TLS + pinned cert) and only send a key through an already-authenticated channel.
26. **Medium – pip installs run on the UI thread**
    `src/REvoDesign/tools/package_manager.py:861-925` calls `pip install/uninstall` directly from menu actions, blocking PyMOL for minutes during heavy installs. Dispatch these calls to `run_worker_thread_in_pool` and stream progress to the dashboard.

## Engineering Principles overdesign audit

Read-only audit recorded on 2026-08-06. The estimates below are directional; each item should be revalidated against the current checkout before implementation.

- [x] **Delete the repository-local Loopkit/Claude framework.** The 1,333 tracked lines under `.claude/` duplicated the root guidance and included migration practices that conflicted with `CLAUDE.md`; the root `CLAUDE.md` is now the sole agent guidance.
- [x] **Delete compatibility-only `QButtonBrick` children.** `QButtonMatrix` is tested and driven through its native selection API without invisible per-cell widgets.
- [ ] **Delete `SingletonAbstract.derive()`.** Its dynamic subclass machinery has no production callers and is exercised only by tests. Define ordinary subclasses if a real use case appears.
- [ ] **Give one component ownership of the translator.** Retain the translator returned by early installation and pass it directly to `LanguageSwitch`; remove `RuntimeUiProxy.trans`, application-child scanning, duck-typed fallback, and bus mirroring.
- [ ] **Remove inappropriate server runtime dependencies.** Move or delete runner-only `biopython`, `matplotlib`, `numpy`, and `pandas`; test-only `requests`; unused `six` and `click`; and redundant `redis`, which is already supplied by `celery[redis]`.
- [ ] **Give `ClusterTabController` sole ownership of the cluster-method selector.** Remove duplicate ordering and filtering in `CallableGroupValues` and both hardcoded registry fallbacks.
- [ ] **Consolidate server reload handling.** Make reload an operation of the main server control script, delete `hot_fix.sh`, and remove duplicated Compose/environment discovery and the legacy `.env` fallback.
- [ ] **Replace `ParamChangeRegister` with direct iteration.** Keep the useful registry items, but remove the single-instance wrapper class.
- [ ] **Delete task-runtime compatibility exports.** Current routes already import the helpers directly from `task_runtime`; remove the two alias chains.
- [ ] **Shrink `PluginRegistry`.** Remove the unused custom installed attribute, package-module exclusion, include predicate, and delegate-only factory.
- [ ] **Delete `DialogWrapperRegistry.use_progressbar`.** It is logged as a legacy preference but never changes execution.
- [ ] **Drop legacy `.xls` support and `xlrd`.** Retain `.xlsx` support through the existing `openpyxl` path.
- [ ] **Delete unused or legacy configuration switches.** Remove `config_settings.auto_save`, `config_settings.save_on_exit`, and the unexposed `rosetta.cart_ddg.use_legacy` option.
- [ ] **Delete the unused `install_qt5_aliases()` compatibility name.** `install_qt6_aliases()` is the current API.

Estimated maximum reduction: approximately 1,900 lines and 9 direct dependencies.

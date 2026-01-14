# Top Design TODOs

1. **High – Harden QtSocketConnector serialization**  
   `src/REvoDesign/clients/QtSocketConnector.py:160-192` still base64-encodes arbitrary `pickle` payloads that are deserialized on receipt, so any collaborator can trigger arbitrary code execution. Replace pickle with a safe schema (msgpack/JSON) and add signature or ACL checks before calling `broadcast`/`digest_dict`.
2. **High – Package manager bootstrapping assumes writable, online site-packages**  
   `src/REvoDesign/tools/package_manager.py:358-404` and `:970-993` always download UI/assets from GitHub gists during startup and write them back into the installed package directory. On read-only installs (system pip, CI wheels) this raises permission errors, and there is no offline cache fallback or signature/timeout on the download. Vendor these assets with the package and gate network calls behind explicit user consent with timeouts.
3. **High – Config bootstrap requires GUI prompts**  
   `src/REvoDesign/bootstrap/set_config.py:18-88` shows Qt modal dialogs while deciding whether to reset config trees. The bootstrap runs during import (tests call `set_REvoDesign_config_file()`), so headless runs and automation hang waiting for GUI input. Refactor these prompts behind a CLI/flag interface and avoid Qt when `PYMOL_GIT_TEST`/headless.
4. **High – Module-level PyMOL imports make the library unusable outside PyMOL**  
   Modules such as `src/REvoDesign/evaluate/evaluator.py:7-18` and `src/REvoDesign/tools/mutant_tools.py:5-26` import `from pymol import cmd` at import time. Any script, CLI, or test that touches these modules without a PyMOL runtime crashes before code executes. Defer PyMOL imports to call sites or inject an abstraction so non-PyMOL contexts can still use the logic.
5. **High – REvoDesignPlugin changes the global working directory**  
   `src/REvoDesign/REvoDesign.py:103-145` calls `os.chdir(self.PWD)` every time a window opens, mutating the process-wide CWD for all other PyMOL plugins and threads. Persisting state should rely on explicit paths stored in the bus, not on moving the interpreter’s CWD.
6. **Medium – ConfigBus is a mutable global singleton storing Qt widget handles**  
   `src/REvoDesign/driver/ui_driver.py:365-381` binds the singleton instance to the active UI and exposes widgets to every module. This leaks Qt objects across tests, prevents multiple windows, and requires manual resets (see `tests/conftest.reset_singletons`). Break ConfigBus into a pure configuration store plus scoped UI adapters so state does not persist globally.
7. **Medium – Developer-only absolute paths are committed**  
   The Makefile and tests refer to `/Users/yyy/...` (e.g., `Makefile:113`, `tests/data/test_data.py:393`), so running scripts on any other machine wipes or looks for that specific user’s home directory. Replace these with `$HOME`/config values or derive from repo-relative paths.
8. **Medium – PIPPack runner calls private APIs of its dependency**  
   `src/REvoDesign/sidechain/mutate_runner/PIPPack.py:64-105` invokes `_initialize_with_a_model`, `_run_repack_single`, and `_run_repack_batch` on the third-party `PIPPack` object. These underscore-prefixed methods are not part of the public API and break whenever upstream refactors; switch to supported entrypoints or wrap the CLI.
9. **High – Shell pipeline script evaluates user input**  
   `server/REvoDesign_PSSM_GREMLIN.sh:158-220` builds shell commands containing user-provided file paths and runs them via `eval "$cmd"`. A crafted FASTA path or output directory injects arbitrary shell code into cluster jobs. Use arrays/`"$@"` instead of eval and properly quote user input.
10. **High – WebSocket keys use non-cryptographic randomness**  
    `src/REvoDesign/tools/utils.py:743-765` uses `random.choice` to generate passwords, and `src/REvoDesign/REvoDesign.py:1158-1167` feeds those into `ui.socket.input.key`. The default PRNG is predictable and unsuitable for authentication secrets; switch to `secrets.choice`/`secrets.token_urlsafe`.
11. **High – Importing the logger mutates user state**  
    `src/REvoDesign/logger/logger.py:1-120` configures logging, creates directories under `user_log_path`, and spins up a background `QueueListener` during import. Simply touching `REvoDesign.logger` writes to the host filesystem and leaves live threads around; lazily initialize logging from the entrypoint instead.
12. **High – WorkerThread drops exceptions**  
    `src/REvoDesign/tools/package_manager.py:2296-2345` executes `self.func` in `QThread.run()` without trapping exceptions or emitting an error signal. Failures just print to stderr while the UI thinks work succeeded. Catch exceptions, forward them through a signal, and surface them via `notify_signal`.
13. **Medium – Conformer preview leaks PyMOL processes**  
    `src/REvoDesign/shortcuts/function_utils.py:17-57` launches a brand-new `pymol -xi` process for every preview and never registers or terminates it, so repeated clicks accumulate orphan PyMOL instances. Reuse the existing PyMOL session or track the subprocess via `RunningProcessRegistry` so abort/exit can kill it.
14. **High – Tests still touch the real config tree**  
    `tests/conftest.py:53-124` calls `set_REvoDesign_config_file()` at import time, which may pop up Qt dialogs and can delete `/Users/yyy/Library/Application Support/REvoDesign/config` if the user confirms. Mock `platformdirs.user_data_dir`/`user_cache_dir` so tests operate entirely inside the repo.
15. **High – RFdiffusion helper forces Qt5Agg backend globally**  
    `src/REvoDesign/tools/rfdiffusion_tools.py:1-7` unconditionally runs `matplotlib.use("Qt5Agg")` on import, breaking headless builds and notebooks that rely on Agg. Only set the backend when a GUI feature is invoked and honor `MPLBACKEND`.
16. **High – Download registry accepts unsigned payloads**  
    `src/REvoDesign/tools/download_registry.py:133-152` leaves registry entries as `None`, so `pooch` skips hash verification and trusts whatever the server returns. Require hashes for every asset or refuse to download; otherwise a MITM can ship arbitrary binaries.
17. **High – RFdiffusion weight downloads block the UI**  
    `src/REvoDesign/shortcuts/tools/rfdiffusion_tasks.py:90-151` fetches multi‑GB checkpoints synchronously inside `RfDiffusion.pick_model`, freezing PyMOL while `pooch` downloads. Move the download to `run_worker_thread_in_pool` and provide progress/abort hooks.
18. **High – DglSolver silently runs pip install**  
    `src/REvoDesign/shortcuts/tools/rfdiffusion_tasks.py:33-70` detects CUDA and immediately executes `python -m pip install dgl==2.2.1` in the current interpreter without prompting or isolating the environment. Prompt the user and install inside a managed env/container so you don’t mutate the host Python unexpectedly.
19. **High – Server keeps plaintext credentials in repo**  
    `server/pssm_gremlin/pssm_gremlin.py:17-36` parses `users.txt` where each line is `username:password` and only hashes them at runtime, so the file on disk stores the raw passwords. Store hashed secrets (or use a proper auth backend) to avoid leaking credentials if the repo/server is compromised.
20. **High – GREMLIN web service hardcodes cluster-only paths**  
    `server/pssm_gremlin/pssm_gremlin.py:38-120` assumes `/mnt/data/...`, `/mnt/db/...`, and `redis://localhost` exist and derives Docker mounts from `/home/{os.getlogin()}`. With no configuration hooks the service cannot run off that exact cluster. Externalize broker paths, DBs, and output dirs via a config file/env vars.
21. **Medium – Config-driven env overrides clobber user variables**  
    `src/REvoDesign/driver/environ_register.py:8-39` iterates `environ.yaml` and unconditionally sets each key in `os.environ`, overwriting whatever the shell provided (proxy settings, CUDA flags, etc.). Respect existing values or mark overrides explicitly in config.
22. **High – Archive extraction is vulnerable to path traversal**  
    `src/REvoDesign/tools/utils.py:592-627` calls `tarfile.ZipFile(...).extractall()` on user-selected archives with no member filtering, so a malicious tar can overwrite arbitrary files. Validate members (reject `..`/absolute paths) or use Python’s newer `tarfile` filters.
23. **High – SSL certificate manager writes weak certs**  
    `src/REvoDesign/tools/ssl_certificates.py:34-115` generates self-signed certs with a fixed serial number, week-long validity, and default filesystem permissions under a shared cache dir. Anyone on the box can read or overwrite the keys. Randomize serials, tighten permissions, and allow the validity to be configured.
24. **High – “Background” workers busy-wait on the GUI thread**  
    `src/REvoDesign/tools/package_manager.py:2635-2661` starts a `WorkerThread` but then loops on `work_thread.isFinished()` calling `refresh_window()`/`time.sleep`, so the main thread stays blocked and abort buttons can’t repaint. Switch to signal-driven completion instead of polling.
25. **High – Aborting a worker interrupts the whole PyMOL session**  
    `src/REvoDesign/tools/package_manager.py:2223-2244` handles every abort click by calling `cmd.interrupt()`, which cancels whatever PyMOL is currently doing—even unrelated jobs. Terminate only the subprocesses registered for that worker rather than nuking the global interpreter.
26. **High – Monaco editor logs its auth token**  
    `src/REvoDesign/editor/monaco/server.py:71-78` generates a `SECRET_TOKEN` and immediately logs it, so anyone with read access to the log file can hijack the editor backend. Never log secrets and rotate them when the server restarts.
27. **High – WebSocket clients hand over the shared auth key on request**  
    `src/REvoDesign/clients/QtSocketConnector.py:813-863` responds to a `RequireKey` message by sending `self.authentication_key` before the server proves its identity. A malicious host can simply ask for the key and impersonate everyone. Authenticate the server (TLS + pinned cert) and only send a key through an already-authenticated channel.
28. **Medium – Git tag fetches are synchronous and unauthenticated**  
    `src/REvoDesign/tools/package_manager.py:2349-2380` hits the public GitHub tags API on startup without auth, caching, or error UI. When the rate limit is exceeded the manager freezes for ~10s and users see nothing. Add caching, a timeout, and a friendly error surface.
29. **Medium – pip installs run on the UI thread**  
    `src/REvoDesign/tools/package_manager.py:861-925` calls `pip install/uninstall` directly from menu actions, blocking PyMOL for minutes during heavy installs. Dispatch these calls to `run_worker_thread_in_pool` and stream progress to the dashboard.
30. **Medium – Archive browsing keeps every extraction forever**  
    `src/REvoDesign/driver/file_dialog.py:240-269` always expands compressed inputs into `<PWD>/expanded_compressed_files/<archive>` with no cleanup or quota. Repeated browsing bloats the session dir and a malicious 20 GB tar can fill the disk. Extract into a temp dir and delete it once the dialog closes.

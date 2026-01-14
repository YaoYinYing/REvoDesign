# Future plans

This future plan document is a chat history with the ChatGPT Codex.

## Tools *vs* Dependencies

### Situation

> [!TIP] REvoDesign wishes to combine various tools into it. how ever, as the toolkit keeps expanding, it's become more and more difficult to make the dependencies compatible/upgradable in one pot. e.g. DGL does not support py3.13 and above and currently not under well maintainance, meaning that it would definitly out-of-date in one day. 
> \# fork
> - what is the future of this toolkit?
> - how should it keep updated while stay compatible to old tools like RFdiffusion and utilize the best performance of local machine?
> - is it posible not to be containerized like docker or singularity?
> - is it possible to offload some computation to cloudservices like biolib or its potential counterparts?


REvoDesign’s value is in orchestrating disparate modeling tools (PyMOL workflows, RFdiffusion, ThermoMPNN, PyTorch/OpenMM helpers) from one UI. That future hinges on treating it as a thin coordination layer rather than a monolithic “one pot” install. Plan on curating a stable core (PyMOL plugin, UI, config, logging, threading infrastructure) and model each heavy dependency as an optional module with explicit version constraints. That lets the project keep evolving (new shortcuts, cloud triggers, automation) while acknowledging that some components will age out.

Staying current while supporting legacy tools requires hard boundaries. Policy: (1) maintain a matrix of “tested” Python versions per optional feature (RFdiffusion, DGL, OpenMM, etc.) and surface those requirements in the UI and docs; (2) isolate third-party stacks via per-tool “runner” shims that can run in dedicated venvs or external processes, so upgrading PyTorch for one feature doesn’t break others; (3) keep benchmarking scripts/tests so when a dependency updates you can verify performance paths on CPU/GPU/MPS automatically. For RFdiffusion-like pipelines, prefer dispatching to their own conda env (or even CLI/REST) while passing data via well-defined files to leverage the local machine’s accelerators without forcing the whole plugin to share the same pip environment.

Avoiding mandatory containerization is realistic if you adopt the per-module virtualization above. The base PyMOL plugin can keep running “bare metal,” while heavyweight runners can either (a) spawn subprocesses bound to dedicated conda environments, or (b) offer optional Docker/Singularity recipes for users who want a sealed stack. Document those as first-class integration paths so users can choose: local envs for quick iterations, containers when reproducibility trumps convenience.

Offloading workloads is very viable. For example, RFdiffusion sampling, GREMLIN scans, or ThermoMPNN scoring can be queued to hosted services such as BioLib, Colab notebooks, or custom FastAPI endpoints. The toolkit already has thread/process orchestration; extend that to remote “drivers” that package inputs, submit jobs (REST/gRPC), and stream back statuses/results. That keeps REvoDesign lightweight locally, leverages cloud GPUs when needed, and gives you a graceful degradation path once certain local dependencies become unmaintainable.

---

### Isolating heavyweight toolchains

> [!TIP] explain this concept: spawn subprocesses bound to dedicated conda environments, or (b) offer optional Docker/Singularity recipes for users who want a sealed stack

That line is outlining two strategies for isolating heavyweight toolchains so REvoDesign’s PyMOL plugin doesn’t have to share one fragile Python environment with everything:

Spawn subprocesses in dedicated conda envs – For each external runner (RFdiffusion, DGL tasks, OpenMM, etc.) you create/activate its own conda environment with the exact versions it needs, and when the user invokes that feature you launch a separate process (Python script, CLI) under that env. The plugin communicates via files/stdin/stdout, so dependency conflicts stay inside that env.

Offer optional Docker/Singularity recipes – For users who prefer totally sealed setups, provide container images that bundle the same runner code plus all its dependencies. REvoDesign can invoke the container (docker run / singularity exec) instead of local Python, guaranteeing reproducible versions without touching the host environment.

Both approaches isolate fragile dependencies, yet the first stays “bare metal” while the second uses full containerization for those who want it.

---

> [!TIP] to make tools available at broad range of devices(Windows, Linux, Macos intel/M-series, aarch, etc), which path is more realisic for REvoDesign?


Given how heterogeneous REvoDesign’s dependency graph is, isolating each heavy toolchain in its own dedicated conda (or virtualenv) and launching it as a subprocess is the more realistic default path for broad device coverage. Reasons:

Conda handles cross‑platform binary wheels far better than Docker does on Windows and macOS (especially on M‑series/aarch). You can ship curated env.yml files per tool, let users create them locally, and they still run “natively” with GPU/MPS acceleration where available.
Spawning subprocesses per env keeps the PyMOL plugin lightweight and works even on locked-down Windows desktops that can’t run Docker/Singularity.
Containers remain valuable for reproducible clusters or cloud offload, so keep them as an optional escape hatch, but don’t make them mandatory because they exclude a large fraction of the Windows/macOS user base.
So: prioritize the multi-env subprocess approach for daily use, and maintain container recipes as optional runners for users who are already container-friendly.

---

### Demo of `Spawning subprocesses per env`

> [!TIP] show me an example of `Spawning subprocesses per env`. REvoDesign  currently rely on PyMOL, heavily. As PyMOL mostly shipped with conda or achievable via conda from scratch, it's should be reasonable if the way like spawning accross envs makes sense.

A practical pattern is:

```python
import subprocess
import sys
from pathlib import Path

def run_tool_in_env(env_prefix: Path, entry_script: Path, *args: str):
    conda_python = env_prefix / "bin" / "python"  # ".exe" on Windows
    cmd = [str(conda_python), str(entry_script), *map(str, args)]
    return subprocess.run(cmd, check=True)

# Example: run RFdiffusion helper inside its own env
rf_env = Path("~/miniconda3/envs/rfdiffusion").expanduser()
rf_entry = Path(__file__).with_name("scripts/run_rfdiffusion.py")
run_tool_in_env(rf_env, rf_entry, "--config", "config.yaml")
```

How it fits REvoDesign:

1. Ship env specs per tool – e.g. envs/rfdiffusion.yaml, envs/dgl.yaml. Users (or installers) create those via conda env create -f ....
2. Entry scripts – keep small Python executables (or CLI wrappers) under src/REvoDesign/tools/runners/. Each script reads arguments, performs the heavy work, and communicates via files/stdout.
3. Launcher – inside the PyMOL plugin, when the user clicks “Run RFdiffusion”, locate that env (via config) and spawn the script through the env’s python (or conda run -n rfdiffusion python script.py ...). You already have run_worker_thread_in_pool; wrap the subprocess call there so the UI stays responsive.
4. Data passing – supply inputs via temp dirs (tmpdir_manager already exists), watch stdout/stderr for progress, and pull results back into PyMOL once the process exits.

Since PyMOL itself often comes from a conda stack, this approach is natural: PyMOL stays in its base env, and each optional designer operates in its own env that can pin incompatible versions without impacting the core.

---

### Technical Details

> [!TIP] the common sense is, conda env requires `activate` to fit runtime terminal session, and `deactivate` to clean these up vise versa. so how robust does this subprocess run work like?

You don’t need to activate/deactivate in-process at all—just launch the tool’s interpreter from the target env. For example:

```python
subprocess.run(
    ["conda", "run", "-n", "rf_env", "python", "scripts/run_rfdiffusion.py", "--cfg", cfg_path],
    check=True,
)
```

or, if you know the env prefix:

```python
env_python = Path("~/miniconda3/envs/rf_env/bin/python").expanduser()
subprocess.run([str(env_python), script, *args], check=True)
```

Because the subprocess inherits its PATH/LD_LIBRARY_PATH from that env’s interpreter (or from conda run), it gets the right packages/GPU drivers without touching the parent PyMOL session. When the subprocess exits there’s nothing to “deactivate”—the main process never switched contexts. This makes the approach robust across platforms: activation is only needed for interactive shells, whereas REvoDesign can always spawn a clean child process with the exact env it needs.

---

### Technical Debts

> [!TIP] now look at the tool registry at `jsons/REvoDesignExtrasTableRich.json` and the parser at `src/REvoDesign/tools/package_manager.py`, how much tech debts to make this refactoring work done? just inspect, estimate and evaluate. dont do the real work.

The current extras registry + parser are very light-weight, so supporting the “spawn per-env runner” concept would require touching multiple layers and adds a noticeable amount of work:

- Schema gaps (JSON jsons/REvoDesignExtrasTableRich.json) – Each extra only tracks extras_id, depts, python_version, and optionally platform. There’s no way to encode “this tool runs from env X”, required interpreters, command entrypoints, download instructions, or where to find the runner script. You’d need to expand the schema (new keys for env spec path, conda channels, executable name, GPU requirements, etc.) and then rev every existing entry. That’s a non-trivial migration because consumers will need backward-compatible defaults.

- Parser limitations (src/REvoDesign/tools/package_manager.py (lines 240-404)) – The current dataclasses (ExtrasItem, ExtrasGroup, ExtrasGroups) simply deserialize the JSON and expose it to the UI. They don’t validate fields, don’t derive constraints, and don’t hook into the installer logic beyond populating a checkbox list. Refactoring to support per-env subprocess launching means:

  - Extending ExtrasItem.from_dict to parse new fields while remaining backward compatible.
  - Threading those fields through CheckableListView, the installer UI, and later code that actually installs or launches extras.
  - Possibly persisting per-extra settings (env prefix paths, runner scripts) in config files.
- Existing installer assumptions – The package manager today just runs pip install for extras_id inside the current environment (see PIPInstaller.install around line 861). Introducing env-aware orchestration would require:

  - Teaching the installer to create/manage multiple conda envs (or at least to run conda run commands).
  - Tracking which extra lives in which env and exposing that to launchers.
  - Updating telemetry/diagnostic code (e.g., around line 2961+ where installed extras are reported) to reflect the new structure.
- UI + workflow updates – The extras dialog currently just lets you check packages and run pip installs. To align with the subprocess-per-env plan, you’d need UI affordances for configuring env locations, showing their health, and routing actions (install/repair/remove). That’s outside the JSON parser, but tied to it—without those extra fields the UI cannot guide users.

Rough effort assessment: The registry refactor alone is a medium project (schema change + JSON migration + parser updates). Layering in env management and subprocess launching pushes it toward a larger, multi-PR effort touching the installer, config, and runner orchestration. There are non-trivial tech debts—everything assumes “extras” are just pip packages in the current env—so you’ll be reworking both data structures and control flow before the new model is workable.

---

### Refactoring work roadmap design


###
> [!TIP] for the tool env setup, maybe we can take a look at homebrew. in fact, a `recipe` record in this json is a prototype of potentially designd behavior like brew.


Using a “recipe” per extra—akin to Homebrew formulas—is a good metaphor. Homebrew encodes, for each package, where to fetch sources/bottles, how to build them, what dependencies exist, and which caveats apply. Your existing jsons/REvoDesignExtrasTableRich.json is already halfway there: each entry has an extras_id, a dependency list (depts), platform hints, etc. To make it homebrew-like:

- Treat each JSON entry as a recipe describing how to provision that tool: include fields for the conda environment spec path (or installer script), required channels, and post-install steps. That recipe then tells the package manager how to set up the env, similar to brew install reading a formula.
- Add metadata for runtime execution (e.g., which runner script to call, expected CLI arguments) so REvoDesign can spawn the tool in its dedicated env without hardcoding behavior elsewhere.
- Because recipes are immutable data, you can ship updates via JSON, allowing the package manager to evolve without changing Python code—just like brew update pulls new formulas.

In short: extend the current registry to carry the same kinds of instructions Homebrew formulas do, and the “brew-like” behavior (install per-tool envs, track versions, surface caveats) naturally follows.

---

## PyMOL, or not PyMOL

### Roadmap

> [!TIP] The next topic i would like to talk about is, the dependancy to PyMOL. As one of the major plan in the future dev is to make REvoDesign more independent -- meaning that it's necessary to reduce and finally replace the uses of functionality of PyMOL with more common bio-tools like biopython and biotite.

- You already noted in src/REvoDesign/tools/pymol_utils.py that those helpers should be “deprecated with biotite or biopython”; that’s the right direction. Start by cataloging where cmd is used (rendering, selections, geometry, file IO) and documenting a replacement API surface built on Biopython/Biotite/NGL/MDAnalysis. Aim for a thin abstraction layer so PyMOL becomes just one backend rather than the core engine.

- Phase-out plan:

 1. Wrap current PyMOL calls behind service classes (structure loading, visualization, mutation ops). That isolates PyMOL dependencies so you can plug in alternative backends without touching business logic.
 2. Re-implement non-visual tasks (sequence parsing, mutant extraction, file conversions) with Biopython/Biotite first—they already exist in BioPython/NumPy land and don’t need visualization.
 3. For visualization, consider web/NGL viewers or VMD-style exporters. Even if PyMOL remains for rich UI, having a non-PyMOL CLI path adds portability for headless runs and future cloud/offload use cases.

- Benefits: independent testing without PyMOL, easier automation (no Qt dependency), and compatibility with environments where PyMOL isn’t available (CI, servers, M-series conda installs). Keep PyMOL as an optional, best-in-class front end, but architect core logic so it can run entirely in standard Python science stacks.
  
---

### Towards a standard Python science stacks

> [!TIP] Talking about `standard Python science stacks`, what is your option and suggestion toward current codebase?

- Strip PyMOL out of the core domain logic. Promote Biopython/Biotite/MDAnalysis as the default data layer for structures, sequences, and mutations so unit tests and CLI flows can run in a plain scientific Python stack (NumPy, pandas, matplotlib) without PyMOL imports firing at module load. Keep PyMOL integrations behind adapters.

- Modularize heavy extras. Each runner (RFdiffusion, ThermoMPNN, OpenMM) should live in its own package/module that depends on the relevant ML/MD stack, while the main plugin sticks to broadly available libs (NumPy, pandas, scipy, requests, hydra/omegaconf). That reduces the shared dependency footprint and aligns with “standard” stacks.

- Replace PyMOL-specific utilities with general-purpose ones: e.g., use Biopython/Biotite for structure parsing/mutation, PyVista/NGL for visualization, and Matplotlib/Plotly for plotting. Offer PyMOL as an optional UI backend via clear abstraction layers, not as the root of all logic.

- Clean up imports and initialization so modules don’t have side effects (Qt dialogs, log listeners) on import. That’s table stakes for being a good citizen in scientific Python ecosystems.

If you refactor along those lines, the codebase can run headless in typical scientific Python environments, while PyMOL becomes an optional—but well-supported—visual shell.

---

## Biomedal?

> [!TIP] Will this project become a new biomedal?

Hard to say—REvoDesign has a different scope (PyMOL‑centric design workflows, lots of local tooling), whereas new Biomedal seems focused on cloud-native pipelines. You can certainly adopt ideas (env isolation, modular runners, web-first UX), but whether it “becomes” Biomedal depends on product goals and resourcing more than technology. Focus on the roadmap we discussed (decouple from PyMOL, recipe-based extras, optional cloud offload) and you’ll carve out your own niche; convergence into another product isn’t predetermined.

---

## Agent and Copilot

> [!TIP] How about agents and AI copilot? does it necessary to the project?

They’re nice-to-have accelerants, not prerequisites.

 - An “agent” or AI copilot could help users compose workflows (“design 20 mutants and run RFdiffusion on chain A”) or assist developers (diagnose environment issues, auto-generate config). If you build a well-structured API layer, you can add such assistants later—either inside REvoDesign (e.g., natural-language macro recorder) or as out-of-band services.

 - However, core priorities—decoupling from PyMOL, modular extras, stable recipes/envs—don’t depend on AI helpers. Without a clean architecture and reliable runtimes, a copilot would just be another layer on shaky foundations.

So: not strictly necessary right now; invest in the infrastructure first. Once the tooling and APIs are solid, AI assistants become more feasible and actually useful.
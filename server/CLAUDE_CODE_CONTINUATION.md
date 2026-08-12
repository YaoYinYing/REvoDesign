# Claude Code Continuation Guide: Scientific Input and Result Plugins

This is a handoff prompt and engineering runbook for continuing the pluggable
scientific input/result workspace work on REvoDesign / REvoCompute. Read this
file completely before editing. Then read the repository files referenced
below; do not treat this document as a substitute for inspecting current code.

## Mission

Continue implementing and validating one friendly input-workspace system that
scales from a simple sequence-only PSSM-GREMLIN submission to structure-heavy,
multi-file tasks such as RFdiffusion, PLACER, EASIFA, and MPNN. Continue the
parallel result-workspace abstraction so new scientific viewers can be added
without rewriting artifact selection, authorization, download, error, or
archive behavior.

The abstraction must not weaken the production contracts:

- the server is authoritative for files, relative paths, parameters, resource
  policy, runner arguments, and task authorization;
- every task retains an immutable isolated snapshot;
- inputs remain read-only and only that task's outputs are writable;
- result viewers receive only authenticated, manifest-approved artifacts;
- individual files and range requests remain first-class;
- ZIP generation remains explicit and optional;
- no YAML-provided executable code, remote plugin URLs, or client-built runner
  commands are allowed.

## Repository and branch

- Repository: `/repo/REvoDesign`
- Branch: `feat/multi-task-server`
- Implementation began from commit:
  `7d798c7532d8b386e344ef9f1f2b1f7c954200ef`
- This remains draft work. Do not create a pull request and do not merge it.
- Never force-push, use `git reset --hard`, discard unrelated changes, or clean
  the worktree destructively.
- Before any work, run:

  ```bash
  cd /repo/REvoDesign
  git status --short --branch
  git rev-parse HEAD
  git rev-parse origin/feat/multi-task-server
  git log --oneline -12
  ```

- If this guide is read after the implementation checkpoint was committed,
  inspect the commits after `7d798c7` and use the current HEAD as truth.
- Commit and push coherent, tested checkpoints to the existing branch. After
  every push, verify local HEAD equals `origin/feat/multi-task-server` exactly.

## Production safety

Do not restart, rebuild, activate, migrate external configuration, submit real
scientific jobs, or delete artifacts merely to continue browser architecture
work. Complete repository tests and local inspection first.

If production work is later explicitly requested:

- environment file: `server/.env.production.v7-slurm`;
- reference it only through
  `REVODESIGN_SERVER_ENV=server/.env.production.v7-slurm`;
- never print the file or secret values;
- keep it Git-ignored and mode `0600`;
- use prepared activation for already-built images/SIFs:

  ```bash
  REVODESIGN_SERVER_ENV=server/.env.production.v7-slurm \
    bash server/run/restart.sh restart --mode=prepared
  ```

- a default/dev restart rebuilds runtime images and is not an appropriate
  activation command when the SIFs are already prepared;
- builds require the deployment's configured `REVODESIGN_BUILD_PROXY`; the
  proxy is build transport, must not remain in final runtime environments, and
  must not be confused with application credentials;
- preserve backups, rollback image tags, and old versioned SIFs;
- do not run Docker or Apptainer prune commands automatically;
- never bypass restart preflight or run as root/sudo merely to make activation
  succeed.

At the last known safe production checkpoint, the `server-slurm` Compose stack
was healthy, the public gateway was on port 8081, `/compute/login` returned 200,
and unauthenticated `/compute/dashboard` returned 401. Re-inspect rather than
assuming this remains current.

## Required reading

Read these files before modifying the implementation:

1. `server/TODO_PLUGGABLE_INPUT_RESULT_UI.md`
2. `server/README.md`
3. `docs/dev-guide/task-types-design.md`
4. `docs/dev-guide/server.md`
5. `server/config/task_types.yaml`
6. `server/revocompute/task_types/__init__.py`
7. `server/revocompute/routes.py`
8. `server/revocompute/templates/create_task.html`
9. `server/revocompute/static/js/plugin-host.js`
10. `server/revocompute/static/js/input-workspace.js`
11. `server/revocompute/static/js/create-task.js`
12. `server/revocompute/templates/task_results.html`
13. `server/revocompute/static/js/result-preview-plugins.js`
14. `server/revocompute/static/js/task-results.js`
15. `server/revocompute/task_runtime.py`
16. `server/tests/test_task_type_registry.py`
17. `server/tests/test_tasks.py`
18. `server/revocompute/resource_policy.py`
19. `server/revocompute/manage_db.py`
20. `server/revocompute/job/runners/slurm_runner.py`
21. `server/revocompute/job/runners/docker_runner.py`
22. `server/revocompute/static/js/configuration.js`
23. `server/tests/test_resource_policy.py`

Also inspect current runner scripts before promising that a UI field maps to an
upstream argument. The test
`test_every_declared_submission_parameter_is_consumed_by_its_runtime_script`
guards this contract.

## What has been implemented

### Server capability schema

`InputCapability` was added to the task registry. Each task may declare:

```yaml
input_workspace:
  capabilities:
    - plugin: files
      id: source_files
      title: Input workspace
      description: Human-readable help
      options: {...}
```

The current built-in plugin IDs are:

- `files`
- `sequence`
- `structure`
- `regions`
- `parameters`
- `review`

The loader allowlists plugin IDs, top-level fields, and per-plugin option keys.
It rejects remote URLs and unknown plugin code implicitly because only those
fixed IDs can load. Capability IDs must be unique. The first capability must
collect files or sequence and the final capability must be `review`.

Registries without `input_workspace` receive a derived backward-compatible
composition based on accepted extensions and typed parameters. This is
important because production uses an external registry which may not be
migrated at the same instant as the server image.

`GET /compute/api/types/<name>` now returns:

```json
{
  "input_workspace": {
    "version": 1,
    "capabilities": []
  }
}
```

Do not put executable strings or runner commands in this payload.

### Checked-in task compositions

The portable registry has explicit compositions for:

- GREMLIN: files + sequence + parameters + review;
- RFdiffusion: files + structure + regions + parameters + review;
- PLACER: files + structure + regions + parameters + review;
- EASIFA: files + structure + parameters + review.

Other tasks currently use the server-derived composition. This is intentional
for incremental migration.

### Shared browser plugin host

`plugin-host.js` supplies `PluginRegistry` and `PluginHost`. It provides local
registration, deterministic definition-order mounting, collection, validation,
refresh, and reverse-order teardown. Do not add dynamic script loading.

`input-workspace.js` registers reusable input components. It currently:

- offers ordinary file selection and folder selection for multi-file tasks;
- preserves `webkitRelativePath` when available;
- lists selected files and lets the user select a supported primary input;
- reorders submission so the server receives the selected primary file first;
- supports pasted FASTA for sequence tasks;
- renders typed basic/advanced parameters;
- parses a local PDB or mmCIF summary and exposes chain/residue context;
- can insert selected residues into a configured region field;
- renders a final review of task, runtime, inputs, parameters, and accelerator;
- tears down listeners when switching task types.

`create-task.js` is now orchestration only: fetch task schemas, mount the
workspace, manage drag/drop, validate plugins, normalize pasted FASTA, build
the existing multipart payload, submit it, and redirect.

The request contract is unchanged:

- repeated `files` entries;
- matching repeated `input_paths` entries;
- `task_type`;
- `params[<name>]`.

### Result preview host

`result-preview-plugins.js` owns the preview registry and a
`ResultPreviewHost`. Text, table, image, and structure renderers are registered
locally. The host enforces declared byte limits and uses a per-render surface
so a stale async preview cannot overwrite a newly selected artifact.

The scientific renderer implementations still live in `task-results.js`; the
registry/selection/lifecycle boundary is extracted. Mol* remains the main
PDB/mmCIF viewer and the pinned py2Dmol alpha-trace remains a degraded fallback.
Raw coordinate text must not be presented as though it were a structure view.

### Canonical end-to-end resources

`resource_policy.py` defines the one typed resource contract. New admin writes
use `cpus`, `memory`, and `max_runtime_seconds`; SLURM placement remains in
validated `slurm_*` fields. Old `nproc`, `maxmem`, `slurm_cpus_per_task`, and
`slurm_mem` values remain resolution fallbacks for production database
migration, but they are no longer shown as competing controls.

The precedence is:

```text
per-task canonical
  -> per-task legacy
  -> global canonical
  -> global legacy
  -> explicit safe default
```

The effective policy contains CPU, memory, maximum runtime, partition, GRES,
nodes, tasks, QOS, account, constraint, exclusivity, and whether GPU is
required. Partition allowlists are enforced. GPU tasks default to `gpu:1`; CPU
tasks ignore global GPU GRES and reject per-task GPU GRES.

The web route resolves resources before persisting uploads, records the policy
in `input_form.resource_policy`, and shows a non-sensitive summary in the form
API. The worker validates the snapshot. This makes queued jobs immutable with
respect to later admin edits. Older queued records without a snapshot resolve
through the live policy for backward compatibility.

SLURM always receives explicit CPU, memory, time, nodes, tasks, GPU (when
required), placement, cwd, and job-name arguments. CPU count is forwarded to
Apptainer thread variables. Docker uses the same CPU/memory limits, forwards
the same thread variables, requests one GPU for GPU tasks, and runs a timeout
watchdog. Admin writes are validated before mutation and applied transactionally.

## Known incomplete areas and likely defects to inspect first

Do not assume the new UI is production-ready. Address these in order:

1. Add real DOM/browser contract tests. The repository currently has Python
   static assertions and Node syntax checks, but no committed JS test harness.
   Choose a small maintainable approach; avoid a large frontend toolchain unless
   justified. At minimum test mount/destroy, task switching, primary reordering,
   folder relative paths, plugin failure isolation, stale async results, and
   keyboard labeling.
2. Exercise the page manually in a local server at desktop and narrow widths.
   Verify GREMLIN, RFdiffusion, PLACER, and EASIFA compositions.
3. Audit `input-workspace.js` lifecycle carefully. File changes should refresh
   structure and review components without recursively rereading structures.
4. Improve inline validation. Current plugin validation reports a consolidated
   status message; required/invalid parameter controls should also receive
   `aria-invalid` and nearby messages.
5. Improve structure interaction. Current residue selection is a local list,
   not a full Mol* selection bridge. Implement a reusable viewer adapter only
   if it can be lifecycle-safe, pinned, bounded, keyboard-accessible, and tested.
6. Validate mmCIF parsing against real representative files. The current local
   summary parser is intentionally lightweight and must never be treated as the
   scientific parser of record.
7. Decide how visual residue selections map to RFdiffusion contig/hotspot syntax.
   Never guess or silently rewrite expert values. Preserve raw advanced fields
   until round-trip rules are demonstrated against the pinned runner.
8. Separate the scientific result renderer implementations into modules only
   when doing so preserves pinned Mol*/py2Dmol integrity constants and fallback
   behavior. The current host boundary is acceptable as an incremental step.
9. Add manifest `group` / `associations` only after server validation, cleanup,
   ZIP inclusion, old-client behavior, and real runtime outputs are specified.
10. Update the external production registry only after backing it up outside
    the active config directory. The derived fallback allows deployment to be
    staged before that migration if necessary.
11. Validate the new prepared-activation resource audit on the production host.
    `restart.sh` now runs a read-only audit inside the candidate worker image
    before `down`; confirm its Compose invocation sees the external registry
    and management database without changing database schema or ownership.
12. Browser-test the redesigned configuration page: inheritance clearing,
    effective values, validation errors, GPU GRES, and allowed partitions.
13. Plan production migration from legacy resource columns. Do not delete old
    columns or values in the first deployment; compare resolved policies before
    and after writing canonical overrides.

## UX requirements by task complexity

### Simple sequence tasks

For GREMLIN, ESM sequence tasks, PRIME, BioEmu, and similar jobs:

- show a file choice and/or pasted sequence, not an empty structure panel;
- show only basic parameters initially;
- show advanced controls in a collapsed group;
- report normalized sequence length and file identity;
- review resource expectations before submission;
- do not make a user understand runtime-family or SLURM internals.

### Structure tasks

For EASIFA, ESM-IF1, Pythia, ProteinMPNN, and similar jobs:

- show the primary structure and detected chains;
- allow task-appropriate chain/residue selection only when it maps to a real
  validated parameter;
- retain a plain file and manual parameter fallback;
- keep model paths, checkpoints, mounts, and devices operator-controlled.

### Complex multi-file tasks

For RFdiffusion and PLACER:

- preserve nested paths and expose primary versus auxiliary roles;
- show all uploaded files in the review;
- RFdiffusion must keep the entire snapshot in `TASK_INPUTS` even though its
  primary input is passed directly;
- PLACER must receive the full snapshot root and consume multiple PDB/mmCIF
  inputs, including nested paths;
- guided controls must round-trip to the exact pinned runner parameters;
- raw expert fields stay available under Advanced;
- resource/cost warnings should be helpful but must not claim scheduler
  guarantees.

## Validation commands

Run syntax and focused tests after each relevant edit:

```bash
cd /repo/REvoDesign

server/.venv/bin/python -m py_compile \
  server/revocompute/resource_policy.py \
  server/revocompute/manage_db.py \
  server/revocompute/task_types/__init__.py \
  server/revocompute/routes.py

node --check server/revocompute/static/js/plugin-host.js
node --check server/revocompute/static/js/input-workspace.js
node --check server/revocompute/static/js/create-task.js
node --check server/revocompute/static/js/result-preview-plugins.js
node --check server/revocompute/static/js/task-results.js

server/.venv/bin/python -m pytest -q \
  server/tests/test_resource_policy.py \
  server/tests/test_slurm_runner.py \
  server/tests/test_docker_runner.py \
  server/tests/test_task_type_registry.py \
  server/tests/test_tasks.py

git diff --check
```

Before committing the completed repository implementation, run the expected
non-container suite:

```bash
cd /repo/REvoDesign/server
python -m py_compile tests/full_stack_smoke.py
python -m pytest -q tests/test_tasks.py
python -m pytest -q \
  --ignore=tests/test_docker.py \
  --ignore=tests/test_runner_docker_compat.py
```

Use `server/.venv/bin/python` from the repository root if the active shell does
not have the server environment activated. Explain any test-count change from
the previous 381-test non-container baseline; this implementation adds tests,
so a higher count is expected.

Do not claim browser behavior is validated merely because static string tests
pass. Record which behaviors were browser-tested and which remain unverified.

## Security review checklist

- All schema titles/descriptions and filenames are inserted with `textContent`,
  not trusted `innerHTML`.
- Unknown capability fields/options and plugin IDs fail at registry load.
- The capability payload cannot broaden server file extensions or parameters.
- Absolute paths, traversal, invalid components, and symlink escape remain
  rejected by server workspace code.
- File role selection changes order only; it does not allow an unsupported
  primary extension.
- Artifact plugins use authenticated URLs from the manifest.
- Text/table previews remain range-bounded.
- Image/structure previews enforce declared byte limits.
- Viewer failures preserve the artifact download fallback.
- Plugin teardown removes listeners, disposes Mol*, revokes object URLs, and
  prevents stale async rendering.
- Logout continues to make protected dashboard/result pages inaccessible.

## Documentation expectations

Keep these synchronized:

- `server/README.md`: operator/developer behavior and safe boundaries;
- `docs/dev-guide/task-types-design.md`: capability schema and task adapter
  ownership;
- `server/TODO_PLUGGABLE_INPUT_RESULT_UI.md`: phase status and open work;
- `CHANGELOG.md`: user-visible changes;
- this handoff: update only when continuation state materially changes.

Do not advertise planned linked plots, galleries, drafts, or visual contig
editing as completed until they are implemented and tested.

## Checkpoint and push procedure

1. Inspect `git status --short` and every diff. Preserve unrelated user work.
2. Run `git diff --check` and the focused/full tests appropriate to the change.
3. Commit only coherent implementation/docs/tests.
4. Push to `origin feat/multi-task-server` without force.
5. Verify:

   ```bash
   git rev-parse HEAD
   git rev-parse origin/feat/multi-task-server
   git status --short --branch
   ```

6. The two hashes must match exactly after every push.
7. Do not create a PR.

## Definition of done for this feature

The feature is not complete until:

- simple and complex tasks are both friendly without task-name conditionals in
  central page orchestration;
- input and result plugins share tested lifecycle/error/fallback contracts;
- RFdiffusion nested primary/auxiliary uploads and PLACER multi-structure input
  pass real minimal server-to-worker-to-SLURM-to-Apptainer smokes;
- structure/region selections map deterministically to pinned runner arguments;
- task switching leaks no parameters, listeners, requests, viewer instances, or
  object URLs;
- keyboard/mobile/error/oversize/unsupported states are validated;
- server validation and workspace/result isolation tests remain green;
- the external registry is backed up and migrated safely if explicit
  compositions are activated in production;
- prepared activation, gateway/service health, authorization, and rollback are
  verified;
- all worthwhile changes are committed and pushed with local/remote HEAD equal;
- no pull request has been created.

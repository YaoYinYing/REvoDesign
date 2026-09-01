# TODO: Pluggable Scientific Input and Result Workspaces

> Result-workspace composition is superseded for new work by the runner-owned
> ResultStoryboard architecture: Expected File Tree → ResultContext →
> ResultStoryboard, with server-owned FileViewers and Files & diagnostics fallback.

Status: implementation complete for the version-3 input and scientific-result
workspace contracts, server-normalized RFdiffusion modes, Mol* residue
selection, candidate/entity/evidence result views, technical output checks,
shortlist export, bounded fetching, and native Chromium contracts. Real-manifest
cataloguing, remaining task mappings, and cross-task composition remain open.
Production SLURM/Apptainer living tests and deployment verification remain
operational release gates. This document is not an activation checklist and
does not authorize production changes.

The next result-view goal is tracked in
[`TODO_SCIENTIFIC_RESULT_VIEW_PROTOCOLS.md`](TODO_SCIENTIFIC_RESULT_VIEW_PROTOCOLS.md).

## Why this work exists

The current create-task page can render typed parameters from the task-type
registry, and the result page already selects a small JavaScript preview plugin
from manifest metadata. Those are useful foundations, but they do not yet form
a reusable scientific workspace.

Structure-heavy tools such as RFdiffusion, PLACER, ProteinMPNN, LigandMPNN, and
EASIFA need richer input interaction than a flat file picker plus a long list
of arguments. Their results likewise need coordinated structure, table, image,
text, and diagnostic viewers rather than task-specific page logic.

The goal is to make both boundaries modular without allowing browser plugins
to bypass server validation, workspace isolation, or manifest approval.

## Intended architecture

```text
                    portable task-type registry
                              |
                              v
                  capabilities + typed schema
                              |
             +----------------+----------------+
             |                                 |
             v                                 v
   input workspace host                result workspace host
   +---------------------+              +---------------------+
   | input-role plugins  |              | preview plugins     |
   | parameter plugins   |              | layout plugins      |
   | validation plugins  |              | action plugins      |
   | summary plugins     |              | fallback/download   |
   +----------+----------+              +----------+----------+
              |                                    ^
              v                                    |
      normalized submission                 result manifest
              |                                    |
              +----------> server/worker ----------+
                         authoritative boundary
```

The browser is responsible for presentation and helpful early validation. The
server remains authoritative for accepted files, relative paths, parameters,
resource policy, command construction, manifest publication, and authorization.

## Design principles

- Plugins implement capabilities, not task names. An input plugin such as a
  structure selector may be reused by RFdiffusion, PLACER, and MPNN tasks.
- Task schemas compose plugins declaratively. YAML must never contain or load
  arbitrary JavaScript, Python, shell commands, or remote plugin URLs.
- A plain file picker, schema-generated parameter form, artifact list, and
  authenticated download remain functional fallbacks.
- Uploaded paths retain their safe relative paths. The UI must not flatten the
  immutable per-task snapshot or imply a username-wide mutable workspace.
- Operator-controlled paths, checkpoints, devices, mounts, and integrity
  overrides are never exposed as user parameters.
- Result plugins consume only manifest-approved artifacts through authenticated
  APIs. They do not recursively browse the host result directory.
- Large artifacts use metadata, ranges, thumbnails, or streaming. A plugin must
  not load an unbounded file into browser memory.
- Plugin failure is isolated: one broken viewer or builder must not make the
  task page, artifact list, download, or another plugin unusable.
- Accessibility and keyboard operation are part of each plugin contract.

## Proposed shared vocabulary

### Input capabilities

Start with a small set of reusable capabilities:

- `files`: one or more files with extension, count, size, and relative-path
  constraints;
- `sequence`: FASTA/text entry with normalization and sequence statistics;
- `structure`: PDB/mmCIF inspection, chain/residue selection, and file-role
  assignment;
- `parameters`: typed scalar, choice, list, range, and advanced fields;
- `regions`: residues, chains, motifs, hotspots, fixed/redesigned positions, or
  contig-like ranges;
- `relationships`: choose a primary input and associate auxiliary inputs;
- `review`: normalized submission summary, warnings, and immutable input paths.

These capabilities should be composable. For example, RFdiffusion would use
`files + structure + regions + parameters + review`; GREMLIN could continue to
use `files/sequence + parameters + review` without loading structure tooling.

### Result capabilities

Preview selection should use explicit manifest metadata with conservative
extension/MIME inference as a compatibility fallback:

- `structure`: PDB/mmCIF and later trajectories or ensembles;
- `table`: CSV/TSV and bounded tabular data;
- `image`: safe raster formats and generated thumbnails;
- `text`: logs, FASTA, JSON, YAML, and plain text with size limits;
- `plot`: declared numeric series or manifest-associated table columns;
- `gallery`: a collection layout over compatible artifacts;
- `diagnostic`: execution logs and operator-facing metadata, kept outside Main
  Results but still individually previewable;
- `download`: universal fallback for unsupported or oversized artifacts.

`role` and `preview` should remain distinct. For example, an execution log has
`role: diagnostic` and `preview: text`; a predicted structure may have
`role: primary` and `preview: structure`.

## Proposed plugin contracts

The implementation uses local, statically registered plugin modules. Specialized
workspace varieties such as `rfdiffusion-regions` remain separate from the
shared input host and are selected by task-type configuration.
Do not introduce runtime-downloaded third-party plugins.

```javascript
// Conceptual API; names may change during implementation.
registerInputPlugin({
  id: "structure-regions",
  supports(capability, context) {},
  mount(host, context) {},
  readValue() {},
  validate(value, context) {},
  summarize(value, context) {},
  destroy() {}
});

registerResultPlugin({
  id: "structure",
  supports(artifact, context) {},
  maxBytes(artifact, context) {},
  render(host, artifact, context) {},
  destroy() {}
});
```

Every mounted plugin receives scoped services rather than global authority:

- authenticated fetch and range helpers;
- object-URL creation with automatic revocation;
- cancellation via `AbortSignal`;
- safe status/error rendering;
- current task/schema/manifest metadata;
- event subscription owned by the host and removed on `destroy()`.

Plugins must not read credentials, construct runner command lines, mutate the
global task schema, or submit directly. The host gathers plugin values into one
normalized payload and uses the existing submission endpoint.

## Schema and manifest evolution

Extend the task form response additively so current clients keep working. A
possible shape is:

```yaml
input_workspace:
  capabilities:
    - plugin: files
      id: source_files
      roles: [primary, auxiliary]
    - plugin: structure-regions
      id: design_region
      source: source_files
    - plugin: parameters
      id: task_parameters
    - plugin: review
      id: submission_review
```

This describes presentation and data relationships only. Existing server-side
`input_extensions`, upload limits, and typed parameter definitions remain the
authoritative constraints.

The result manifest may later add optional presentation hints:

```json
{
  "path": "designs/model_1.pdb",
  "role": "primary",
  "preview": "structure",
  "media_type": "chemical/x-pdb",
  "group": "designs",
  "associations": ["scores/model_1.csv"]
}
```

Hints must be generated by trusted server adapters during manifest publication,
validated as safe relative paths, and ignored gracefully by older clients.

## RFdiffusion reference composition

RFdiffusion should be the first rich input-workspace proof because it exercises
most of the abstraction:

```text
Inputs                       Builder                    Review
+----------------------+     +--------------------+     +------------------+
| structures/model.pdb | --> | design mode        | --> | normalized files |
| config/settings.json |     | chain/residue pick |     | contig summary   |
| auxiliary/...        |     | contig builder     |     | resource request |
| primary-file role    |     | expert parameters  |     | warnings         |
+----------------------+     +--------------------+     +------------------+
```

The builder should support:

- structure upload with preserved nested paths;
- explicit primary-file selection;
- chain, residue, motif, and hotspot selection in a local structure viewer;
- guided design modes with a raw contig editor available under Advanced;
- two-way synchronization between visual selections and normalized contigs;
- inline errors for missing residues, invalid ranges, incompatible modes, and
  unsupported files;
- a submission summary showing normalized values, not a shell command;
- the complete uploaded snapshot remaining available to the runtime through
  `TASK_INPUTS`, even when RFdiffusion consumes only the primary input directly.

The same structure and region plugins should later serve PLACER and MPNN tasks.
Task-specific behavior belongs in declarative composition or a narrowly scoped
adapter, not copied page-level event handlers.

## Result-workspace reference composition

Keep the artifact tree and principal scientific result as separate views over
one manifest. The result host supports:

- a primary candidate, entity-table, or evidence view for manifest-designated scientific outputs;
- a searchable artifact tree preserving nested paths;
- one active preview stage with plugin-owned controls;
- optional linked views, such as selecting a score row and highlighting the
  associated structure;
- text/table/image/structure viewers with explicit byte limits;
- diagnostic logs in the artifact tree but outside the primary gallery;
- individual download at all times and explicit optional ZIP generation;
- clear empty, running, partially available, failed, unsupported, and oversized
  states.

Mol* should remain the full structure viewer. A lightweight alpha-carbon trace
may remain a local fallback, but it must be presented as a degraded structure
view rather than silently falling back to raw coordinate text. Result viewers
hide Mol*'s right-side controls by default to prioritize the structure, while
input workbenches explicitly enable them for selection-oriented work. A
selection-enabled workbench also enters Mol* selection mode automatically and
reports canonical residue locations from the structure-selection manager.

## Delivery plan

### Phase 0: inventory and design tests

- Map current create-task and result-page behavior, API payloads, manifest
  fields, size guards, viewer dependencies, and task-specific event handlers.
- Catalogue the input needs of every enabled task type and group them by
  reusable capability.
- Catalogue real output manifests from the runtime-family smoke matrix.
- Write contract tests for plugin selection, teardown, fallback, validation,
  path preservation, and bounded fetching before moving behavior.
- Decide the minimum additive schema and manifest metadata; document versioning
  and unknown-plugin behavior.

### Phase 1: extract stable hosts and registries

- Extract an input workspace host from `create-task.js` while preserving the
  current generated form as the default plugin.
- Extract the existing result `previewPlugins` registry into separate local
  modules with a single lifecycle contract.
- Centralize authenticated range fetching, byte limits, error states, object-URL
  cleanup, focus management, and plugin teardown.
- Add a development-only registry diagnostics view or test helper; do not expose
  internal paths or sensitive configuration.

### Phase 2: reusable input plugins

- Implement files, sequence, typed-parameters, structure, regions, and review
  plugins.
- Add deterministic serialization from plugin state to the existing API
  submission payload.
- Ensure task switching destroys prior plugin state so parameters never leak
  across task types.
- Preserve non-JavaScript/basic-form behavior where practical.

### Phase 3: RFdiffusion and PLACER pilot

- Compose RFdiffusion from reusable plugins and validate primary plus nested
  auxiliary uploads.
- Verify `TASK_INPUTS` points to the complete snapshot root while the primary
  file is passed explicitly.
- Reuse the structure/files workspace for PLACER and verify it receives every
  nested PDB/mmCIF input.
- Test visual and raw contig editing against the exact pinned RFdiffusion
  adapter arguments.
- Run the smallest production-safe server-to-SLURM-to-Apptainer smoke cases.

### Phase 4: result plugin extraction and scientific views

- Move text, table, image, and Mol* viewers behind the shared result contract.
- Add gallery composition from manifest roles/groups rather than task-name
  conditionals.
- Add linked table/structure selection only after associations are represented
  explicitly in the manifest.
- Keep archive generation separate from previewing and downloads.

### Phase 5: migrate remaining task families

- Capture real manifests before declaring mappings for upstream-owned output trees.
- Adopt input capabilities for MPNN, ESM/DMS, PRIME, GREMLIN, OpenDDE, BioEmu,
  and EASIFA incrementally.
- Add domain viewers only when supported by real output artifacts and bounded
  browser behavior.
- Remove old page-specific listeners only after parity tests pass.

### Phase 6: cross-task composition

- Accept only authorized immutable `{task_id, artifact_path, sha256}` source references.
- Validate destination input compatibility, then copy or hardlink into a new task snapshot; never retain live result-tree symlinks.
- Record minimal lineage and define source-retention behavior without introducing a DAG engine.

### Phase 7: production hardening

- Test desktop, narrow/mobile, keyboard-only, and basic screen-reader flows.
- Test plugin failures, slow/ranged responses, cancelled navigation, oversized
  artifacts, malformed manifests, and unavailable viewer assets.
- Verify logout and authorization boundaries for every artifact request.
- Run workspace isolation, traversal, symlink, multi-upload, cleanup, and
  optional-archive regressions.
- Activate through the prepared-image path only after all server and static
  assets are built, pinned, integrity-checked, and rollback-ready.

## Required tests

- Unit tests for capability resolution and deterministic plugin ordering.
- Contract tests shared by every input and result plugin.
- Schema tests rejecting unknown capability fields where they would weaken
  validation, while tolerating unknown optional presentation hints.
- DOM tests for mount/destroy cycles, task switching, focus, and error isolation.
- API tests proving browser hints cannot broaden accepted files or parameters.
- Security tests for path traversal, unsafe filenames, HTML/script content,
  unauthorized artifact access, and remote plugin injection.
- Performance tests demonstrating bounded reads and cleanup of object URLs,
  viewers, workers, and event listeners.
- End-to-end tests for RFdiffusion nested uploads, PLACER multi-structure input,
  MPNN structure selection, manifest galleries, individual downloads, byte
  ranges, previews, and optional ZIP behavior.

## Acceptance criteria

- Adding a standard task requires registry composition and a runner adapter,
  not edits to the central create-task page.
- Adding a preview format requires registering one local plugin, not editing
  artifact selection, error, download, or archive workflows.
- Unknown or failed plugins fall back safely without hiding artifacts.
- Server validation remains authoritative and all task inputs remain isolated.
- The input workspace preserves nested relative paths and explicit file roles.
- Result viewers operate only on manifest-approved, authorized artifacts.
- Large files are ranged, streamed, summarized, or rejected from inline preview.
- Task switching and page navigation leave no stale parameters, event handlers,
  network requests, object URLs, or viewer instances.
- RFdiffusion and PLACER pass real minimal SLURM/Apptainer smoke tests through
  the composed input workspace.
- Existing task submission, artifact download, optional archive, and cleanup
  behavior remain backward compatible throughout migration.

## Explicit non-goals for the first cycle

- No third-party marketplace or runtime-downloaded plugin code.
- No arbitrary JavaScript or command templates in YAML.
- No shared mutable username workspace.
- No browser-side construction of trusted runner commands.
- No automatic recursive ZIP creation.
- No complete visual redesign of unrelated dashboard or administration pages.
- No removal of the generic form or download fallback until all supported tasks
  have equivalent tested behavior.

## Design decisions

- Capability and result-view composition live declaratively in
  `task_types.yaml`; the server validates and serializes versioned documents.
- Linked results use named, plugin-owned views and groups rather than a general
  association graph.
- Node lifecycle contracts are complemented by native Chromium tests through
  Playwright.
- RFdiffusion exposes unconditional, motif-scaffolding, binder, and expert
  modes; Python normalization remains the syntax authority.
- Input workspace varieties are independently registered modules selected by
  task type; shared host code does not branch on task names.

Draft persistence remains outside this cycle. Production activation still
requires the smoke and accessibility gates listed above.

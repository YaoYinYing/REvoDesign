# Scientific result-view plugins

Result views are a protocol between the server-owned task registry, the
published schema-v3 manifest, and the browser result host. They describe how a
scientist reads a result; they do not identify a task by name or grant the
browser access to undeclared files.

## Design test

Add a view only when it helps answer at least one scientific question:

1. What did the method produce?
2. Which candidates, residues, frames, or measurements matter most?
3. How confident or complete is the result?
4. What evidence supports the interpretation?
5. What should be inspected or exported next?

If a bounded text, image, table, structure preview, or download already answers
the question, use that existing preview. Do not add a plugin, task-name branch,
or plotting dependency merely to make the page more visual.

## Authoritative boundary

- `server/config/task_types.yaml` declares `result_workspace.views`.
- The server validates plugin IDs, sources, mappings, roles, and identifiers at
  startup and resolves selectors only against manifest-approved artifacts.
- The result manifest records resolved relative paths; it never publishes host
  paths, globs, commands, or credentials.
- The browser renders the resolved manifest. It does not infer scientific
  meaning from task names or duplicate the task registry.
- Every result keeps the searchable artifact list and authenticated download as
  a fallback, even when a view fails or an artifact is too large to preview.

Historical manifests that predate schema v3 may lack the task snapshot,
workspace mapping, units, numbering, or output checks required for a scientific
view. Do not guess or reconstruct missing scientific metadata in JavaScript.

## View declaration

Every view has exactly these fields:

```yaml
result_workspace:
  views:
    - plugin: candidate-collection
      id: ranked_models
      role: primary
      title: Ranked structure models
      description: Models in the ranking order published by the method.
      sources:
        candidates:
          - {glob: "*/ranked_*.pdb", required: true}
      mapping:
        confidence_encoding: plddt_bfactor
```

- `plugin` is an allowlisted local protocol implementation.
- `id` is stable within the task type and identifies checks and linked state.
- `role` is `primary` or `evidence`; at most the scientifically principal view
  should be primary.
- `title` names the scientific object, not the widget type.
- `description` states what the view contains without making unsupported
  accuracy or validity claims.
- `sources` maps protocol-defined source roles to ordered selectors. Each
  selector is an exact `path` or `glob` plus `required: true|false`.
- `mapping` supplies only protocol-defined semantics such as entity keys,
  residue numbering, labels, units, or confidence encoding.

A required selector means that a scientifically complete run must publish a
non-empty match. Missing required output is reported by `output_check`; it must
not be hidden by a friendly empty state. Optional sources may render an explicit
empty state.

## Built-in protocols

### `candidate-collection`

Use for comparable generated or ranked candidates such as predicted structures
or accepted designs. `sources.candidates` is required;
`sources.supporting` is optional. Candidate order follows the resolved manifest
order. `mapping.confidence_encoding: plddt_bfactor` enables pLDDT colouring only
when B factors actually carry pLDDT.

The view must provide candidate identity, size, shortlist control, bounded
single-candidate preview, and download. Switching candidates cancels or ignores
stale asynchronous renders.

### `entity-table`

Use when rows identify scientific entities and optionally link them to a
structure. `sources.table` is required; `sources.structure` is optional unless
the scientific claim depends on the link. `mapping.entity` is `residue`,
`mutation`, or `candidate`; `key_columns` identifies a row; `label_column` names
it. A residue link additionally declares `chain_column`, `residue_column`, and
`numbering` (`label_seq_id` or `auth_seq_id`). `evidence_columns` identifies the
values a scientist should compare.

Tables are paged by the server. Selection must remain stable across pages and a
selection made before Mol* is ready must replay once the structure is loaded.

### `evidence-bundle`

Use for a small, ordered set of heterogeneous evidence that is interpreted
together, for example an alignment, PSSM, and coupling map. `sources.items` is
required and `mapping` is currently empty. Each artifact delegates to the
standard bounded preview selected by manifest `preview` metadata.

This is not a miscellaneous-files gallery. Diagnostics and unrelated outputs
stay in the artifact list.

## Candidate future protocols

Add these only after a living task publishes stable data and a contract test
pins its semantics.

### `trajectory`

Use for a multi-model structure or coordinates associated with one topology.
The source roles should be `topology` (PDB/mmCIF, required) and `coordinates`
(multi-model PDB or a trajectory such as XTC/DCD, required). Mapping must declare
time units and timestep when they are not encoded in the trajectory, plus an
optional alignment selection.

The Mol* implementation should provide model/frame selection, previous/next,
play/pause, a scrubber, frame/time readout, playback speed, and optional
alignment. XTC/DCD must never be opened without its declared topology. Loading
is bounded or streamed; changing views aborts pending topology/trajectory work.
Plotting libraries are not trajectory renderers.

### quantitative metric views

Use a metric/table protocol for stable numeric schemas such as per-residue
pLDDT, PAE, pTM/iPTM, ranked candidate scores, RMSF, or dihedral angles. Mapping
must declare the entity key, value columns, units, missing-value behavior, and
whether higher or lower is favourable. Thresholds and colour scales must come
from the scientific contract, not browser guesses.

Prefer native SVG/canvas or an already-installed dependency. Add a maintained
plot library only when interaction such as linked brushing, zoom, or multiple
large series materially improves interpretation. A Ramachandran view must show
phi/psi definitions, residue identity, allowed-region provenance, outliers, and
selection linkage to the structure; a decorative scatter plot is insufficient.

## Browser lifecycle and safety

Every plugin is resolved locally and implements the existing preview-host
lifecycle:

- render only into its supplied surface;
- fetch only manifest URLs through authenticated helpers;
- honour `AbortSignal` and the host generation after every asynchronous step;
- enforce byte, row, candidate, and cache bounds before downloading;
- revoke object URLs and remove listeners on destroy;
- isolate a failure to the active preview and keep artifacts/download usable;
- expose loading, empty, partial, failed, unsupported, and oversized states;
- preserve keyboard operation, visible focus, accessible names, status updates,
  and non-colour encodings.

The Mol* shell remains sandboxed. CDN assets must be pinned with SRI and may not
be vendored into the repository.

## Implementation gate

Before declaring a plugin or mapping complete:

1. Capture a real API → worker → SLURM → Apptainer result manifest.
2. Confirm every required selector against actual non-empty artifact paths.
3. Record the scientific question, entity keys, units, numbering, confidence
   encoding, and interpretation direction from the pinned tool contract.
4. Add startup validation for every source and mapping field.
5. Add one manifest contract test and one browser interaction/error-state test.
6. Verify bounded fetching, stale-render cancellation, fallback downloads, and
   keyboard/accessibility behaviour.
7. Live-test the canonical result page and confirm a scientist can identify the
   outcome, limitations, evidence, and next action without opening raw logs.

Do not mark a task type complete merely because its files appear in the generic
artifact list.

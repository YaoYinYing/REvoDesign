# TODO: Universal scientific result-view protocols

> Superseded for task-level meaning. Generic format renderers remain useful, but
> new scientific result composition belongs to each runner's ResultStoryboard.

Status: next goal after the result-workspace redesign PR. Do not expand the
current PR with these feature tracks. The current implementation establishes
schema-v3 manifests, server-declared ordered views, output checks, bounded
artifact previews, shortlist export, and candidate/entity/evidence protocols.

The normative plugin contract is
[`docs/dev-guide/result-view-plugins.md`](../docs/dev-guide/result-view-plugins.md).
This TODO tracks the remaining product work.

> Completed 2026-09-01. The checkboxes below are the original planning record;
> the completion evidence is the live inventory and the contract tests.

## Goal

Every enabled task type should publish a result page that lets a scientist
identify the outcome, completeness, strongest evidence, uncertainty or
confidence, and next inspection/export action without reading execution logs.
The protocol must remain task-name-independent, server-owned, bounded,
accessible, modular, and ordered.

## Current audit

- 23 task types are enabled in the live registry.
- All 23 enabled task types now declare a scientific result view, except ESM-2
  tensors where authenticated download is the documented scientific result.
- Implemented composition protocols: `candidate-collection`, `entity-table`,
  and `evidence-bundle`.
- Implemented artifact previews: bounded text, table, image, structure, and
  download fallback.
- YAML view order and selector order survive registry loading and manifest
  publication. The browser renders tabs in manifest order and selects the
  first `primary` view initially.
- Artifact and scientific-view renderers share one registry/host lifecycle for
  cancellation, stale-generation guards, error isolation, and teardown.
- Trajectories/ensembles, scalar and series metrics, matrices/heatmaps,
  alignments, confidence/error maps, and linked quantitative selections are
  first-class protocols.
- Historical schema-v2 manifests lack the result-workspace/output-check data
  needed for this UI. Do not invent browser compatibility mappings for them.
- The 2026-08-27/2026-09-01 living matrix completed all 23 enabled task types
  through API, worker, SLURM, and Apptainer. PRIME and PRIME-DMS use exact
  SHA-256-checked local snapshots and both live runs finished with passing
  schema-3 output checks.

## Phase 0 — finish the living inventory

- [ ] Complete one minimal API → worker → SLURM → Apptainer run for every
  enabled task type using `server/tests/live_task_matrix.py`.
- [ ] Store, for each run: manifest schema, artifact paths/media/size, output
  check, stage/result status, runtime, and SLURM resource outcome.
- [ ] Classify every non-empty artifact by scientific entity and question, not
  by extension alone.
- [ ] Record units, residue numbering, candidate ordering, confidence meaning,
  score direction, topology/trajectory association, and missing-value rules
  from the pinned tool contract.
- [ ] Separate real protocol gaps from bad smoke inputs, missing weights,
  unavailable hardware, and incomplete scientific outputs.

## Phase 1 — freeze the minimum universal vocabulary

Choose the smallest protocol set that covers the real manifest inventory.
Candidate additions, only when justified by Phase 0 data:

- [ ] `trajectory`: required topology plus multi-model PDB or XTC/DCD
  coordinates; model/frame selection, play/pause, scrub, time/frame readout,
  speed, and optional alignment.
- [ ] `metric-table`: typed entity keys, values, units, uncertainty, ranking
  direction, and optional linked structure/candidate selection.
- [ ] `metric-series`: ordered numeric series such as per-residue pLDDT or
  RMSF, with units, missing values, zoom/brush only when materially useful, and
  linked selection.
- [ ] `matrix`: bounded symmetric/asymmetric matrices such as PAE, contacts, or
  mutation scans, with axes, units, colour scale, and click-through entity
  mapping.
- [ ] `alignment`: sequence/alignment conservation and column selection when a
  text preview cannot answer the scientific question.
- [ ] `scalar-summary`: a small declared set of run/candidate values such as
  pTM, iPTM, ipSAE, or aggregate confidence; never parse these from filenames.

Do not create separate plugins for each task type. Compose protocols when a
method needs structure + metrics, candidates + ranking, or trajectory + series.

## Phase 2 — ordered modular registry

- [ ] Keep one local allowlist in Python and one local browser registry; reject
  unknown plugins and unknown source/mapping keys at startup.
- [ ] Preserve declared view order, source selector order, and resolved
  artifact order end to end. Document any protocol-owned secondary sort.
- [ ] Enforce at most one principal initial view and deterministic behaviour
  when no view is primary.
- [ ] Give every plugin the same scoped services: authenticated fetch/ranges,
  `AbortSignal`, host generation, bounded object URLs/cache, status rendering,
  and owned event cleanup.
- [ ] Keep plugins independent of task names. A task-specific branch belongs
  in server normalization or a narrowly declared mapping field.
- [ ] Split browser modules only where it improves ownership/testing; do not add
  a framework, dynamic plugin loader, remote plugin URL, or speculative SDK.
- [ ] Preserve the generic artifact tree and authenticated download when any
  plugin is empty, incomplete, unsupported, oversized, or failed.

## Phase 3 — trajectory and ensemble viewing

- [ ] Verify Mol* APIs and supported topology/coordinate combinations against
  maintained upstream documentation before implementation.
- [ ] Multi-model PDB: expose state/model count, select, previous/next, and
  playback without flattening models into one structure.
- [ ] XTC/DCD: require an explicit PDB/mmCIF topology association; never infer
  topology from filename proximity.
- [ ] Display frame or physical time with declared units/timestep, playback
  speed, scrubber, and optional alignment selection.
- [ ] Use bounded/range/streamed loading and abort stale topology/coordinate
  work on view changes.
- [ ] Link trajectory frame selection to any declared RMSD/RMSF/energy series.
- [ ] Keep Plotly or another plotting library out of atom rendering. Add a
  maintained plotting dependency only if native SVG/canvas cannot satisfy the
  demonstrated metric interaction, and load CDN assets pinned with SRI.

## Phase 4 — scientist-facing mappings by task family

Final mappings depend on Phase 0 manifests; these are hypotheses to verify:

- GREMLIN: alignment + PSSM + coupling/contact evidence and linked residue-pair
  scores.
- Pythia-ddG, ESM-1v, PRIME-DMS, ThermoMPNN: mutation entity table/matrix with
  score units/direction and structure or sequence linkage where available.
- ESM-MSA/ESM-2: alignment/contact matrix and embedding metadata; raw tensor
  arrays remain downloads unless a scientific summary is declared.
- ESM-IF1 and MPNN variants: ranked sequence candidates, scores/probabilities,
  designed-chain context, and optional structure linkage.
- ESMDynamic: contact/frequency/kinetics evidence; do not label predictions as
  an MD trajectory.
- OpenDDE, RFdiffusion, PLACER, FreeBindCraft: candidate structures with ranking,
  per-candidate confidence, ligand/interface context, and generated trajectories
  only when actual topology/frame semantics are available.
- BioEmu: ensemble/trajectory plus structural variability metrics and sampling
  limitations.
- EASIFA: residue entity table linked to the enzyme structure, including class
  probabilities.
- AlphaFold/ColabFold: ranked structures, pLDDT, PAE, pTM/iPTM where produced,
  model/ranking provenance, and honest absent-metric states.
- PRIME: scalar prediction plus method-defined interpretation and limitations.

## Phase 5 — implementation and release gates

For each new protocol:

- [ ] Add server dataclasses/allowlists and fail-closed source/mapping
  validation.
- [ ] Add manifest resolution/output checks using real artifact selectors.
- [ ] Add one manifest contract test and one browser lifecycle/interaction/error
  test.
- [ ] Test empty, partial, failed, oversized, stale, aborted, and unsupported
  states; keep downloads working.
- [ ] Test keyboard use, focus, accessible names, live status, non-colour
  encodings, and mobile layout.
- [ ] Live-test canonical HTTPS with the task type that justified the protocol.
- [ ] Review the page as a scientist: outcome, evidence, uncertainty,
  limitations, and next action must be legible without raw logs.
- [ ] Update `CHANGELOG.md`, the normative plugin guide, and the task mapping
  inventory.

Completion means every enabled task type has either a validated scientific view
or a documented reason why bounded generic artifacts are the scientifically
correct presentation. File visibility alone is not completion.

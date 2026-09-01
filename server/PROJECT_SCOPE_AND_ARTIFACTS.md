# Project Scope, Storage, and Artifact References

REvoCompute tasks belong to exactly one authoritative scope. Scope controls
authorization, discovery, storage, and artifact reuse; it is not presentation
metadata.

```text
User
 |
 +-- Personal Scope
 |     `-- Task
 |          `-- Artifact
 |
 `-- Project Membership
        `-- Project Scope
             `-- Task
                  `-- manifest Artifact
                         `-- ArtifactReference
                                `-- downstream Task input snapshot
```

## Authorization

Global account roles (`admin`, `user`, and `guest`) remain independent from
Project roles. Project roles are `owner`, `maintainer`, `contributor`, and
`viewer`; the collaboration service maps them to explicit capabilities.
Routes ask capability questions rather than interpreting role names.

Visibility controls non-member discovery and reading:

- `private`: members only; unknown callers receive the same response as a
  missing Project.
- `internal`: authenticated non-members may discover the read-only Project
  surface.
- `public`: anonymous callers may discover the read-only Project surface.

Visibility does not grant membership, submission, artifact reuse, diagnostic
downloads, or future runner-policy eligibility. A viewer can read Project
results but cannot reuse artifacts. Task mutation requires `cancel_own_tasks`
or `cancel_project_tasks`, independently of read access.

## Scoped storage

Usernames and Project names are presentation metadata. Each user and Project
receives a persistent storage key with a readable initial prefix and random
opaque suffix. Renames never update that key or move result trees.

New task paths are resolved only by `StorageResolver`:

```text
results/
  users/<user-storage-key>/tasks/<task-id>/
  projects/<project-storage-key>/tasks/<task-id>/
```

Input snapshots use the same scope hierarchy beneath the configured input
root. The physical hierarchy is an implementation detail and not an API.
Routes, workers, Docker/SLURM jobs, manifest finalization, archives, recovery,
and cleanup resolve paths from the persisted task scope.

Project Scope ships with a fresh schema contract. Deployments adopting this
version rebuild the REvoCompute databases and storage roots; there is no old
task-layout resolver or username-based fallback. Every task row is complete at
creation and every path is derived from its immutable scope identity.

## Artifact references

An input may use `@<task-id>/<logical-artifact-path>`. This is submission syntax
only. Before any physical lookup, the server loads the source task and checks
that the caller may reuse artifacts in the same Personal or Project scope.
Cross-user and cross-Project reuse is denied.

The storage resolver then requires a finalized source task and an exact entry
in its authoritative result manifest. It rejects absolute paths, traversal,
empty path segments, symlinks, missing files, and content that no longer
matches the manifest hash or size. The caller never supplies or receives a
host, container, SLURM, or storage-key path.

An authorized artifact is copied into the downstream task's immutable input
snapshot and appears to the runner as an ordinary local input. Provenance
records the downstream input, source task and scope, logical artifact path,
SHA-256, size, media type, and timestamp.

```text
provenance propagates
permissions do not
```

Archiving or renaming the source scope therefore cannot mutate a submitted
downstream task, and access to the downstream task does not grant access to the
upstream task.

---
name: sql-review
description: Review SQLite + SQLAlchemy queries in the REvoDesign server for correctness, safety, concurrency, and performance. Stronger and more specific than the generic loopkit sql-review — targets the actual patterns in server/pssm_gremlin/pssm_gremlin.py.
when_to_use: new query, schema change, migration, N+1 suspicion, slow dashboard, touching _ensure_columns or TaskDatabase
---

# SQL Review (REvoDesign Server)

The server uses **SQLite + SQLAlchemy Core** (not ORM) in `TaskDatabase` (`server/pssm_gremlin/pssm_gremlin.py`). No Alembic — schema evolution is hand-rolled. The app runs under gunicorn with multiple workers sharing one SQLite file.

## Injection — parameterized, always

SQLite runs in-process; SQL injection gives direct filesystem access. No string interpolation:

```python
# Correct: SQLAlchemy parameterized
conn.execute(text("SELECT * FROM tasks WHERE md5sum = :md5"), {"md5": md5})
# Wrong: f-string or %-formatting into SQL
```

## SQLite concurrency

SQLite handles one writer at a time; WAL mode is not enabled. With gunicorn workers:

- **Writes MUST be serialized** — if two workers `CREATE TABLE` or `ALTER TABLE` simultaneously, one gets `sqlite3.OperationalError: database is locked`.
- The current `metadata.create_all()` pattern catches "already exists" errors — this is fragile. Instead: use a migration lock table, or run schema changes once at startup before forking.
- `_ensure_columns()` reads `PRAGMA table_info` then runs `ALTER TABLE ADD COLUMN` — these can race across workers. A column could be added between the check and the ALTER. Wrap in a retry or run once at startup.
- Long-running writes (batch inserts) should use WAL mode: `PRAGMA journal_mode=WAL`.

## Schema discipline

The current schema has no formal migration system. `_ensure_columns()` only adds new columns — no renames, type changes, or drops.

When adding or changing a column:

- **Add nullable first, backfill later, then add NOT NULL.** Adding a NOT NULL with no default on an existing table fails immediately.
- **Never rename a column inline.** SQLite's `ALTER TABLE RENAME COLUMN` exists (3.25+), but if you rename a column that code accesses as both old and new names (like `"local user"` vs `local_user`), you'll break half the accessors. Pick one name and normalize all access.
- **Column names MUST NOT contain spaces.** The `"local user"` column forces `_normalize_task_row()` to bridge `task["local user"]` ↔ `task["local_user"]`. This is tech debt — rename it.
- **Add an index for every column in WHERE/JOIN/ORDER BY.** `status` and `username` are filtered on every dashboard load — they have no indexes. Add `CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)` and `... ON tasks(username)`.
- Typo preserved for compatibility: `"deleted:finshed"` — if you're touching the status enum, fix this. Otherwise, at least document it in the schema.
- **Schema changes → CHANGELOG entry.** Since there's no migration versioning, the changelog is the migration log.

## Query patterns

### SELECT by status (dashboard hot path)

```python
# Current: full scan on status
sel = tasks.select().where(tasks.c.status == "running")
# Fix: add index on status
```

### Batch operations on large result sets

- If `SELECT * FROM tasks` can return thousands of rows, add pagination or `LIMIT`. The dashboard already does client-side filtering from the full set — this is fine for moderate task counts but breaks at scale.
- `DELETE` operations on multiple tasks should run in a single transaction so partial failure can't leave orphaned files.

### N+1 suspicion

- The dashboard renders with one query (`SELECT * FROM tasks`), filters client-side. No N+1 risk in the current code.
- Any new code that queries per-task inside a loop: replace with a single batched query.

## Transactions for multi-step operations

Any operation that touches multiple rows or a row + a file must be transactional:

```python
with engine.begin() as conn:
    conn.execute(delete_stmt)
    # file cleanup after commit — don't delete files inside the transaction
```

Current code creates a new engine per request (`TaskDatabase._connect()`). This is fine for SQLite but means transactions don't span requests.

## Testing queries

Before deploying a schema or query change:

```bash
# Test locally with a copy of the production database
python -c "
from server.pssm_gremlin.pssm_gremlin import TaskDatabase
db = TaskDatabase('test.db')
db._connect()
# Run your query
db.engine.dispose()
"
```

## Red flags

- **`ALTER TABLE` in a request handler.** Schema changes must happen at startup, never during request processing.
- **`PRAGMA table_info` then `ALTER TABLE` without error handling.** Race window between gunicorn workers.
- **String-built SQL anywhere.** Even in debug logging — use SQLAlchemy's `str(stmt.compile())` or bind params.
- **Commit-then-file-cleanup without error handling.** If file deletion fails, the task is committed but the file persists.
- **No index on a column filtered thousands of times.** SQLite's query planner defaults to full table scan without indexes.

# ADR-0002: Atomic, serialized persistence for data.json

- **Status:** Proposed
- **Date:** 2026-10-22
- **Deciders:** archive team (system-architect, build)

## Context

The whole persisted state of the archive is one JSON array in `data.json` (records `{id, filename, tags[]}`) plus image files in `uploads/`. Today (`app.py`) the store is read with `load_data()` and written with `save_data()`, which does a direct `open(DATA_FILE, 'w')` truncating write, and every mutating route does its own load → mutate → save cycle with no coordination. The approved data model (`docs/design/art-reference-archive-data-model.md`) records three hazards this creates:

- **I5 — the store must be replaced whole.** US-003 AC 15 requires a global tag rename/delete to be all-or-nothing, and US-002 AC 12 requires a cancelled edit to leave stored tags untouched. A direct in-place write also means a crash mid-write leaves a truncated file — the persisted array must be either the complete old array or the complete new one.
- **I9 — read-modify-write has no lock.** Two overlapping requests (a double-clicked upload, a delete racing a tag save) can both load the old array and the later save silently drops the earlier update. The acceptable mitigation for this single-user app is to serialize writes inside the process.
- **I4 — delete can leave a dangling record.** The current `delete_picture` removes the file from `uploads/` *and then* rewrites `data.json`; a crash in between leaves a record whose `filename` resolves to nothing — exactly the forbidden failure direction. The invariant is "no dangling record"; an *orphaned file* (no record) is tolerated garbage.
- **Silent data loss on read failure.** `load_data()` returns `[]` when JSON parsing fails, so a truncated or corrupt file is presented to the user as an empty archive — and the next successful save makes that loss permanent.

Further constraints: no database and no new service (US-001 assumptions); stdlib only; the app runs on the Flask dev server as a single serving process (the debug reloader's watcher process serves no requests); the project must work on Windows (NTFS) and POSIX; the 7 existing records are not migrated.

## Decision

All reads and writes of `data.json` will go through a single store component that provides atomic, serialized persistence:

1. **Serialized critical section.** The store holds one `threading.Lock`. Every mutating operation — single upload, ZIP import, delete, per-picture tag edit, global tag rename/delete — executes its complete load → mutate-in-memory → single-write cycle inside that lock. Read-only endpoints (gallery, random viewer, slideshow) may read without the lock.
2. **Atomic write.** A save serializes the new array to a temporary file *in the same directory as* `data.json`, flushes and `os.fsync`s it, closes it, then commits with `os.replace(tmp, DATA_FILE)`. `os.replace` is atomic on both NTFS and POSIX, so the store on disk is always either the complete old array or the complete new one (I5). Tag operations compose the whole result in memory and write exactly once — never a rewrite per picture.
3. **Record-first delete ordering.** Deletion rewrites `data.json` (record removed) *first*, then removes the image file. A crash after the rewrite but before the file removal leaves an orphaned file — the tolerated direction — instead of a dangling record. Orphaned files may be cleaned up lazily later; nothing observes them as an error.
4. **Fail loudly on an unreadable store.** `load_data` stops returning `[]` on parse failure: a missing file or a valid empty array `[]` is a legal empty archive, but invalid JSON raises a store error. Mutating endpoints fail with an explicit error message and never save over a store they could not read, closing the silent-data-loss path.

The identity allocator from ADR-0001 runs under this same lock, so allocation and persistence are one consistent critical section.

## Consequences

- **Positive:** US-003 AC 15 and US-002 AC 12 hold by construction (one write per operation); overlapping requests can no longer lose whole updates in-process (I9); a crash mid-write can no longer truncate the store — the old array survives intact (I5); delete can no longer produce a dangling record (I4); a corrupt `data.json` surfaces immediately instead of being silently erased.
- **Negative:** all mutations serialize through one lock (irrelevant at single-user scale, but a throughput ceiling if the app ever grows); `fsync` adds milliseconds per save (acceptable for a local single-user tool); the in-process lock protects nothing if the app is ever deployed as multiple worker processes — documented limitation, revisited only if that deployment happens; a crash in the delete window leaves orphaned files that accumulate until cleaned (accepted garbage per I4).
- **Follow-ups:** implement the store class (load/save/lock/delete sequencing) and route all existing endpoints through it; replace the current `delete_picture` ordering; add an optional, deferred orphan-file sweep; tests: concurrent tag-edit + upload, kill-mid-write (verify old array intact), delete crash window (verify no dangling record), corrupt `data.json` (verify loud failure and no save-over).

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| Keep the current direct `open('w')` write | Truncates the file before writing, so a crash mid-write destroys the archive (violates I5); no locking, so lost updates remain (I9); silent `[]` on corrupt read stays open. |
| Migrate to SQLite | Rejected by constraint: US-001's assumptions keep `data.json` + `uploads/` as the persistence surface and introduce no database; the data model documents the JSON array as the store of record; migrating 7 records buys atomicity we can get from `os.replace` at far lower cost. |
| File-level locking (fcntl / portalocker / lockfile) | `fcntl` is POSIX-only and this project must run on Windows; library lockers add a dependency the constraints exclude; a file lock solves cross-*process* coordination this single-process app does not have, while leaving the truncating-write and delete-ordering hazards unsolved. |
| Atomic rename without the lock | Fixes truncation (I5) but not lost updates (I9): two interleaved load → mutate → rename cycles still each commit an array computed from the old state, and the earlier update still vanishes — atomicity of a write is not serialization of the read-modify-write cycle. |

## Links

- `docs/design/art-reference-archive-data-model.md` — invariants I4, I5, I9 (delete ordering, whole-store replacement, unlocked read-modify-write); I8 (existing records must keep loading unchanged)
- `docs/requirements/US-002-tag-editing-and-deletion.md` — US-002 AC 12 (cancel leaves tags untouched), US-003 AC 15 (all-or-nothing global operations)
- ADR-0001 — batch-safe identity allocation; runs under this store's lock

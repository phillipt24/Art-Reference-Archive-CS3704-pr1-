# ADR-0001: Batch-safe picture identity and stored-filename generation

- **Status:** Proposed
- **Date:** 2026-10-22
- **Deciders:** archive team (system-architect, build)

## Context

Every picture record in `data.json` carries `{id, filename, tags[]}`, and today both the `id` and the stored `filename` are derived from the wall clock at upload time (`app.py`: `int(time.time() * 1000)` for the id, `f"{int(time.time() * 1000)}{ext}"` for the filename). That is safe for one upload per human click and unsafe the moment ids are allocated in a loop: US-001 requires importing up to 200 ZIP entries inside a single request, and entries processed within the same millisecond receive the *same* id and the *same* filename.

The approved data model records the consequences (`docs/design/art-reference-archive-data-model.md`):

- **I1 — id uniqueness:** duplicate ids are silent failures — `DELETE /api/pictures/<id>` removes the first match, `exclude_ids` in the random viewer excludes both records, and the tag editor writes to whichever record matches first. An import of 200 entries makes a collision near-certain, not hypothetical. The id must remain a JSON integer (not a string, not a UUID) that survives `int(...)`, Flask's `<int:picture_id>` converter and `jsonify`.
- **I2 — filename uniqueness:** two imports in one clock tick target the same path in `uploads/`, so one image's bytes replace the other's on disk while both records claim to exist. The stored filename must be a basename — no `/`, no `\`, no `..`, no drive letter — and only the extension may be carried over from the source name (the current single upload already discards the original basename). A name collision with an existing picture must create a *new* record with a *new* filename, never an overwrite.
- **I7 — no migration, no clock meaning:** the 7 existing records have epoch-millisecond ids; they are not migrated, nothing may depend on ids being timestamps or numerically ordered (display order is array order), and no new required field may be added.

Further constraints: the application is single-user and unauthenticated; there is no database; stdlib only; no new service is introduced (US-001 assumptions). All allocations happen inside the single serving process.

## Decision

We will allocate picture ids from a single strictly-increasing integer allocator owned by the store component (see ADR-0002), computed as:

```
next_id = max(last_allocated + 1, int(time.time() * 1000))
```

`last_allocated` is seeded once, when the store first loads `data.json`, from the maximum id among existing records (0 if the archive is empty). Every subsequent allocation bumps `last_allocated`, so ids never repeat within a process even when 200 entries are imported inside one request.

The stored filename is derived from the same allocation: `filename = f"{allocated_id}{ext}"`, where `ext` is the lowercased extension of the source file. Because the id is unique per record and the filename embeds it, filename uniqueness follows from id uniqueness with no separate mechanism. The importer validates the extension against the supported set `{jpg, jpeg, png, gif, webp}` (US-001 AC 4); the existing single-image upload keeps its current extension behavior (US-001 AC 3).

Allocation and persistence run under the store's write lock (ADR-0002), so no two requests can observe or reuse the same `last_allocated` value.

## Consequences

- **Positive:** one mechanism guarantees both I1 and I2 — batch imports of 200 entries cannot collide on id or filename; ids remain JSON integers in the familiar epoch-millisecond magnitude, so `<int:picture_id>`, `jsonify` and the 7 existing records stay compatible with zero migration; the derivation `filename = id + ext` removes the separate filename-uniqueness code path and satisfies I2's "collision creates a new record, never an overwrite" rule by construction.
- **Negative:** ids roughly reveal creation time (harmless — single user, and I7 already forbids relying on id ordering); the allocator is in-process, so a future multi-process deployment (e.g., gunicorn workers) would need a cross-process scheme — accepted, since the app runs as one serving process on the Flask dev server; the store must successfully load `data.json` once to seed the allocator, so an unreadable store now fails loudly (ADR-0002) instead of quietly re-seeding from zero.
- **Follow-ups:** implement the allocator inside the store class; after any bulk import, verify the data-model check `len({r['id'] for r in data}) == len(data)` and the same for `filename` (I2's verification note); add a regression test that imports >200-entry batches from one request.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| Keep epoch milliseconds (status quo) | Collides whenever two allocations land in the same millisecond — near-certain for a 200-entry import loop (I1, I2); no ordering fix can repair records that were already merged or overwritten. |
| UUID-derived integer (e.g., `uuid.uuid4().int`) | A full 128-bit UUID exceeds the safely-representable JSON/JS integer range (2^53), so `jsonify` and any JS consumer silently lose precision; truncating reintroduces collisions probabilistically; ids also stop fitting the "integer in a familiar magnitude" property I1 asks to preserve. |
| Random large integer (e.g., `secrets.randbits(63))` | Uniqueness is only probabilistic (astronomically unlikely but nonzero, and untestable in the I2 verification check); harder to debug ("which record is newer?"); gains nothing over a deterministic counter in a single-process app. |
| Pure monotonic counter seeded at `max(existing ids) + 1`, ignoring the clock | Correct, but new ids drift far below/above the epoch-ms magnitude of the 7 existing records for no benefit; the `max(last + 1, epoch_ms)` form is equally simple and keeps ids in a range consistent with existing data. |

## Links

- `docs/design/art-reference-archive-data-model.md` — invariants I1, I2, I7 (identity, filename, no-migration); I2's post-import verification check
- `docs/requirements/US-001-zip-bulk-upload.md` — AC 3 (single upload unchanged), AC 4 (extension gate), AC 9/10 (duplicate names, collisions with existing pictures)
- ADR-0002 — atomic, serialized persistence; the allocator runs under the same write lock

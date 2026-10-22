# Sequence Diagram: Bulk ZIP Import (US-001)

Scope: one `POST` of a `.zip` archive, from the owner's click to the rendered import report. The diagram shows the *proposed* design: the importer, store and allocator components do not exist in `app.py` yet. Tag editing (renaming, removing or adding tags after upload) is out of scope for now; the only tag behavior here is that imported pictures are saved untagged.

## Design rules this diagram follows

The diagram depends on four rules. They are stated here so this document stands on its own.

- **R1 - Unique ids, even in a batch.** Today `app.py` uses `int(time.time() * 1000)` for both the id and the filename, so two entries imported in the same millisecond would get the same id *and* overwrite each other's file. Instead, ids come from one allocator: `next_id = max(last_allocated + 1, int(time.time() * 1000))`, seeded from the largest existing id when `data.json` is first loaded. The stored filename is `f"{id}{ext}"`, so a unique id gives a unique filename. Ids stay plain integers, so `<int:picture_id>` routes and the 7 existing records keep working without migration.
- **R2 - One lock, one atomic save.** Every change to `data.json` runs load → change in memory → save inside a single `threading.Lock`. The save writes a temp file in the same folder, `fsync`s it, and then `os.replace`s it onto `data.json`, so the file on disk is always either the complete old array or the complete new one. A whole import is saved once, not once per picture.
- **R3 - No record without its file.** A record must never point to a missing image (the user would see a broken tile). An image file with no record is harmless leftover and is tolerated. So files are written *before* the record that names them is saved.
- **R4 - Fail loudly on a corrupt store.** Today `load_data()` returns `[]` if `data.json` can't be parsed, and the next save would wipe the archive. Instead, a missing file or `[]` is a legal empty archive, but invalid JSON raises `StoreError`, and nothing is ever saved over a store that couldn't be read.

## Diagram

```
  [ Owner ]        [ :ImportRoute ]     [ :ZipImporter ]     [ :PictureStore ]    [ :IdAllocator ]      [ :UploadsDir ]
      |                    |                    |                    |                    |                    |
      | 1. POST /api/import-zip                 |                    |                    |                    |
      |------------------->|                    |                    |                    |                    |
      |                    | 2. import_archive(upload)               |                    |                    |
      |                    |------------------->|                    |                    |                    |
      |                    |                    |---+  3. check_archive_gates(upload)     |                    |
      |                    |                    |<--+                |                    |                    |
+--alt [archive refused: >100 MB | unreadable | >200 entries | >500 MB extracted] ------------------------------------+
      |                    | 4a. ImportResult(0, msg)                |                    |                    |
      |                    |< - - - - - - - - - |                    |                    |                    |
      | 5a. 400 {message}  |                    |                    |                    |                    |
      |< - - - - - - - - - |                    |                    |                    |                    |
+--else [archive accepted] -------------------------------------------------------------------------------------------+
+--loop [for each entry in the archive] ------------------------------------------------------------------------------+
      |                    |                    |---+  4. validate_entry(info)            |                    |
      |                    |                    |<--+                |                    |                    |
+--opt [entry invalid] -----------------------------------------------------------------------------------------------+
      |                    |                    |---+  5. failures.append(ImportFailure(archive_path, reason)) |
      |                    |                    |<--+                |                    |                    |
+---------------------------------------------------------------------------------------------------------------------+
+---------------------------------------------------------------------------------------------------------------------+
      |                    |                    | 6. add_pictures(valid_entries)          |                    |
      |                    |                    |------------------->|                    |                    |
      |                    |                    |                    |---+  7. acquire write lock              |
      |                    |                    |                    |<--+                |                    |
      |                    |                    |                    |---+  8. records = load()                |
      |                    |                    |                    |<--+                |                    |
+--loop [for each valid entry] ---------------------------------------------------------------------------------------+
      |                    |                    |                    | 9. next_id()       |                    |
      |                    |                    |                    |------------------->|                    |
      |                    |                    |                    | 10. id             |                    |
      |                    |                    |                    |< - - - - - - - - - |                    |
      |                    |                    |                    | 11. write(f"{id}{ext}")                 |
      |                    |                    |                    |---------------------------------------->|
      |                    |                    |                    |---+  12. records.append({id, filename, tags: []})
      |                    |                    |                    |<--+                |                    |
+---------------------------------------------------------------------------------------------------------------------+
      |                    |                    |                    |---+  13. save_atomic(records)           |
      |                    |                    |                    |<--+                |                    |
      |                    |                    |                    |---+  14. release write lock             |
      |                    |                    |                    |<--+                |                    |
      |                    |                    | 15. added: list[Picture]                |                    |
      |                    |                    |< - - - - - - - - - |                    |                    |
      |                    | 16. ImportResult(n, failures, message)  |                    |                    |
      |                    |< - - - - - - - - - |                    |                    |                    |
      | 17. 200 {report}   |                    |                    |                    |                    |
      |< - - - - - - - - - |                    |                    |                    |                    |
+---------------------------------------------------------------------------------------------------------------------+
```

## Notation

- header row: participants. `Owner` is the human using the browser page; `:Type` participants are proposed server-side components
- vertical line: lifeline (time flows downward)
- `------>` solid arrow: synchronous call
- `< - - -` dashed arrow: return
- `---+` / `<--+`: self-call (the participant calls one of its own operations)
- `+--alt [...]` / `+--else [...]`: alternative fragment; exactly one branch runs
- `+--loop [...]`: repeated fragment; `+--opt [...]`: optional fragment that runs only when its guard holds
- a full-width `+-----+` line closes the innermost open fragment
- messages are numbered in time order; `4a`/`5a` are the refused-archive branch

## Scenario

- **Use case:** US-001, import many pictures from one ZIP archive (no `UC-###` assigned yet)
- **Preconditions:** the app is running; `data.json` is readable (missing or `[]` counts as an empty archive); the owner has selected a `.zip` in the bulk-upload control.
- **Outcome (accepted archive):** every valid entry is one new record `{id, filename, tags: []}` in `data.json` with its bytes at `uploads/<id><ext>`; every invalid entry is named in `failures[]` with a reason; `imported_count` equals the number of records actually added.
- **Outcome (refused archive):** nothing is written to `data.json` or `uploads/`; the report says why and `imported_count = 0`.

## Participants

| Participant | Responsibility in this scenario |
|-------------|---------------------------------|
| Owner | Picks the archive, then reads the report. Single user, unauthenticated. |
| :ImportRoute | Proposed Flask view for `POST /api/import-zip`. Only HTTP work: takes the upload, calls the importer, turns `ImportResult` into JSON and a status code. |
| :ZipImporter | Opens the archive with stdlib `zipfile` and applies every US-001 gate. Builds `ImportFailure`s and the final `ImportResult`. It never touches `data.json` and never builds a path inside `uploads/`. |
| :PictureStore | The single store (R2). Owns the write lock, `load()`, `save_atomic()` and the allocator. It is the only component that writes `data.json` or `uploads/`. |
| :IdAllocator | The id allocator from R1, seeded from the largest existing id the first time the store loads. |
| :UploadsDir | The `uploads/` folder on disk. |

## Messages

| # | From → To | Message | Kind |
|---|-----------|---------|------|
| 1 | Owner → :ImportRoute | `POST /api/import-zip`, multipart field `archive` | call |
| 2 | :ImportRoute → :ZipImporter | `import_archive(upload)` | call |
| 3 | :ZipImporter → itself | `check_archive_gates(upload)`: upload ≤ 100 MB; `zipfile.ZipFile` opens; ≤ 200 supported entries; sum of declared `file_size` ≤ 500 MB | self-call |
| 4a | :ZipImporter → :ImportRoute | `ImportResult(imported_count=0, failures=[], message)` naming the gate that failed | return |
| 5a | :ImportRoute → Owner | `400 {message, imported_count: 0, failed_count: 0, failures: []}` | return |
| 4 | :ZipImporter → itself | `validate_entry(info)`: skip directory entries; reject unsafe path (absolute, drive letter, `..` segment); extension in `{jpg, jpeg, png, gif, webp}`; bounded read ≤ 20 MB; not zero bytes; header bytes match the extension's image signature | self-call |
| 5 | :ZipImporter → itself | `failures.append(ImportFailure(archive_path, reason))` | self-call |
| 6 | :ZipImporter → :PictureStore | `add_pictures(valid_entries)`, each entry being `(archive_path, ext, bytes)` | call |
| 7 | :PictureStore → itself | acquire the write lock (`with self._lock:`) | self-call |
| 8 | :PictureStore → itself | `records = load()`; raises `StoreError` if `data.json` is corrupt (R4) | self-call |
| 9 | :PictureStore → :IdAllocator | `next_id()` | call |
| 10 | :IdAllocator → :PictureStore | `id` (strictly greater than every id handed out before) | return |
| 11 | :PictureStore → :UploadsDir | write bytes to `uploads/<id><ext>`; the name comes from the id, never from the archive path | call |
| 12 | :PictureStore → itself | `records.append({id, filename, tags: []})` | self-call |
| 13 | :PictureStore → itself | `save_atomic(records)`: temp file in the same folder, `fsync`, `os.replace` onto `data.json`. **One write for the whole batch.** | self-call |
| 14 | :PictureStore → itself | release the lock (a `with` block releases it even on an exception) | self-call |
| 15 | :PictureStore → :ZipImporter | the list of records added | return |
| 16 | :ZipImporter → :ImportRoute | `ImportResult(imported_count=len(added), failures, message)` | return |
| 17 | :ImportRoute → Owner | `200 {imported_count, failed_count, failures[], message}` | return |

## Design decisions shown by this diagram

1. **Validation runs before the lock; writing runs inside it.** Steps 3–5 read and check the archive without holding the store lock, so a slow 500 MB archive doesn't block a single upload or a delete for the whole time. Only allocation, file writes and the save (steps 7–14) are serialized. This is R2's critical section, kept as small as possible.
2. **Whole-archive gates run before any write** (step 3, branch `4a/5a`). A refused archive returns before the store is called, so it can't create records or files (AC 6, 11, 12, 14).
3. **Per-entry failures don't roll back their siblings** (the `opt` fragment). An invalid entry becomes one `ImportFailure`, and the loop continues (AC 4, 5, 13).
4. **Path safety by construction, plus explicit rejection.** The stored filename is `f"{id}{ext}"` (R1), so an archive path is never joined onto `uploads/`, and `../../x.png` can't escape the folder. AC 5 still requires the entry to be *named in the report*, so step 4 also rejects unsafe paths explicitly rather than quietly flattening them.
5. **File first, then record, then one save** (steps 11 → 12 → 13). If the process crashes between 11 and 13, files exist with no record. That is the harmless direction allowed by R3. A record is never saved before its file exists, so there can be no record pointing at a missing image.
6. **The report can't disagree with the store.** `imported_count` is computed from what `add_pictures` actually returned (step 15), not from how many entries passed validation.

## Error paths not drawn

These would clutter the main flow, so they are listed instead of drawn. Each one keeps the invariants above.

| Situation | Behavior |
|-----------|----------|
| `data.json` is corrupt at step 8 | `StoreError`; the lock is released; nothing is written; `500 {error}` and no import report, so nothing is claimed as imported. Never save over an unreadable store (R4). |
| A file write fails at step 11 (e.g. disk full) | That entry moves to `failures[]` with reason "could not be saved"; the loop continues with the next entry. |
| `save_atomic` fails at step 13 | `data.json` is still the complete old array (`os.replace` never ran). Files written in step 11 become leftover files with no record (allowed by R3). The response is `500 {error}` with no import report, so nothing is claimed as imported. |
| The archive lies about sizes (zip bomb) | The 500 MB gate in step 3 uses *declared* sizes, but step 4 reads each entry with a hard 20 MB cap and keeps a running total, so a forged header can't push extraction past the limits. |

## Traceability

| US-001 acceptance criterion | Where it holds in the diagram |
|-----------------------------|-------------------------------|
| AC 1, 15 (untagged, persists after restart) | step 12 `tags: []`; step 13 atomic save |
| AC 2 (untagged pictures and filters) | not in this flow: the existing filter in `app.py` already returns `tags: []` pictures for an empty filter and excludes them for any non-empty one |
| AC 3 (single upload unchanged) | separate route; `/api/upload` only changes in that it now goes through the same store |
| AC 4, 13, 16 (partial success, honest report) | `loop`/`opt` fragment; steps 15–17 |
| AC 5 (path escape rejected and reported) | step 4 path check; step 11 id-based filename |
| AC 6, 11, 12, 14 (whole-archive refusal) | step 3; branch 4a/5a |
| AC 7 (empty or no images) | the loop yields zero valid entries → report says 0 imported, with a reason per examined entry |
| AC 8, 9, 10 (nested folders, duplicate names, collisions) | steps 9–11: a new id and filename per entry, independent of the archive name |

## Open questions for the team

- **Endpoint name.** `POST /api/import-zip` is a proposal; the frontend only calls `/api/upload` today.
- **MB vs MiB.** US-001 doesn't say whether 1 MB is 1 000 000 or 1 048 576 bytes. Pick one before the limits are hard-coded (about a 5% difference).
- **Image signature check.** "Undecodable image" (AC 4) has to be checked without Pillow (stdlib only), and `imghdr` was removed in Python 3.13. The proposal is to compare magic bytes per format (`FF D8 FF`, `89 50 4E 47`, `GIF8`, `RIFF....WEBP`). That catches renamed non-images but not a truncated JPEG. Is that good enough?
- **Memory.** `valid_entries` holds the bytes in memory, bounded by the 500 MB gate. That's fine for a local single-user tool; streaming each entry inside the lock is the alternative if it ever matters.

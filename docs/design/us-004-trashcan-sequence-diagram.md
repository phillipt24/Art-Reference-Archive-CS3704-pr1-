# Sequence Diagram: Trash, Restore, and Permanently Delete a Picture (US-004)

Scope: the three flows of US-004: moving a picture to the trash, opening the trash and restoring a picture, and permanently deleting a picture from the trash. Requirements come from `docs/requirements/US-004-trashcan-soft-delete.md` (AC 1–20 plus the edge cases listed under its assumptions).

This is a **design for code not yet written**, unlike the US-002 diagram, which describes code as built. The participants that already exist (`delete_picture`, `get_pictures`, `get_random_picture`, `load_data`, `save_data`, `data_lock`) keep their names. The new routes and page functions named here are proposals. Update this file if the implementation names them differently.

## The central design decision: how trashed state is stored

US-004 leaves the representation of "in the trash" to the design. **Decision: an optional boolean field `trashed` on the picture record in `data.json`.**

- A trashed record looks like `{"id": 1730..., "filename": "1730....jpg", "tags": ["nature", "tree"], "trashed": true}`.
- An active record has **no `trashed` key at all**. Restore deletes the key instead of setting it to `false`, so an active record always has the same three keys it has today.
- A record without the key is active. The 7 existing records therefore load as active with no migration, no rewrite on read, and no new required field (data model I7, I8; US-004 "design decision" assumption).
- The image file stays where it is in `uploads/` while the picture is in the trash. Only a permanent delete removes it.
- The record stays at the same position in the `data.json` array while trashed, so a restored picture returns to its **original position** in the gallery. That settles the story's open question about display position.

| Alternative considered | Why it was rejected |
|------------------------|---------------------|
| A separate `trash.json` file | US-004 requires `data.json` plus `uploads/` to stay the only persistence. Two files can also drift out of sync, so a crash between writing them could leave a picture both active and trashed, or neither (US-004 last edge case). |
| Change `data.json` to `{"active": [...], "trash": [...]}` | Changes the file's root shape, so the 7 existing records would need a migration. Every existing route that reads the array would also change. |
| Move trashed image files into `uploads/trash/` | That is a second storage location. Moving a file plus rewriting `data.json` is two steps that can fail separately, and invariant I4 ("no record without a file") would have to hold across both folders. |

## Design rules these diagrams follow

- **R1 - Active means "no `trashed` flag".** One helper, `is_active(picture)`, returns `not picture.get('trashed', False)`. Every active view uses it: the gallery (`get_pictures`), the random viewer, and the slideshow (both use `get_random_picture`). They **drop trashed records first, then apply the tag filter**, so a trashed picture can never match a filter or be picked as a fallback (AC 2, 3, 11, 19).
- **R2 - Same lock, same atomic save as US-001 and US-002.** Every state change runs load → change in memory → `save_data()` (temp file, `fsync`, `os.replace`) inside `data_lock`, with one write per action (data model I5).
- **R3 - The server checks the state, not the page.** A request is rejected if the picture's state on disk isn't the one the action needs: soft delete needs an active record, and restore and permanent delete need a trashed one. A stale browser tab therefore gets a message instead of causing damage (AC 12, 13, 16).
- **R4 - Permanent delete saves the record removal before deleting the file**, exactly like today's `delete_picture`. A crash in between leaves an orphaned file, which I4 tolerates, never a record without its image, which I4 forbids.
- **R5 - Every rejection returns a message, and the page refreshes the view it came from** (US-004 assumption: "a stale view never fails silently"). `404` means the picture no longer exists. `409` means it exists but is in the wrong state for the action.

## Diagram 1: Move a picture to the trash (soft delete)

The existing **Delete** buttons in the gallery, random viewer and slideshow keep calling `DELETE /api/pictures/<id>`. Only the server's behavior changes: instead of removing the record and file, it sets the flag. This matches the story's confirmed scope that the soft delete replaces permanent deletion as the default meaning of the existing delete control.

```
  [ Owner ]          [ :Page ]           [ :AppRoutes ]        [ :DataStore ]        [ :Uploads ]
      |                   |                     |                     |                     |
      | 1. click "Delete" (gallery, random viewer or slideshow)       |                     |
      |------------------>|                     |                     |                     |
      |                   |---+  2. confirm("Move this picture to the trash?")              |
      |                   |<--+                 |                     |                     |
+--alt [Owner cancels] --------------------------------------------------------------------------------+
      |                   |---+  3a. nothing is sent; the picture stays where it is         |
      |                   |<--+                 |                     |                     |
+--else [Owner confirms] ------------------------------------------------------------------------------+
      |                   | 3. DELETE /api/pictures/<id>              |                     |
      |                   |-------------------->|                     |                     |
      |                   |                     |---+  4. acquire data_lock                 |
      |                   |                     |<--+                 |                     |
      |                   |                     | 5. load_data()      |                     |
      |                   |                     |-------------------->|                     |
      |                   |                     | 6. records          |                     |
      |                   |                     |<- - - - - - - - - - |                     |
+--alt [no record has this id] ------------------------------------------------------------------------+
      |                   | 7a. 404 {error: "...no longer exists."}   |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [record already has trashed: true] ------------------------------------------------------------+
      |                   | 7b. 409 {error: "...already in the trash."}                     |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [record is active] ----------------------------------------------------------------------------+
      |                   |                     |---+  7. picture['trashed'] = True   (same position; tags, filename untouched)
      |                   |                     |<--+                 |                     |
      |                   |                     | 8. save_data(records)                     |
      |                   |                     |-------------------->|                     |
      |                   |                     | 9. saved (tmp, fsync, os.replace)         |
      |                   |                     |<- - - - - - - - - - |                     |
      |                   |                     |---+  10. release data_lock                |
      |                   |                     |<--+                 |                     |
      |                   | 11. 200 {success, picture}                |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+------------------------------------------------------------------------------------------------------+
      |                   |---+  12. drop the picture from the view; random viewer / slideshow move on
      |                   |<--+                 |                     |                     |
      | 13. updated view + message              |                     |                     |
      |<- - - - - - - - - |                     |                     |                     |
+------------------------------------------------------------------------------------------------------+
```

## Diagram 2: Open the trash and restore a picture

```
  [ Owner ]          [ :Page ]           [ :AppRoutes ]        [ :DataStore ]        [ :Uploads ]
      |                   |                     |                     |                     |
      | 1. click "Trash"  |                     |                     |                     |
      |------------------>|                     |                     |                     |
      |                   | 2. GET /api/trash   |                     |                     |
      |                   |-------------------->|                     |                     |
      |                   |                     |---+  3. acquire data_lock                 |
      |                   |                     |<--+                 |                     |
      |                   |                     | 4. load_data()      |                     |
      |                   |                     |-------------------->|                     |
      |                   |                     | 5. records          |                     |
      |                   |                     |<- - - - - - - - - - |                     |
      |                   |                     |---+  6. release data_lock; keep records where trashed is true
      |                   |                     |<--+                 |                     |
+--loop [each trashed record] -------------------------------------------------------------------------+
      |                   |                     | 7. os.path.isfile(uploads/<filename>)     |
      |                   |                     |------------------------------------------>|
      |                   |                     | 8. True / False     |                     |
      |                   |                     |<- - - - - - - - - - - - - - - - - - - - - |
+------------------------------------------------------------------------------------------------------+
      |                   | 9. 200 [{id, filename, tags, image_available}]                  |
      |                   |<- - - - - - - - - - |                     |                     |
      | 10. trash list: image or "Image unavailable", tags, Restore, Delete Permanently     |
      |<- - - - - - - - - |                     |                     |                     |
      |                   |                     |                     |                     |
      | 11. click "Restore"                     |                     |                     |
      |------------------>|                     |                     |                     |
      |                   | 12. POST /api/trash/<id>/restore          |                     |
      |                   |-------------------->|                     |                     |
      |                   |                     |---+  13. acquire data_lock                |
      |                   |                     |<--+                 |                     |
      |                   |                     | 14. load_data()     |                     |
      |                   |                     |-------------------->|                     |
      |                   |                     | 15. records         |                     |
      |                   |                     |<- - - - - - - - - - |                     |
+--alt [no record has this id] ------------------------------------------------------------------------+
      |                   | 16a. 404 {error: "...no longer exists."}  |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [record is active] ----------------------------------------------------------------------------+
      |                   | 16b. 409 {error: "...not in the trash."}  |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [record is trashed] ---------------------------------------------------------------------------+
      |                   |                     | 16. os.path.isfile(uploads/<filename>)    |
      |                   |                     |------------------------------------------>|
      |                   |                     | 17. True / False    |                     |
      |                   |                     |<- - - - - - - - - - - - - - - - - - - - - |
+--alt [image file missing] ---------------------------------------------------------------------------+
      |                   | 18a. 409 {error: "...image is unavailable..."}                  |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [image file present] --------------------------------------------------------------------------+
      |                   |                     |---+  18. del picture['trashed']   (back to {id, filename, tags})
      |                   |                     |<--+                 |                     |
      |                   |                     | 19. save_data(records)                    |
      |                   |                     |-------------------->|                     |
      |                   |                     | 20. saved (tmp, fsync, os.replace)        |
      |                   |                     |<- - - - - - - - - - |                     |
      |                   |                     |---+  21. release data_lock                |
      |                   |                     |<--+                 |                     |
      |                   | 22. 200 {success, picture}                |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+------------------------------------------------------------------------------------------------------+
+------------------------------------------------------------------------------------------------------+
      |                   |---+  23. 200: remove from trash list / error: show message, reload trash list
      |                   |<--+                 |                     |                     |
      | 24. updated trash view + message        |                     |                     |
      |<- - - - - - - - - |                     |                     |                     |
```

## Diagram 3: Permanently delete a picture from the trash

```
  [ Owner ]          [ :Page ]           [ :AppRoutes ]        [ :DataStore ]        [ :Uploads ]
      |                   |                     |                     |                     |
      | 1. click "Delete Permanently" on a trash entry                |                     |
      |------------------>|                     |                     |                     |
      |                   |---+  2. confirm("Permanently delete <filename>? This cannot be undone.")
      |                   |<--+                 |                     |                     |
+--alt [Owner cancels or dismisses] -------------------------------------------------------------------+
      |                   |---+  3a. nothing is sent; entry stays in the trash              |
      |                   |<--+                 |                     |                     |
+--else [Owner confirms] ------------------------------------------------------------------------------+
      |                   | 3. DELETE /api/trash/<id>                 |                     |
      |                   |-------------------->|                     |                     |
      |                   |                     |---+  4. acquire data_lock                 |
      |                   |                     |<--+                 |                     |
      |                   |                     | 5. load_data()      |                     |
      |                   |                     |-------------------->|                     |
      |                   |                     | 6. records          |                     |
      |                   |                     |<- - - - - - - - - - |                     |
+--alt [no record has this id] ------------------------------------------------------------------------+
      |                   | 7a. 404 {error: "...no longer exists."}   |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [record is active] ----------------------------------------------------------------------------+
      |                   | 7b. 409 {error: "...not in the trash."}   |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+--else [record is trashed] ---------------------------------------------------------------------------+
      |                   |                     |---+  7. records.remove(picture)           |
      |                   |                     |<--+                 |                     |
      |                   |                     | 8. save_data(records)                     |
      |                   |                     |-------------------->|                     |
      |                   |                     | 9. saved (tmp, fsync, os.replace)         |
      |                   |                     |<- - - - - - - - - - |                     |
      |                   |                     | 10. os.remove(uploads/<filename>) if it exists
      |                   |                     |------------------------------------------>|
      |                   |                     | 11. removed / already missing             |
      |                   |                     |<- - - - - - - - - - - - - - - - - - - - - |
      |                   |                     |---+  12. release data_lock                |
      |                   |                     |<--+                 |                     |
      |                   | 13. 200 {success}   |                     |                     |
      |                   |<- - - - - - - - - - |                     |                     |
+------------------------------------------------------------------------------------------------------+
      |                   |---+  14. 200: remove entry / error: show message, reload trash list
      |                   |<--+                 |                     |                     |
      | 15. updated trash view + message        |                     |                     |
      |<- - - - - - - - - |                     |                     |                     |
+------------------------------------------------------------------------------------------------------+
```

## Notation

- header row: participants. `Owner` is the human using the browser; `:Type` participants are parts of the running app
- vertical line: lifeline (time flows downward)
- `------>` solid arrow: synchronous call or request
- `<- - -` dashed arrow: return or response
- `|---+` / `|<--+`: self-call (the participant runs one of its own functions); long labels run past the lifelines to their right
- `+--alt [...]` / `+--else [...]`: alternative fragment; exactly one branch runs
- `+--loop [...]`: repeated fragment
- a full-width `+-----+` line closes the innermost open fragment
- messages are numbered in time order within each diagram; a letter suffix (`7a`, `16b` ...) marks a step in an alternative branch
- in every error branch, leaving the `with data_lock:` block releases the lock and nothing is saved; that release is not drawn separately

## Scenario

- **Use case:** US-004, move to trash, restore, permanently delete (no `UC-###` assigned yet)
- **Preconditions:** the app is running; `data.json` is readable; the archive holds at least one picture.
- **Outcome (move to trash):** the record gains `"trashed": true` and nothing else about it changes; its file stays in `uploads/`; it disappears from every active view; no other record changes.
- **Outcome (restore):** the `trashed` key is removed, so the record is exactly as it was before the delete, at the same array position; it reappears in the gallery, the filters, the random viewer and the slideshow.
- **Outcome (permanent delete):** the record is gone from `data.json` and its file is gone from `uploads/`; nothing in the app can bring it back.
- **Outcome (any rejected or cancelled action):** `data.json` and `uploads/` are unchanged, and the Owner sees a message.

## Participants

| Participant | Responsibility in these scenarios | Where in the code |
|-------------|-----------------------------------|-------------------|
| Owner | Deletes, opens the trash, restores, permanently deletes, confirms or cancels. Single user, unauthenticated. | — |
| :Page | The JavaScript in `templates/index.html`: the gallery, random viewer, slideshow and a new trash view. Shows confirmations and messages, sends requests, and refreshes the view after a response. | existing: `deleteGalleryPicture`, `deleteRandomPicture`, `deleteTimerPicture`, `loadGallery`; new (proposed): `loadTrash`, `restorePicture`, `deletePermanently` |
| :AppRoutes | The Flask routes. Owns `data_lock`, checks the picture's state, and changes the record. | existing: `delete_picture` (changed to a soft delete), `get_pictures`, `get_random_picture`, `update_picture_tags`; new (proposed): `get_trash`, `restore_picture`, `delete_permanently`, helper `is_active` |
| :DataStore | Reads and writes the whole archive. | `app.py`: `load_data`, `save_data` |
| :Uploads | The `uploads/` folder on disk. Checked with `os.path.isfile` and changed only by a permanent delete. | `UPLOAD_FOLDER` |

## Messages

### Diagram 1: move to trash

| # | From → To | Message | Kind |
|---|-----------|---------|------|
| 1 | Owner → :Page | click **Delete** on the picture shown in the gallery, random viewer or slideshow | call |
| 2 | :Page → itself | `confirm("Move this picture to the trash? You can restore it later.")` | self-call |
| 3a | :Page → itself | cancelled: no request is sent and the view is unchanged | self-call |
| 3 | :Page → :AppRoutes | `DELETE /api/pictures/<id>` (same URL as today) | call |
| 4 | :AppRoutes → itself | `with data_lock:` | self-call |
| 5–6 | :AppRoutes ↔ :DataStore | `load_data()` → all records | call / return |
| 7a | :AppRoutes → :Page | `404 {"error": "This picture no longer exists."}` | return |
| 7b | :AppRoutes → :Page | `409 {"error": "This picture is already in the trash."}`; nothing is written, so there is still exactly one copy (AC 12) | return |
| 7 | :AppRoutes → itself | `picture['trashed'] = True`; `id`, `filename`, `tags` and array position are untouched | self-call |
| 8–9 | :AppRoutes ↔ :DataStore | `save_data(records)`: one atomic write | call / return |
| 10 | :AppRoutes → itself | leaving the `with` block releases `data_lock` | self-call |
| 11 | :AppRoutes → :Page | `200 {"success": true, "picture": {...}}` | return |
| 12 | :Page → itself | gallery: `loadGallery()` with the current filter; random viewer and slideshow: stop showing the picture now and request the next one, which the server can no longer return (AC 20); on 404/409: refresh the view the same way | self-call |
| 13 | :Page → Owner | refreshed view plus "Moved to trash." or the error message | return |

### Diagram 2: trash view and restore

| # | From → To | Message | Kind |
|---|-----------|---------|------|
| 1 | Owner → :Page | click **Trash** | call |
| 2 | :Page → :AppRoutes | `GET /api/trash` (new) | call |
| 3–5 | :AppRoutes ↔ :DataStore | lock, `load_data()`, all records | call / return |
| 6 | :AppRoutes → itself | release the lock; keep only records with `trashed: true`, so no active picture is listed (AC 11) | self-call |
| 7–8 | :AppRoutes ↔ :Uploads | for each trashed record, `os.path.isfile(...)`; a missing file is reported, never raised as an error (AC 14) | call / return |
| 9 | :AppRoutes → :Page | `200 [{id, filename, tags, image_available}]` | return |
| 10 | :Page → Owner | one entry per trashed picture: the image via `/uploads/<filename>` at gallery size, or "Image unavailable"; its tags unchanged; **Restore** and **Delete Permanently** buttons (AC 4, 14) | return |
| 11 | Owner → :Page | click **Restore** | call |
| 12 | :Page → :AppRoutes | `POST /api/trash/<id>/restore` (new) | call |
| 13–15 | :AppRoutes ↔ :DataStore | lock, `load_data()`, all records | call / return |
| 16a | :AppRoutes → :Page | `404 {"error": "This picture no longer exists."}` (permanently deleted in another tab, AC 16) | return |
| 16b | :AppRoutes → :Page | `409 {"error": "This picture is not in the trash."}` (AC 13) | return |
| 16–17 | :AppRoutes ↔ :Uploads | `os.path.isfile(uploads/<filename>)` | call / return |
| 18a | :AppRoutes → :Page | `409 {"error": "The image for this picture is unavailable, so it cannot be restored."}`; the picture stays in the trash (AC 14) | return |
| 18 | :AppRoutes → itself | `del picture['trashed']`: the record is back to exactly `{id, filename, tags}` | self-call |
| 19–20 | :AppRoutes ↔ :DataStore | `save_data(records)` | call / return |
| 21 | :AppRoutes → itself | release `data_lock` | self-call |
| 22 | :AppRoutes → :Page | `200 {"success": true, "picture": {...}}` | return |
| 23 | :Page → itself | 200: remove the entry from the trash list; error: show the message and call `loadTrash()` again so the list matches the server (AC 16) | self-call |
| 24 | :Page → Owner | updated trash view plus "Restored." or the error message | return |

### Diagram 3: permanent delete

| # | From → To | Message | Kind |
|---|-----------|---------|------|
| 1 | Owner → :Page | click **Delete Permanently** on a trash entry | call |
| 2 | :Page → itself | `confirm("Permanently delete <filename>? It will be removed permanently and this cannot be undone.")`: names the picture and says it can't be undone (AC 9) | self-call |
| 3a | :Page → itself | cancelled or dismissed: no request is sent; the entry, its tags and its file are unchanged and it is still restorable (AC 10) | self-call |
| 3 | :Page → :AppRoutes | `DELETE /api/trash/<id>` (new) | call |
| 4–6 | :AppRoutes ↔ :DataStore | lock, `load_data()`, all records | call / return |
| 7a | :AppRoutes → :Page | `404 {"error": "This picture no longer exists."}` (AC 16) | return |
| 7b | :AppRoutes → :Page | `409 {"error": "This picture is not in the trash."}`; an active picture can only be permanently deleted after it is moved to the trash | return |
| 7 | :AppRoutes → itself | remove the record from the in-memory list | self-call |
| 8–9 | :AppRoutes ↔ :DataStore | `save_data(records)` **before** touching the file (R4) | call / return |
| 10–11 | :AppRoutes ↔ :Uploads | `os.remove(...)` only if the file exists; an already-missing file is not an error (AC 15) | call / return |
| 12 | :AppRoutes → itself | release `data_lock` | self-call |
| 13 | :AppRoutes → :Page | `200 {"success": true}` | return |
| 14 | :Page → itself | 200: remove the entry; error: show the message and reload the trash list | self-call |
| 15 | :Page → Owner | updated trash view plus "Permanently deleted." or the error message | return |

## Design decisions shown by these diagrams

1. **A flag, not a move** (Diagram 1 step 7, Diagram 2 step 18). A soft delete and a restore each change one key in one record and write once. No file moves, so there is no two-step operation that could fail halfway (last edge case in US-004).
2. **The existing Delete URL changes meaning, not shape** (Diagram 1 step 3). `DELETE /api/pictures/<id>` now soft-deletes. The three existing delete buttons need only new confirmation text, and permanent deletion gets its own URL under `/api/trash/`, so it can't be triggered from an active view by accident.
3. **Filter out trashed records before anything else** (R1). `get_random_picture` has a fallback that can return an excluded picture when nothing else is left. Because trashed records are dropped before that fallback runs, the fallback can never return a trashed picture (AC 3).
4. **State checks happen inside the lock** (steps 7a/7b, 16a/16b). The check and the write happen in the same critical section, so a double-click or a stale tab can't trash, restore or delete a picture twice (AC 12, 13, 16).
5. **Restoring a picture with no image is refused** (Diagram 2 step 18a). Returning it to the gallery would create the "record without a file" state that I4 forbids. Permanent delete still works for it (AC 14, 15).
6. **Permanent delete removes the record before the file** (R4). This is the same safe order as today's `delete_picture`.

## Changes to existing behavior this design requires

| Code | Change | Why |
|------|--------|-----|
| `get_pictures` | keep only `is_active` records, then apply the tag filter | AC 2, 11, 19 |
| `get_random_picture` | keep only `is_active` records before the tag filter and the `exclude_ids` fallback | AC 2, 3, 11, 19, 20 |
| `delete_picture` | set `trashed` instead of removing the record and file; `409` if already trashed | AC 1, 12 |
| `update_picture_tags` | `409 {"error": "This picture is in the trash."}` for a trashed picture | a stale gallery tab must not change a trashed picture's tags, which must come back unchanged on restore (AC 4, 6) |
| upload and ZIP import | no change; new records are written without a `trashed` key, so they are active | R1 |
| `serve_upload` | no change; trashed images are still served so the trash view can show them, and a permanently deleted file returns 404 because it no longer exists (AC 8, 17) | AC 4, 8 |
| `tests/test_zip_import.py::test_delete_removes_record_and_file` | must be rewritten: `DELETE /api/pictures/<id>` now keeps the record and file | the old behavior is now the permanent delete in Diagram 3 |

## Error paths not drawn

| Situation | Behavior |
|-----------|----------|
| `data.json` is corrupt when loaded | `load_data()` raises `StoreError`; the lock is released; nothing is saved; `500 {"error": "data.json could not be read; nothing was changed"}`; the page shows the error. |
| `save_data` fails (e.g. disk full) | `os.replace` never ran, so `data.json` is still the complete old array; `500` with "could not be saved; nothing was changed". For a permanent delete, the file is not removed either, because step 10 comes after the save. |
| `os.remove` fails after the save in a permanent delete (e.g. file locked) | the record is already gone, so the picture is permanently deleted from the app's point of view; the orphaned file is invisible garbage, which I4 tolerates. The route still returns `200`. |
| The response isn't JSON (e.g. the server is down) | the page shows a generic "The action could not be completed." and reloads the view it is on. |

## Traceability

| US-004 requirement | Where it holds |
|--------------------|----------------|
| AC 1 (5 active → 4 active + 1 trashed; others unchanged) | Diagram 1 steps 2–11; step 7 changes only one record |
| AC 2 (trashed picture absent from gallery, filter, random, slideshow) | R1, decision 3 |
| AC 3 (only "sky" picture trashed → "no pictures match") | R1; `get_random_picture` returns its existing 404 "No pictures match criteria" |
| AC 4 (trash entry shows image and tags unchanged) | Diagram 2 steps 9–10; Diagram 1 step 7 leaves tags untouched |
| AC 5 (trash survives restart) | Diagram 1 steps 8–9 write `trashed` to `data.json` |
| AC 6 (restore: back once, tags unchanged, matches filters) | Diagram 2 step 18 removes only the flag; R1 includes it again |
| AC 7 (restore survives restart) | Diagram 2 steps 19–20 |
| AC 8 (permanent delete: record and file gone, unrecoverable) | Diagram 3 steps 7–11 |
| AC 9 (confirmation names the picture, says permanent, nothing changes before confirm) | Diagram 3 step 2; no request before step 3 |
| AC 10 (cancel leaves everything unchanged) | Diagram 3 branch 3a |
| AC 11 (trash lists only trashed; active views only active) | Diagram 2 step 6; R1 |
| AC 12 (delete of an already-trashed picture rejected) | Diagram 1 branch 7b, decision 4 |
| AC 13 (restore of an active picture rejected) | Diagram 2 branch 16b |
| AC 14 (missing image: trash still opens, entry marked, restore refused) | Diagram 2 steps 7–10 and branch 18a, decision 5 |
| AC 15 (missing image: permanent delete still succeeds) | Diagram 3 steps 10–11 |
| AC 16 (stale trash view: rejected with message, view refreshes) | Diagram 2 branch 16a and step 23; Diagram 3 branch 7a and step 14 |
| AC 17 (restart with 3 active, 2 trashed, 1 permanently deleted) | R2: every state is in `data.json`; AC 5, 7 and 8 rows |
| AC 18 (other pictures' tags and images unchanged) | each action changes or removes exactly one record and at most one file |
| AC 19 (tag only on a permanently deleted picture matches nothing; shared tag still works) | Diagram 3 step 7 removes the record; tags exist only inside records (data model I3) |
| AC 20 (picture on display in random viewer or slideshow disappears at once) | Diagram 1 step 12 |

## Open questions for the team

- **Data model doc.** `docs/design/art-reference-archive-data-model.md` should get the optional `trashed` field and a note that a record without it is active. Who updates it, and should that be part of the US-004 PR?
- **US-003 interaction.** If global tag rename or delete is built, should it change pictures in the trash? This design leaves trashed pictures out of `[TagUsageSummary]` counts, as the story assumes, but the requirements owner hasn't confirmed it yet.
- **Status codes.** This design uses `409 Conflict` for "wrong state" and `404` for "doesn't exist". Confirm the team is happy with that split before the tests are written against it.

---
*Drafted with AI assistance (Claude Code) from US-004 and the existing `app.py`; reviewed and edited by the author.*

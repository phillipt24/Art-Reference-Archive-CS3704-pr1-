# Sequence Diagram: Edit the Tags of One Picture (US-002)

Scope: one tag edit on one picture in the gallery, from clicking **Edit Tags** to the picture showing its new tags. Unlike the US-001 diagram, this one describes the code **as built**: every participant and message below exists in `app.py` or `templates/index.html` on the `feature/tag-editing` branch. Requirements come from `docs/requirements/US-002-tag-editing-and-deletion.md` (AC 1–12 plus the edge cases listed under its assumptions).

## Design rules this diagram follows

- **R1 - Nothing is stored until Save.** The editor works on a local copy (`editorTags`). Removing, adding, cancelling and navigating away never send a request, so an abandoned edit cannot change `data.json` (AC 12).
- **R2 - Save sends the whole tag list.** The request carries the picture's complete new tag list, not a list of add/remove changes. The server replaces the picture's `tags` with it in one step.
- **R3 - One normalization rule, applied on both sides.** Trim, lowercase, split on commas, drop empty values, and drop duplicates while keeping the first one's position. The page uses `normalizeTags()` so it can show messages right away. The server uses `normalize_tags()`, the same helper single upload and the search filters use, so the server never trusts the page.
- **R4 - One lock, one atomic save.** As in US-001: load → change in memory → `save_data()` (temp file, `fsync`, `os.replace`), all inside `data_lock`. The file on disk is always either the complete old array or the complete new one.

## Diagram

```
  [ Owner ]           [ :GalleryPage ]           [ :AppRoutes ]            [ :DataStore ]
      |                       |                         |                         |
      | 1. click "Edit Tags"  |                         |                         |
      |---------------------->|                         |                         |
      |                       |---+  2. openTagEditor(): editorTags = normalizeTags(tags)
      |                       |<--+                     |                         |
      | 3. editor: current tags, x buttons, Add box     |                         |
      |< - - - - - - - - - - -|                         |                         |
      |                       |                         |                         |
+--loop [Owner edits the local copy; no request is sent] --------------------------------------+
+--alt [click x on a tag] ---------------------------------------------------------------------+
      |                       |---+  4. editorTags.remove(tag); renderEditorTags()|
      |                       |<--+                     |                         |
+--else [type text, click "Add" or press Enter] -----------------------------------------------+
      |                       |---+  5. addEditorTags(): normalizeTags(input)     |
      |                       |<--+                     |                         |
+--alt [nothing left after normalizing] -------------------------------------------------------+
      | 6a. "A tag cannot be empty."                    |                         |
      |< - - - - - - - - - - -|                         |                         |
+--else [some new tags were already in editorTags] --------------------------------------------+
      | 6b. "Already present: <tags>" (no duplicate)    |                         |
      |< - - - - - - - - - - -|                         |                         |
+----------------------------------------------------------------------------------------------+
+----------------------------------------------------------------------------------------------+
+----------------------------------------------------------------------------------------------+
      |                       |                         |                         |
+--alt [click "Cancel", Previous/Next, or reload the gallery] ---------------------------------+
      |                       |---+  7a. closeTagEditor(): editorTags discarded   |
      |                       |<--+                     |                         |
+--else [click "Save"] ------------------------------------------------------------------------+
      | 7. click "Save"       |                         |                         |
      |---------------------->|                         |                         |
      |                       |---+  8. saveTagEdit(); leftover input -> addEditorTags()
      |                       |<--+                     |                         |
      |                       | 9. PUT /api/pictures/<id>/tags {tags}             |
      |                       |------------------------>|                         |
      |                       |                         |---+  10. update_picture_tags(): validate body
      |                       |                         |<--+                     |
+--alt [not a list of strings, or a value normalizes to empty] --------------------------------+
      |                       | 11a. 400 {error}        |                         |
      |                       |< - - - - - - - - - - - -|                         |
      | 12a. show error; editor stays open              |                         |
      |< - - - - - - - - - - -|                         |                         |
+--else [valid] -------------------------------------------------------------------------------+
      |                       |                         |---+  11. tags = normalize_tags(raw_tags)
      |                       |                         |<--+                     |
      |                       |                         |---+  12. acquire data_lock
      |                       |                         |<--+                     |
      |                       |                         | 13. load_data()         |
      |                       |                         |------------------------>|
      |                       |                         | 14. records             |
      |                       |                         |< - - - - - - - - - - - -|
+--alt [no record has this id] ----------------------------------------------------------------+
      |                       |                         |---+  15a. release data_lock
      |                       |                         |<--+                     |
      |                       | 16a. 404 {error}        |                         |
      |                       |< - - - - - - - - - - - -|                         |
      |                       |---+  17a. closeTagEditor()                        |
      |                       |<--+                     |                         |
      |                       | 18a. GET /api/pictures?tags=<filter>              |
      |                       |------------------------>|                         |
      |                       | 19a. pictures (deleted one absent)                |
      |                       |< - - - - - - - - - - - -|                         |
      | 20a. gallery refreshed + message                |                         |
      |< - - - - - - - - - - -|                         |                         |
+--else [record found] ------------------------------------------------------------------------+
      |                       |                         |---+  15. picture['tags'] = tags
      |                       |                         |<--+                     |
      |                       |                         | 16. save_data(records)  |
      |                       |                         |------------------------>|
      |                       |                         | 17. saved (tmp, fsync, os.replace)
      |                       |                         |< - - - - - - - - - - - -|
      |                       |                         |---+  18. release data_lock
      |                       |                         |<--+                     |
      |                       | 19. 200 {success, picture}                        |
      |                       |< - - - - - - - - - - - -|                         |
      |                       |---+  20. galleryImages[i] = picture; close        |
      |                       |<--+                     |                         |
      | 21. "Tags: nature, tree, forest" / "None"       |                         |
      |< - - - - - - - - - - -|                         |                         |
+----------------------------------------------------------------------------------------------+
+----------------------------------------------------------------------------------------------+
+----------------------------------------------------------------------------------------------+
```

## Notation

- header row: participants. `Owner` is the human using the browser; `:Type` participants are parts of the running app
- vertical line: lifeline (time flows downward)
- `------>` solid arrow: synchronous call or request
- `< - - -` dashed arrow: return or response
- `|---+` / `|<--+`: self-call (the participant runs one of its own functions); long labels run past the lifelines to their right
- `+--alt [...]` / `+--else [...]`: alternative fragment; exactly one branch runs
- `+--loop [...]`: repeated fragment
- a full-width `+-----+` line closes the innermost open fragment
- messages are numbered in time order; a letter suffix (`6a`, `7a`, `11a` ...) marks a step in an alternative branch

## Scenario

- **Use case:** US-002, add and remove tags on one picture (no `UC-###` assigned yet)
- **Preconditions:** the app is running; `data.json` is readable; the gallery is showing at least one picture.
- **Outcome (Save succeeds):** that picture's record in `data.json` holds exactly the normalized, duplicate-free tag list shown in the editor; no other record changes; the gallery shows the new tags at once, or "None" if the list is empty.
- **Outcome (Cancel or navigate away):** no request is sent and `data.json` is unchanged.
- **Outcome (rejected Save):** `data.json` is unchanged and a message explains why: a tag cannot be empty, or the picture no longer exists.

## Participants

| Participant | Responsibility in this scenario | Where in the code |
|-------------|---------------------------------|-------------------|
| Owner | Opens the editor, removes and adds tags, then saves or cancels. Single user, unauthenticated. | — |
| :GalleryPage | The gallery's JavaScript. Holds `galleryImages`, `galleryIndex` and the editor's local copy `editorTags`; shows messages; sends the request on Save. | `templates/index.html`: `openTagEditor`, `addEditorTags`, `renderEditorTags`, `saveTagEdit`, `closeTagEditor`, `loadGallery` |
| :AppRoutes | The Flask routes. `update_picture_tags` handles `PUT /api/pictures/<id>/tags`; `get_pictures` handles the gallery refresh. Owns `data_lock`. | `app.py`: `update_picture_tags`, `normalize_tags`, `get_pictures` |
| :DataStore | Reading and writing the archive: `load_data()` and `save_data()` over `data.json`. | `app.py`: `load_data`, `save_data` |

## Messages

| # | From → To | Message | Kind |
|---|-----------|---------|------|
| 1 | Owner → :GalleryPage | click **Edit Tags** on the picture shown | call |
| 2 | :GalleryPage → itself | `openTagEditor()`: `editorTags = normalizeTags(current.tags)`; a stored duplicate (e.g. `sky, sky`) shows once | self-call |
| 3 | :GalleryPage → Owner | editor with each current tag, an × button per tag, an Add box, **Save** and **Cancel** | return |
| 4 | :GalleryPage → itself | × clicked: remove that tag from `editorTags`; `renderEditorTags()` | self-call |
| 5 | :GalleryPage → itself | `addEditorTags()`: `normalizeTags(input)`; append tags not already in `editorTags` | self-call |
| 6a | :GalleryPage → Owner | "A tag cannot be empty." (input was empty, only spaces, or only commas); `editorTags` unchanged | return |
| 6b | :GalleryPage → Owner | "Already present: forest"; the tag still appears once | return |
| 7a | :GalleryPage → itself | `closeTagEditor()` (Cancel, Previous/Next, or `loadGallery()`): `editorTags` is discarded and **no request is sent** | self-call |
| 7 | Owner → :GalleryPage | click **Save** | call |
| 8 | :GalleryPage → itself | `saveTagEdit()`: text still in the Add box goes through `addEditorTags()` first; if that shows 6a, the save stops here | self-call |
| 9 | :GalleryPage → :AppRoutes | `PUT /api/pictures/<id>/tags` with JSON `{"tags": editorTags}` | call |
| 10 | :AppRoutes → itself | `update_picture_tags(id)`: the body must be a list of strings, and every value must normalize to at least one tag | self-call |
| 11a | :AppRoutes → :GalleryPage | `400 {"error": "A tag cannot be empty."}` (or "Tags must be a list of strings.") | return |
| 12a | :GalleryPage → Owner | the error is shown; the editor stays open with the Owner's edits | return |
| 11 | :AppRoutes → itself | `tags = normalize_tags(raw_tags)` | self-call |
| 12 | :AppRoutes → itself | `with data_lock:` acquires the lock | self-call |
| 13 | :AppRoutes → :DataStore | `load_data()` | call |
| 14 | :DataStore → :AppRoutes | all records (raises `StoreError` if `data.json` is corrupt; see Error paths) | return |
| 15a | :AppRoutes → itself | no record has this id: leaving the `with` block releases the lock; nothing was changed | self-call |
| 16a | :AppRoutes → :GalleryPage | `404 {"error": "This picture no longer exists."}` | return |
| 17a | :GalleryPage → itself | `closeTagEditor()` | self-call |
| 18a | :GalleryPage → :AppRoutes | `loadGallery()`: `GET /api/pictures?tags=<current filter>` | call |
| 19a | :AppRoutes → :GalleryPage | the matching pictures, without the deleted one | return |
| 20a | :GalleryPage → Owner | refreshed gallery plus "This picture no longer exists." | return |
| 15 | :AppRoutes → itself | `picture['tags'] = tags`, changing only this record | self-call |
| 16 | :AppRoutes → :DataStore | `save_data(records)`: one write for the whole edit | call |
| 17 | :DataStore → :AppRoutes | saved: temp file `data.json.tmp`, `fsync`, `os.replace` onto `data.json` | return |
| 18 | :AppRoutes → itself | leaving the `with` block releases `data_lock` | self-call |
| 19 | :AppRoutes → :GalleryPage | `200 {"success": true, "picture": {id, filename, tags}}` | return |
| 20 | :GalleryPage → itself | `galleryImages[galleryIndex] = picture`; `closeTagEditor()`; `updateGalleryDisplay()` | self-call |
| 21 | :GalleryPage → Owner | "Tags: nature, tree, forest", or "Tags: None" when the list is empty | return |

## Design decisions shown by this diagram

1. **All editing is local until Save** (the `loop` fragment and branch `7a`). Steps 1–8 never reach `:AppRoutes`, so a cancelled or abandoned edit needs no undo. There was never a server change to undo (R1, AC 12).
2. **The whole list is sent, not add/remove changes** (step 9, R2). The server doesn't have to merge changes into what it has stored, and stored duplicates are cleaned up because the list is normalized again in step 11. The cost: if the same picture were edited in two browser tabs, the last Save would win. That is acceptable because the story says the app is single-user with "no loss-of-update concerns".
3. **Messages come from the page; the server enforces the rules anyway** (6a/6b vs. 10–11). Checking on the page gives instant feedback without a round trip. Repeating the check on the server (R3) means a hand-made request can never store an empty, padded or uppercase tag.
4. **Validation happens before the lock** (step 10 comes before 12). A bad request is rejected without ever holding `data_lock` or reading `data.json`.
5. **The id is checked inside the lock** (steps 13–15a). A picture deleted between opening the editor and clicking Save is noticed in the same critical section as the write. So a tag save can never bring a deleted record back or create a new one.
6. **Only the edited record changes** (step 15). Other pictures, even ones with duplicate tags stored, are written back exactly as they were loaded, as the story's scope requires.

## Error paths not drawn

| Situation | Behavior |
|-----------|----------|
| `data.json` is corrupt at step 13 | `load_data()` raises `StoreError`; leaving the `with` block releases the lock; nothing is saved; `500 {"error": "data.json could not be read; nothing was changed"}`. The page shows the error, and the editor stays open. |
| `save_data` fails at step 16 (e.g. disk full) | `os.replace` never ran, so `data.json` is still the complete old array; `500 {"error": "data.json could not be saved; nothing was changed"}`; the page shows the error, and the editor stays open. |
| The response isn't JSON (e.g. the server is down) | `saveTagEdit()` falls back to "The tags could not be saved." and keeps the editor open. |

## Traceability

| US-002 requirement | Where it holds in the diagram |
|--------------------|-------------------------------|
| AC 1 (editor shows current tags with add and remove controls) | steps 1–3 |
| AC 2 (new tag displayed immediately) | steps 9–21; step 20 updates the page from the server's response |
| AC 3 (survives restart) | steps 16–17: written to `data.json` before the response is sent |
| AC 4 ("  Forest  " stored as "forest") | steps 5 and 11 (`normalizeTags` / `normalize_tags`) |
| AC 5 (variant of an existing tag: still one, with a message) | step 6b; step 11 removes duplicates again on the server |
| AC 6 (empty tag: unchanged, with a message) | step 6a on the page; branch 11a–12a on the server |
| AC 7 ("sky, water" adds both) | steps 5 and 11 split on commas |
| AC 8 (removing from one picture doesn't touch the other; search reflects it) | step 4 (remove); step 15 changes only this record |
| AC 9 (last tag removed: zero tags, still shown, "None") | step 15 stores `[]`; step 21 shows "None" |
| AC 10, 11 (gallery, random viewer and slideshow filters see the change without restart) | not in this flow: `get_pictures` and `get_random_picture` call `load_data()` on every request, so they read what step 16 wrote |
| AC 12 (cancel or abandon: tags unchanged) | branch 7a; nothing is sent before step 9 |
| Edge case: duplicates already stored are cleaned when that picture is edited | step 2 shows them once; step 11 stores them once; step 15 leaves other records alone |
| Edge case: picture deleted before Save | branch 15a–20a |

## Open questions for the team

- **Two tabs, same picture.** Because the whole list is sent (decision 2), the second Save overwrites the first without warning. The story rules this out as a concern for a single user. Is that still true if the team uses the app from more than one tab?
- **The "already present" message exists only on the page.** If the server receives a duplicate, it quietly keeps one copy and doesn't say so. AC 5 is met through the UI. Should the API report it too?
- **Leftover text in the Add box counts as an add on Save** (step 8). US-002 doesn't say what should happen. Confirm this is the behavior the team wants.

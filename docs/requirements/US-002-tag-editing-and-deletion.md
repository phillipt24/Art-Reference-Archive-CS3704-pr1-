# User Stories: Art Reference Archive — Tag Editing and Deletion

## US-002 — Add and remove tags on one picture

**Story:** As the archive owner, I want to add and remove tags on a single existing picture, so that I can correct or extend the tags of a picture — including pictures imported from a ZIP — without deleting and re-uploading it.

**Acceptance Criteria**

1. Given a picture is shown in the gallery, when the user opens that picture's tag editor, then the editor shows the picture's current tags and provides controls to add tags and remove individual tags.
2. Given a picture displayed in the gallery that has the tags "nature" and "tree", when the user adds the tag "Forest" and confirms the edit, then the picture immediately displays the tags "nature", "tree", and "forest".
3. Given the tag "forest" was just added to a picture, when the application is restarted and the gallery is opened, then the picture still displays "forest" among its tags.
4. Given the user enters the tag "  Forest  " for a picture, when the edit is confirmed, then the picture's tag list contains "forest" and contains no tag with surrounding whitespace or uppercase letters.
5. Given a picture already has the tag "forest", when the user adds "Forest" or " forest " to that same picture, then the picture still shows exactly one "forest" tag and a message indicates the tag is already present.
6. Given the user enters an empty value or only whitespace as a tag, when the edit is confirmed, then the picture's tags are unchanged and a message indicates a tag cannot be empty.
7. Given the user enters "sky, water" as tags for one picture, when the edit is confirmed, then both "sky" and "water" are added to that picture.
8. Given two pictures both have the tag "sky", when the user removes "sky" from one of them and confirms, then that picture no longer shows "sky", the other picture still shows "sky", and searching by "sky" returns the other picture only.
9. Given a picture whose only tag is "sky", when the user removes "sky" and confirms, then the picture is saved with zero tags, remains present in the gallery, and displays "None" for its tags.
10. Given a picture was just edited to add the tag "forest", when the user filters the gallery, the random viewer, or the slideshow by "forest" without restarting the application, then that picture is eligible to be returned.
11. Given a picture's tag "forest" was just removed, when the user filters the gallery, the random viewer, or the slideshow by "forest" without restarting the application, then that picture is not returned.
12. Given the user cancels or abandons a tag edit before confirming it, when the user reloads the gallery, then the picture's tags are exactly as they were before the cancelled edit.

**Priority:** Must-have (MoSCoW)

**Related requirements:** No `REQ-###` or `UC-###` is assigned to this capability yet; this story is the origin of those IDs. Related stories: US-001 — ZIP-imported pictures arrive untagged, so this story is how they become searchable; US-003 — global rename/delete of the same tag data using the same normalization rules.

**Assumptions / dependencies:**

- Depends on `data.json` records continuing to hold tags per picture as a list of strings, and on the existing normalization rules (trim, lowercase, drop empty, no per-picture duplicates) being applied to edits as they are at upload time.
- Depends on the existing AND-semantics filtering; editing tags must not change which tag lists a filter can match.
- Confirmed scope: per-picture tag editing is available from the gallery and uses an explicit Save/Confirm action; the random viewer and slideshow do not need their own edit controls.
- Confirmed scope: changes are persisted when the user confirms the edit, not on each keystroke, so cancelling before confirmation leaves the stored tags untouched.
- Confirmed scope: a tag edit or a global rename cleans duplicate tags only on the pictures it actually changes; pictures it does not touch keep their existing records.
- The application is single-user and unauthenticated, so there are no permission checks and no loss-of-update concerns from concurrent editors.
- **Edge cases considered:** adding a case/whitespace variant of an existing tag (AC 5); empty or whitespace-only tag (AC 6); multiple comma-separated tags in one edit (AC 7); removing the last tag so the picture becomes untagged and displays "None" (AC 9); duplicate tags already present in a stored record are collapsed when that picture is next edited; a picture deleted in another view before the edit is confirmed is rejected with a message and the gallery refreshes; removing a tag that the current filter uses (AC 11).

---

## US-003 — Rename or delete a tag across all pictures

**Story:** As the archive owner, I want to rename a tag everywhere it is used or delete it everywhere it is used, so that I can fix a misspelled or unwanted tag across the whole archive in one action instead of editing pictures one by one.

**Acceptance Criteria**

1. Given 6 pictures are tagged "forrest" and no picture is tagged "forest", when the user renames "forrest" to "forest" and confirms, then all 6 pictures display "forest" instead of "forrest", the archive contains no picture tagged "forrest", and the total picture count is unchanged.
2. Given 3 pictures are tagged "tree" and 2 different pictures are tagged "wood", when the user renames "wood" to "tree" and confirms, then all 5 pictures display "tree", no picture shows "wood", and no picture displays "tree" twice.
3. Given a picture is tagged both "wood" and "tree", when the user renames "wood" to "tree" and confirms, then that picture displays "tree" exactly once after the rename.
4. Given the user enters "  Forest  " as the new name when renaming "forrest", when the rename is confirmed, then the resulting tag reads "forest" on every affected picture.
5. Given the user enters an empty value or only whitespace as the new tag name, when the rename is confirmed, then no picture changes and a message indicates a tag cannot be empty.
6. Given the user renames the tag "forest" to "forest" or to "Forest", when the rename is confirmed, then no picture changes, no error is reported, and a message indicates the tag name is unchanged.
7. Given a tag named "sky" is used on 4 pictures, when the user deletes the tag "sky" and confirms, then none of those 4 pictures shows "sky", each of the 4 pictures keeps any other tags it had, and the total picture count is unchanged.
8. Given a picture's only tag is "sky", when the user deletes the tag "sky" globally and confirms, then that picture remains in the gallery as an untagged picture displaying "None".
9. Given the user renames or deletes a tag that exists on no picture, when the action is confirmed, then no picture changes and a message indicates no pictures used that tag.
10. Given the user deletes the tag "sky" globally, when the user filters the gallery, the random viewer, or the slideshow by "sky" without restarting the application, then no picture is returned.
11. Given a global rename or delete is requested, when the confirmation step is shown, then it states how many pictures the action will affect before the change is applied.
12. Given the user is shown the confirmation step for a global rename or delete, when the user cancels it, then no picture changes.
13. Given a global rename is applied, when the application is restarted and the gallery is opened, then the new tag name is shown on every affected picture and the old name appears nowhere.
14. Given a global rename or delete is applied, when the user views any affected picture, then its image still displays correctly and no picture's file has been removed.
15. Given a global rename or delete fails partway through, when the operation ends, then no picture is changed (all-or-nothing) and an error message is shown.

**Priority:** Must-have (MoSCoW) — confirmed in scope together with per-picture editing for this sprint.

**Related requirements:** No `REQ-###` or `UC-###` is assigned to this capability yet. Related stories: US-002 — same tag data and normalization rules applied to one picture at a time; US-001 — imported pictures provide the untagged and mistagged content these operations act on.

**Assumptions / dependencies:**

- Depends on US-002's normalization rules (trim, lowercase, reject empty, no per-picture duplicates); criteria 2–6 are the many-picture version of US-002 criteria 4–7.
- Depends on `data.json` being the single source of truth for tags and on the gallery, random viewer, and slideshow all reading tags at request time, so criteria 10 and 13 hold without a restart.
- Confirmed scope: global operations are destructive only to tag assignments, never to pictures or image files, and are confirmed before they run.
- Confirmed scope: no undo is required; the operation applies all-or-nothing (AC 15).
- Confirmed scope: a rename merges into an existing tag and removes duplicates only on the pictures it changes; pictures not touched by the rename are not otherwise repaired.
- The application is single-user and unauthenticated, so a global action affects the only archive that exists.
- **Edge cases considered:** renaming onto an existing tag merges without duplicates (AC 2, 3); renaming to a case/whitespace variant of itself is a harmless no-op (AC 6); empty or whitespace-only name rejected (AC 5); tag used on zero pictures gives an explanatory no-op (AC 9); picture whose only tag is deleted becomes untagged and remains viewable (AC 8); a tag used on every picture updates all pictures with no file loss (AC 1, 7, 14); a filter currently using the renamed or deleted tag returns no matches without a restart (AC 10); cancellation leaves the archive untouched (AC 12); an interrupted operation leaves the archive untouched (AC 15).

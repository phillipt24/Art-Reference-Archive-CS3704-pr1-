# Black Box Test Plan — Art Reference Archive

| Item | Value |
|---|---|
| Course | CS3704 — Intermediate Software Design and Engineering |
| Project | Art Reference Archive |
| Milestone | PM2.2 — Development Sprint II |
| Document | Black Box Test Plan |
| Version | 1.0 |
| Date | November 5, 2026 |
| Prepared by | Grace Marrone, Connor Williams, Phillip Truong |
| System under test | Flask web application started with `python app.py`, served at `http://127.0.0.1:5000` |

## 1. Purpose

This document defines black box test cases for the Art Reference Archive. A black box test
treats the application as a single unit: the tester supplies input through the user interface
and observes only the output the application produces. The tester does not inspect or reason
about the source code while executing a case.

The cases verify the acceptance criteria in the project requirements:

- `docs/requirements/US-001-zip-bulk-upload.md` — importing many pictures from one ZIP archive.
- `docs/requirements/US-002-tag-editing-and-deletion.md` — adding and removing tags on one picture.

Cases also cover the existing single-image upload and browsing features described in
`README.md`, and the size, entry-count, and format constraints recorded in US-001.

## 2. Scope

### In scope

- Bulk ZIP import, including mixed valid and invalid entries, unsafe archive paths, and the
  reported import summary.
- ZIP size, entry-count, per-image size, and extracted-size limits.
- Supported image formats: JPG, JPEG, PNG, GIF, and WebP.
- Persistence of imported pictures across an application restart.
- Interaction between untagged imported pictures and tag filters.
- Single-image upload with tags.
- Tag editing: adding, normalizing, deduplicating, and removing tags.
- Gallery filtering, random picture viewer, timer slideshow, and picture deletion.

### Out of scope

- Performance, load, and stress testing.
- Security penetration testing beyond the archive-path escape case required by US-001.
- Multi-user behavior, authentication, and authorization; the application is single-user and
  unauthenticated.
- Browser compatibility beyond the current versions of Chrome and Firefox.
- Mobile layout and accessibility conformance.
- Unit and integration testing of internal functions; those are covered by
  `tests/test_zip_import.py` and are white box tests, not part of this plan.

## 3. Test approach

### 3.1 Required test case information

Each case in this plan records the four items required by the lecture test-case template:

1. **Unique identifier** — `BB-01` through `BB-32`.
2. **Input** — the test data and the actions the tester performs.
3. **Expected output** — the observable result that must occur for the case to pass.
4. **Actual results** — intentionally left blank for the PM2.2 submission and completed when
   the plan is executed.

Two supplementary columns, **Related acceptance criteria** and **Preconditions**, are included
so the plan is traceable to the requirements and reproducible by another tester. They do not
replace any of the four required items.

### 3.2 Test design techniques

The cases use two black box techniques from the lecture:

- **Equivalence partitioning** — one representative from each class of input: a valid archive,
  an archive with mixed valid and invalid entries, an empty archive, a corrupt archive, an
  archive with unsafe paths, and archives over each limit.
- **Boundary value analysis** — values at and just outside the stated limits: 200 versus 201
  entries, an image exactly 20 MB versus larger than 20 MB, and an archive larger than 100 MB.
  The application defines MB as 1024 x 1024 bytes, so boundary fixtures are built with that
  definition.

Every case is independent. Where a case depends on data created by another case, the
precondition states the required starting state so the case can be set up on its own.

## 4. Test environment and setup

1. Use a copy of the project with a known `data.json` and `uploads/` folder. Back up both
   before execution and restore them between test sessions.
2. Start the application from the project root with `python app.py`.
3. Open `http://127.0.0.1:5000` in a current version of Chrome or Firefox.
4. Record the starting picture count before each case. The gallery counter and the empty-filter
   gallery view both show this count.
5. Prepare the fixtures in Section 5 before execution. Each fixture is a separate file so a
   failure in one case does not contaminate another.
6. For every case, write the observed result and a pass/fail decision in the **Actual results**
   column. If the precondition cannot be established, record the case as **Not Run**, not
   **Fail**.

## 5. Test data fixtures

All images in these fixtures must be real, viewable images, not text files renamed with an image
extension, except where a case deliberately tests the renamed-file behavior.

| Fixture | Contents | Used by |
|---|---|---|
| `F-01 valid-mixed.zip` | `tree.jpg`, `rock.png`, `sky.gif` — three valid images, each under 20 MB | BB-01, BB-09, BB-10 |
| `F-02 mixed-invalid.zip` | Three valid images plus `notes.txt` and `fake.png` (a text file renamed `.png`) | BB-02 |
| `F-03 corrupt.zip` | A truncated file or a text file renamed `.zip`; it is not a readable ZIP | BB-03 |
| `F-04 empty.zip` | A valid ZIP containing zero entries | BB-04 |
| `F-05 nonimage-only.zip` | `notes.txt`, `readme.md` — no supported images | BB-05 |
| `F-06 nested.zip` | `folderA/cat.png`, `folderB/dog.jpg` — different filenames in nested folders | BB-06 |
| `F-07 duplicate-names.zip` | `folderA/cat.png`, `folderB/cat.png` — same filename, two different images | BB-07 |
| `F-08 collision.zip` | An image named exactly like an existing picture's stored file name, for example `1.jpg` | BB-08 |
| `F-09 all-formats.zip` | One valid `.jpg`, `.jpeg`, `.png`, `.gif`, and `.webp` image | BB-11 |
| `F-10 mac-metadata.zip` | `__MACOSX/._tree.jpg`, `.DS_Store`, `tree.jpg` | BB-12 |
| `F-11 unsafe-paths.zip` | `../../evil.png`, `/absolute.png`, `C:/drive.png`, `safe.png` | BB-13 |
| `F-12 over-100mb.zip` | A valid ZIP whose file size is greater than 100 MB | BB-14 |
| `F-13 201-images.zip` | 201 small valid PNG images, each a distinct entry | BB-15 |
| `F-14 200-images.zip` | Exactly 200 small valid PNG images, each a distinct entry | BB-16 |
| `F-15 oversize-image.zip` | `big.png` larger than 20 MB plus `ok.png` smaller than 20 MB | BB-17 |
| `F-16 exact-20mb.zip` | One image exactly 20 MB (20 x 1024 x 1024 bytes) plus `ok.png` | BB-18 |
| `F-17 over-500mb-extracted.zip` | 26 images of about 20 MB each; each image is within the per-image limit, but the total exceeds 500 MB | BB-19 |
| `F-18 tag-setup` | Two pictures: P1 tagged `sky`, `nature`; P2 tagged `sky`; P3 tagged `drawing` | BB-26, BB-29 |

## 6. Test cases

### 6.0 Test case inventory

| Section | Cases | Count |
|---|---|---|
| 6.1 Bulk ZIP import — core behavior | BB-01 to BB-12 | 12 |
| 6.2 Bulk ZIP import — unsafe archive paths | BB-13 | 1 |
| 6.3 Bulk ZIP import — limits and boundaries | BB-14 to BB-19 | 6 |
| 6.4 Single-image upload | BB-20 | 1 |
| 6.5 Tag editing (US-002) | BB-21 to BB-28 | 8 |
| 6.6 Browsing and existing views | BB-29 to BB-32 | 4 |
| **Total** | | **32** |

### 6.1 Bulk ZIP import — core behavior

| ID | Related AC | Preconditions | Input | Expected output | Actual results |
|---|---|---|---|---|---|
| BB-01 | US-001 AC1, AC16 | The gallery contains exactly 4 pictures, each with at least one tag. The application is running. | In **Bulk Upload (ZIP)**, choose `F-01 valid-mixed.zip` and click **Import ZIP**. Then open **Gallery View (Browse All)** with an empty tag filter. | The report reads `Imported 3 picture(s); 0 failed.` No failure bullets are shown. The gallery lists 7 pictures. Each of the 3 new pictures displays `Tags: None`. The original 4 pictures keep their tags. | |
| BB-02 | US-001 AC4 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-02 mixed-invalid.zip` and click **Import ZIP**. | The report reads `Imported 3 picture(s); 2 failed.` The failure list contains exactly two bullets: `notes.txt` with the reason `not a supported image type (jpg, jpeg, png, gif, webp)`, and `fake.png` with the reason `file contents are not a valid image`. The gallery count becomes N + 3. The 3 valid pictures are viewable; neither failed entry appears in the gallery. | |
| BB-03 | US-001 AC6 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-03 corrupt.zip` and click **Import ZIP**. | The report reads `The archive could not be read.` No picture is added and the gallery count remains N. No failure bullets are shown. | |
| BB-04 | US-001 AC7 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-04 empty.zip` and click **Import ZIP**. | The report reads `The archive contained no entries.` No picture is added and the gallery count remains N. | |
| BB-05 | US-001 AC7 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-05 nonimage-only.zip` and click **Import ZIP**. | The report reads `Imported 0 picture(s); 2 failed.` The failure list names `notes.txt` and `readme.md`, each with a reason that the entry is not a supported image type. No picture is added and the gallery count remains N. | |
| BB-06 | US-001 AC8 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-06 nested.zip` and click **Import ZIP**. Then open the gallery with an empty filter and view each new picture. | The report reads `Imported 2 picture(s); 0 failed.` The gallery count becomes N + 2. Each image appears as its own gallery entry and opens for viewing. No stored filename shown in the image address contains a folder separator. | |
| BB-07 | US-001 AC9 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-07 duplicate-names.zip` and click **Import ZIP**. Open each new picture in the gallery. | The report reads `Imported 2 picture(s); 0 failed.` The gallery count becomes N + 2. The two pictures have different identifiers and different image addresses, and both remain viewable. Deleting one does not remove the other. | |
| BB-08 | US-001 AC10 | The archive contains a picture whose stored file name is `1.jpg` and whose tag is `keep`. The application is running. | In **Bulk Upload (ZIP)**, choose `F-08 collision.zip`, which contains a different image named `1.jpg`, and click **Import ZIP**. Open the gallery with an empty filter. | The report reads `Imported 1 picture(s); 0 failed.` The existing picture still displays the tag `keep` and remains viewable. The new picture is added as a separate gallery entry with `Tags: None` and is also viewable. The gallery count increases by 1. | |
| BB-09 | US-001 AC15 | BB-01 has completed and the gallery shows 7 pictures. | Stop the application with Ctrl+C, start it again with `python app.py`, reload the page, and open the gallery with an empty filter. | The gallery still shows 7 pictures. The 3 imported pictures are still present and each still displays `Tags: None`. | |
| BB-10 | US-001 AC2 | The gallery contains at least one picture tagged `nature` and the 3 untagged pictures imported in BB-01. The application has not been restarted since the import. | In **Gallery View**, click **Show Matching Pictures** once with an empty filter and once with `nature`. Repeat both filters in the **Random Picture Viewer** and in the **Timer Slideshow**. | With an empty filter, all pictures are eligible, including the untagged imported pictures. With the filter `nature`, only pictures that have the tag `nature` are returned. The untagged imported pictures never appear under any non-empty tag filter in the gallery, random viewer, or slideshow. | |
| BB-11 | US-001 constraint: supported formats | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-09 all-formats.zip` and click **Import ZIP**. Open the gallery. | The report reads `Imported 5 picture(s); 0 failed.` All five pictures (`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`) appear as separate gallery entries and are viewable. | |
| BB-12 | US-001 assumption: OS metadata | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-10 mac-metadata.zip` and click **Import ZIP**. | The report reads `Imported 1 picture(s); 0 failed.` No failure bullets are shown. Only `tree.jpg` is added; the `__MACOSX` entry and `.DS_Store` are ignored. The gallery count becomes N + 1. | |

### 6.2 Bulk ZIP import — unsafe archive paths

| ID | Related AC | Preconditions | Input | Expected output | Actual results |
|---|---|---|---|---|---|
| BB-13 | US-001 AC5 | The gallery count is N. The application is running. Record the contents of the `uploads/` folder and its parent folder before the test. | In **Bulk Upload (ZIP)**, choose `F-11 unsafe-paths.zip` and click **Import ZIP**. | The report reads `Imported 1 picture(s); 3 failed.` The failure list names `../../evil.png`, `/absolute.png`, and `C:/drive.png`, each with the reason `path would place the file outside the uploads folder`. `safe.png` is imported and viewable. The gallery count becomes N + 1. No file named `evil.png`, `absolute.png`, or `drive.png` appears outside `uploads/` or in its parent folder. | |

### 6.3 Bulk ZIP import — limits and boundaries

| ID | Related AC | Preconditions | Input | Expected output | Actual results |
|---|---|---|---|---|---|
| BB-14 | US-001 AC11 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-12 over-100mb.zip` and click **Import ZIP**. | The report reads `The archive is larger than the 100 MB limit.` No picture is added and the gallery count remains N. | |
| BB-15 | US-001 AC12 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-13 201-images.zip` and click **Import ZIP**. | The report reads `The archive contains more than 200 images, the entry limit.` No picture is added and the gallery count remains N. The archive is refused whole; no partial import occurs. | |
| BB-16 | US-001 AC12 (boundary) | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-14 200-images.zip`, which contains exactly 200 supported images, and click **Import ZIP**. | The report reads `Imported 200 picture(s); 0 failed.` The gallery count becomes N + 200. All 200 pictures are viewable. | |
| BB-17 | US-001 AC13, AC4 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-15 oversize-image.zip` and click **Import ZIP**. Open the gallery. | The report reads `Imported 1 picture(s); 1 failed.` The failure list names `big.png` with a reason that it is larger than the 20 MB per-image limit. `big.png` is not added. `ok.png` is imported and viewable, and the gallery count becomes N + 1. | |
| BB-18 | US-001 AC13 (boundary) | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-16 exact-20mb.zip`, which contains one image exactly 20 MB and one smaller image, and click **Import ZIP**. | The report reads `Imported 2 picture(s); 0 failed.` Both images are imported and viewable. The exactly-20-MB image is not rejected. | |
| BB-19 | US-001 AC14 | The gallery count is N. The application is running. | In **Bulk Upload (ZIP)**, choose `F-17 over-500mb-extracted.zip` and click **Import ZIP**. | The report reads `The archive would extract to more than 500 MB, the extracted-size limit.` No picture is added and the gallery count remains N. The archive is refused whole; no partial import occurs. | |

### 6.4 Single-image upload

| ID | Related AC | Preconditions | Input | Expected output | Actual results |
|---|---|---|---|---|---|
| BB-20 | US-001 AC3 | The gallery count is N. The application is running. | In **Upload Picture**, choose one valid image, enter `Nature, tree` in the tag field, and click **Upload**. Open the gallery with an empty filter. | Exactly one picture is added and the gallery count becomes N + 1. The new picture displays the tags `nature` and `tree`, both lowercased with no extra whitespace. The picture is viewable. | |

### 6.5 Tag editing (US-002)

The tag-editing cases describe the behavior specified in US-002. If tag editing is not present
in the build under test, record these cases as **Not Run** and execute them once the feature is
available; do not record them as failures before the feature exists.

| ID | Related AC | Preconditions | Input | Expected output | Actual results |
|---|---|---|---|---|---|
| BB-21 | US-002 AC1 | A picture in the gallery has the tags `nature` and `tree`. The application is running. | Open that picture's tag editor. | The editor shows the current tags `nature` and `tree`. It provides a control to add a tag and a control to remove each individual tag. No tag is changed until the edit is confirmed. | |
| BB-22 | US-002 AC2, AC3, AC4, AC10 | A picture in the gallery has the tags `nature` and `tree`. The application is running. | Open the tag editor, enter `  Forest  ` as a new tag, and confirm the edit. Reload the gallery and filter it by `forest` without restarting. Then restart the application and open the gallery again. | The picture immediately shows the tags `nature`, `tree`, and `forest`. The new tag is lowercased and has no surrounding whitespace. Filtering by `forest` without a restart returns that picture. After the restart, the picture still shows `forest`. | |
| BB-23 | US-002 AC5 | A picture already has the tag `forest`. The application is running. | Open the tag editor for that picture, add `Forest` or ` forest `, and confirm. | The picture still shows exactly one `forest` tag. A message indicates that the tag is already present. No duplicate tag is created. | |
| BB-24 | US-002 AC6 | A picture is open in the tag editor. The application is running. | Enter an empty value, or only spaces, as a new tag, and confirm. | The picture's tags are unchanged. A message indicates that a tag cannot be empty. | |
| BB-25 | US-002 AC7 | A picture is open in the tag editor. The application is running. | Enter `sky, water` as new tags and confirm. | Both `sky` and `water` are added to that picture and displayed. | |
| BB-26 | US-002 AC8, AC11 | Two pictures both have the tag `sky`: P1 also has `nature`, and P2 has only `sky` (as in `F-18`). The application is running. | Open the tag editor for P2, remove `sky`, and confirm. Then filter the gallery by `sky`. Also check the random viewer and slideshow with the same filter. | P2 no longer shows `sky`; P1 still shows `sky`. Filtering by `sky` returns P1 only. P2 is not returned by the gallery, random viewer, or slideshow under the `sky` filter without restarting the application. | |
| BB-27 | US-002 AC9 | A picture's only tag is `sky`. The application is running. | Open the tag editor, remove `sky`, and confirm. Open the gallery with an empty filter and with the `sky` filter. | The picture remains in the gallery, displays `Tags: None`, and appears under the empty filter. It does not appear under the `sky` filter. | |
| BB-28 | US-002 AC12 | A picture has the tags `nature` and `tree`. The application is running. | Open the tag editor, enter `forest`, then cancel the edit or reload the page without confirming. | The picture's tags remain exactly `nature` and `tree`. The unconfirmed `forest` tag is not saved. | |

### 6.6 Browsing and existing views

| ID | Related AC | Preconditions | Input | Expected output | Actual results |
|---|---|---|---|---|---|
| BB-29 | US-002 AC8, AC11; README browsing behavior | The archive contains P1 tagged `sky`, `nature`; P2 tagged `sky`; P3 tagged `drawing`. The application is running. | In **Gallery View**, filter by `nature, sky` and click **Show Matching Pictures**. Then filter by `nature` and click again. | The filter `nature, sky` returns P1 only, because the filter requires all listed tags. The filter `nature` returns P1 only. P3 is never returned by either filter. | |
| BB-30 | README browsing behavior | At least two pictures have the tag `nature` and at least one picture does not. The application is running. | In **Random Picture Viewer**, enter `nature`, click **Give Me Random Picture** five times. | Every picture shown has the tag `nature`. No picture without `nature` is shown. When only one picture matches, that same picture may be shown again after the recent-history limit is exhausted. | |
| BB-31 | README browsing behavior | At least two pictures have the tag `nature`. The application is running. | In **Timer Slideshow**, enter `nature`, set the interval to 2 seconds, click **Start**, wait 6 seconds, then click **Stop**. | A matching picture is displayed and changes about every 2 seconds. Every displayed picture has the tag `nature`. The status text shows a running countdown. After **Stop**, the picture stops changing. | |
| BB-32 | README browsing behavior | The gallery count is N and at least one picture is present. The application is running. | Open **Gallery View** with an empty filter, select a picture, click **Delete From Gallery**, and confirm. Re-open the gallery with an empty filter. | The gallery count becomes N - 1. The deleted picture is absent from the gallery, the random viewer, and the slideshow. The remaining pictures are unaffected and still viewable. | |

## 7. Traceability matrix

### 7.1 US-001 — Bulk ZIP upload

| Acceptance criterion | Covered by |
|---|---|
| AC1 — 3 images added to 4, all untagged | BB-01 |
| AC2 — untagged imports follow empty and non-empty filters | BB-10 |
| AC3 — single-image upload behavior unchanged | BB-20 |
| AC4 — partial import with named failures and reasons | BB-02, BB-17 |
| AC5 — archive path cannot escape `uploads/` | BB-13 |
| AC6 — corrupt archive adds nothing | BB-03 |
| AC7 — empty or no-supported-image archive adds nothing | BB-04, BB-05 |
| AC8 — nested folders become individual pictures | BB-06 |
| AC9 — duplicate filenames in one archive both import | BB-07 |
| AC10 — name collision keeps the existing picture | BB-08 |
| AC11 — archive larger than 100 MB refused | BB-14 |
| AC12 — more than 200 entries refused; 200 accepted | BB-15, BB-16 |
| AC13 — image larger than 20 MB fails alone; 20 MB accepted | BB-17, BB-18 |
| AC14 — extracted content over 500 MB refused | BB-19 |
| AC15 — imported pictures survive restart | BB-09 |
| AC16 — all-valid report states zero failed | BB-01 |
| Constraint — supported formats | BB-11 |
| Assumption — OS metadata ignored | BB-12 |

### 7.2 US-002 — Tag editing and deletion

| Acceptance criterion | Covered by |
|---|---|
| AC1 — editor shows current tags and add/remove controls | BB-21 |
| AC2 — adding a tag updates the picture immediately | BB-22 |
| AC3 — tag change survives restart | BB-22 |
| AC4 — tags are trimmed and lowercased | BB-22 |
| AC5 — duplicate tag is not added and a message is shown | BB-23 |
| AC6 — empty or whitespace-only tag is rejected | BB-24 |
| AC7 — comma-separated tags are all added | BB-25 |
| AC8 — removing a tag affects only that picture | BB-26 |
| AC9 — removing the last tag leaves an untagged, visible picture | BB-27 |
| AC10 — filter reflects the added tag without restart | BB-22 |
| AC11 — filter reflects the removed tag without restart | BB-26 |
| AC12 — cancelled edit leaves tags unchanged | BB-28 |

### 7.3 Existing browsing features

| Behavior (from `README.md`) | Covered by |
|---|---|
| Gallery filters by all supplied tags | BB-29 |
| Random viewer returns only pictures matching the filter | BB-30 |
| Slideshow advances on the chosen interval and stops on demand | BB-31 |
| Deleting a picture removes it from the archive | BB-32 |

## 8. Execution and exit criteria

### 8.1 Execution procedure

1. Reset `data.json` and `uploads/` to the precondition state for the case.
2. Perform the actions in the **Input** column exactly as written.
3. Compare the observed behavior with the **Expected output** column.
4. Record what actually happened in the **Actual results** column, including the exact message
   shown and the gallery count.
5. Mark the case **Pass** only when every part of the expected output is observed. Mark it
   **Fail** otherwise, and note the first difference. Mark it **Not Run** if a precondition
   cannot be established.

### 8.2 Exit criteria

The plan is complete when:

- Every case has a recorded actual result and a pass/fail decision.
- Every US-001 and US-002 acceptance criterion in Section 7 is covered by at least one executed
  case.
- No case that exercises an acceptance criterion remains **Fail** or **Not Run** at the end of
  the semester.

## 9. Assumptions, risks, and open items

- The application is a single-user, local Flask application with no login; cases assume one
  tester at a time and the default port 5000.
- The gallery count is observed through the application's own views. Cases that check stored
  filenames or files outside `uploads/` necessarily inspect the file system; that inspection is
  used only to confirm a black box result and does not change the test input.
- Large fixtures (`F-12`, `F-13`, `F-14`, `F-17`) take time to build and can be generated once
  and reused. `F-17` should be stored as a compressed archive because its uncompressed content
  exceeds 500 MB while the archive itself is small.
- The boundary definition for size limits is 1024 x 1024 bytes per MB, matching the values used
  by the application.
- US-002 tag-editing cases are included because US-002 is part of the project requirements. If
  the feature is not in the build under test, those cases are **Not Run** until it is.
- Actual results are intentionally blank in this PM2.2 submission; they will be completed when
  the plan is executed.

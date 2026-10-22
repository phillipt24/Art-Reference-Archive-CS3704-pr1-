# User Stories: Art Reference Archive — Bulk ZIP Upload

## US-001 — Import many pictures from one ZIP archive

**Story:** As the archive owner, I want to upload a single .zip file and have every supported image inside it added to my archive as an untagged picture, so that I can stock the archive from a folder of references without uploading images one at a time.

**Acceptance Criteria**

1. Given the collection contains 4 pictures, when the user selects a .zip containing 3 supported image files and confirms the bulk upload, then the gallery lists 7 pictures, each of the 3 new pictures displays no tags, and the stored record for each new picture has an empty tag list.
2. Given pictures were imported from a .zip without tags, when the user searches the gallery, the random viewer, or the slideshow with an empty tag filter, then those pictures are eligible to appear; when the user applies any non-empty tag filter, then the untagged imported pictures are not returned.
3. Given the existing single-image upload control, when the user uploads one image with the tags "Nature, tree", then exactly one picture is added with the tags "nature" and "tree", unchanged from the current behavior.
4. Given a .zip containing 3 supported images and 2 entries that are not supported images, when the bulk upload completes, then the 3 valid images are added, the 2 failing entries are not added, and the result report lists 3 imported and 2 failed, naming each failed entry by its path inside the archive with a reason for each.
5. Given a .zip entry whose archive path would place the extracted file outside the uploads folder, when the user uploads that .zip, then that entry is rejected and named in the failure report, no file appears outside the uploads folder, and the remaining valid entries are still imported.
6. Given a corrupted or malformed .zip file, when the user selects it, then no picture is added, the picture count is unchanged, and a message states that the archive could not be read.
7. Given a valid .zip that contains no supported images — a completely empty archive, or one containing only non-image entries — when the upload completes, then no picture is added and the result report states 0 imported, and either states that the archive contained no entries or gives a reason for every entry it examined.
8. Given a .zip whose images are inside nested folders, when the upload completes, then each image is imported as its own picture, appears in the gallery as an individual entry, and opens for viewing; no stored filename contains a folder separator.
9. Given a .zip containing two entries with the same filename in different folders, when the upload completes, then both are imported as two distinct pictures and both remain viewable afterwards.
10. Given a .zip entry whose filename matches the filename of a picture already in the archive, when the upload completes, then the existing picture keeps its own tags and stays viewable, and the new picture is added as a separate picture that is also viewable.
11. Given a .zip file larger than 100 MB, when the user selects it, then the upload is refused with a message stating the size limit, no picture is added, and the picture count is unchanged.
12. Given a .zip containing more than 200 supported image entries, when the user selects it, then the archive is refused whole with a message stating the entry limit and no picture is added.
13. Given a .zip containing one supported image larger than 20 MB, when the upload completes, then that entry is named in the failure report with a size reason, it is not added, and the remaining valid entries are imported.
14. Given a .zip whose extracted image content would exceed 500 MB in total, when the user selects it, then the archive is refused whole with a message stating the extracted-size limit and no picture is added.
15. Given a bulk upload has completed, when the application is restarted and the gallery is opened, then every picture reported as imported is still present and still displays no tags.
16. Given a bulk upload where every entry is valid, when it completes, then the result report states the number imported, states zero failed, and shows no per-entry failure reasons.

**Priority:** Must-have (MoSCoW)

**Related requirements:** No `REQ-###` or `UC-###` is assigned to this capability yet; this story is the origin of those IDs. Related stories: US-002 and US-003 — pictures imported by this story arrive untagged, so tag editing is the way to make them findable by tag.

**Assumptions / dependencies:**

- Depends on the existing single-image upload, the `data.json` record shape `{id, filename, tags[]}`, and the `uploads/` folder remaining the only picture storage location; no new service or database is introduced.
- Depends on the existing AND-semantics tag filtering for criterion 2; no change to filtering semantics is requested here.
- Confirmed scope: imported pictures are always untagged; tag assignment during ZIP import is out of scope.
- Confirmed scope: valid entries are kept when other entries fail; the import is not rolled back.
- Confirmed limits: the uploaded .zip is at most 100 MB, contains at most 200 supported image entries, and each extracted image is at most 20 MB. Supported formats are JPG/JPEG, PNG, GIF, and WebP. Over-limit archives (100 MB or 200 entries) are refused whole rather than partially imported.
- The 500 MB extracted-content cap in criterion 14 is a derived safety limit for compressed archives; it is not a change to the 100 MB upload limit.
- Confirmed scope: duplicate filenames inside one .zip are both kept as separate pictures.
- The existing upload path never overwrites an existing file; bulk import follows the same rule and resolves name collisions with existing pictures by creating a new distinct stored filename.
- The application is single-user and unauthenticated, so no per-user ownership or permission rules apply.
- **Edge cases considered:** malformed or corrupt .zip (AC 6); empty .zip or only non-image entries (AC 7); nested folders flattened to individual pictures (AC 8); duplicate filenames inside one .zip kept separate (AC 9); archive paths escaping `uploads/` via `../`, absolute paths, or unusual separators (AC 5); non-image, zero-byte, and supported-extension-but-invalid files reported as failed while valid entries import (AC 4); per-entry size limit and archive limits (AC 11–14); filename collisions with existing pictures (AC 10); persistence across restart (AC 15); the result report never claims success for a rejected entry (AC 4, AC 16).

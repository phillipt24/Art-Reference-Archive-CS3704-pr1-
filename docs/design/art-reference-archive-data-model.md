# Data Model: Art Reference Archive

Scope: the whole persistence surface of the single-user Flask app - one JSON array in `data.json` and one folder `uploads/` - plus the request-scoped value objects the ZIP import (US-001) and tag operations (US-002, US-003) pass around in memory. Nothing else is stored.

## ER Diagram

```
PERSISTED STORE  --  data.json (one JSON array)  +  uploads/ (one folder)

+-------------------------------------------------------+
|                       [Picture]                       |
+-------------------------------------------------------+
|PK  id          integer, unique, not null              |
|AK  filename    string, unique, not null,              |
|                never contains a path separator        |
|    tags[]      ordered array<string>,                 |
|                0..* elements; [] is legal             |
+-------------------------------------------------------+
                         | 1
                         |
                         | 1
+-------------------------------------------------------+
|                      [StoredFile]                     |
+-------------------------------------------------------+
|PK  name        string, unique, relative to            |
|                the uploads/ folder                    |
|    bytes       integer >= 0                           |
+-------------------------------------------------------+

TRANSIENT  --  request-scoped value objects; never written to data.json or uploads/

+-------------------------------------------------------+
|                    [ImportRequest]                    |
+-------------------------------------------------------+
|    zip_bytes        integer <= 104857600 (100 MB)     |
|    max_entries      integer = 200                     |
|    image_bytes      integer <= 20971520  (20 MB)      |
|    extracted_bytes  integer <= 524288000 (500 MB)     |
|    extensions       set<string> = {jpg, jpeg,         |
|                     png, gif, webp}                   |
+-------------------------------------------------------+
                         | 1
                         |
                         | 0..1
+-------------------------------------------------------+
|                    [ImportResult]                     |
+-------------------------------------------------------+
|    imported_count  integer >= 0                       |
|    failed_count    integer >= 0, = size of failures[] |
|    failures[]      0..* [ImportFailure]               |
|    message         string, summary shown to user      |
+-------------------------------------------------------+
                         | 1
                         |
                         | 0..*
+-------------------------------------------------------+
|       [ImportFailure]  (one per rejected entry)       |
+-------------------------------------------------------+
|    archive_path    string, path of the entry          |
|                    inside the archive                 |
|    reason          string, why it failed              |
+-------------------------------------------------------+

+-------------------------------------------------------+
|              [TagUsageSummary]  (derived)             |
+-------------------------------------------------------+
|    tag             string, normalized                 |
|    affected_count  integer >= 0                       |
+-------------------------------------------------------+
                         *...... reads [Picture].tags[]  ......0..*   (derived view; nothing stored)
```

**Deliberate absences.** There is no `[User]` entity, no `owner_id`, no per-user folder and no permission column: the application is single-user and unauthenticated, so the archive itself is the only scope. There is also no `[Tag]` entity, no tag id and no join table - a tag is an *embedded, normalized string inside one picture's `tags[]`*; it "exists" only while at least one record contains it, which is why US-003's rename is a value substitution and its delete is a value removal. Both absences are choices, not oversights.

## Notation

- `+----+` box - entity (persisted or transient; the group header above it states which)
- `PK` / `FK` - primary key / foreign key (this model declares no `FK`; see Relational Schema)
- `AK` - alternate (candidate) key, i.e. a second uniqueness constraint
- `1`, `*`, `0..1`, `0..*` at a line end - cardinality of the relationship nearest that end
- a line between entities is a relationship; it is named in the Relationships table
- `......` dotted connector - derived, read-only relationship; no stored data corresponds to it
- `[]` after a name - multi-valued attribute or nested list of value objects (`tags[]`, `failures[]`)
- limits are written as byte counts, e.g. `104857600 (100 MB)`; the MB-to-byte convention is an assumption, flagged in I6

## Entities

| Entity | Purpose | Key attributes |
|--------|---------|----------------|
| [Picture] | Persisted. One element of the single `data.json` array: one viewable image plus the tags assigned to it. The array index order is the display order. | id (PK), filename (AK), tags[] |
| [StoredFile] | Persisted on the filesystem, not in `data.json`. The image bytes inside `uploads/`; it carries no metadata beyond its name, so size is whatever the filesystem reports. | name (PK), bytes |
| [ImportRequest] | Transient. The uploaded archive together with the limits it must satisfy; exists only for the duration of one request and is discarded after the report is rendered. | zip_bytes, max_entries, image_bytes, extracted_bytes, extensions |
| [ImportFailure] | Transient. One archive entry that was *not* added, and why. Rendered in the result report; never persisted, so per-entry failure history is not retained. | archive_path, reason |
| [ImportResult] | Transient. The outcome shown to the user: how many pictures were added, which entries failed, and a summary message. | imported_count, failed_count, failures[], message |
| [TagUsageSummary] | Transient and derived. Read-only projection answering "how many pictures carry this normalized tag", the number US-003 AC 11 must show before a global rename or delete is confirmed. | tag, affected_count |

## Relationships

| Relationship | Entities | Cardinality | Description |
|--------------|----------|-------------|-------------|
| designates | [Picture]-[StoredFile] | 1 : 1 | Each picture names exactly one file inside `uploads/` (its `filename`); because `filename` is unique, a file is named by at most one picture. A file named by no picture is orphaned garbage, not a relationship instance. |
| reports | [ImportRequest]-[ImportResult] | 1 : 0..1 | One import attempt produces at most one report; a request refused before processing still yields a report with `imported_count = 0`. |
| lists | [ImportResult]-[ImportFailure] | 1 : 0..* | Composition: failures are nested value objects inside the report, with no identity or lifetime of their own. Zero failures is the all-valid case (US-001 AC 16). |
| aggregates | [Picture]-[TagUsageSummary] | * : 0..* | Derived, read-only. One summary per distinct normalized tag string found in any `tags[]`; its `affected_count` is the number of pictures whose `tags[]` contains that string. Nothing is stored for this relationship. |

Note: a ZIP entry is *not* modeled as an entity. It is transport, not state - its path survives only as `ImportFailure.archive_path`, and it never influences a picture's identity or stored filename (see I2).

## Relational Schema

**There is no DBMS in this system.** The persisted store is a single JSON file, `data.json`, holding one JSON array whose elements are picture records. There is no SQL table, no index, no declared foreign key, and no partial update: the file is read in full and rewritten in full. The table below documents the *record (document) schema* of that array plus the shape of the file each record points at on disk. It is schema documentation, not DDL, and the constraints in the last column are enforced only by application code.

| Table | Column | Type | Key / constraint |
|-------|--------|------|------------------|
| picture (element of the `data.json` array) | id | integer (JSON number) | PK - unique across all elements, not null; must stay a JSON integer that survives `int(...)`, `<int:picture_id>` URL conversion and `jsonify` |
| picture | filename | string | AK - unique, not null; basename only, no `/`, no `\`, no `..`; must resolve to an existing file directly inside `uploads/` |
| picture | tags | array of string | not null, may be empty `[]`; ordered (order is display order); each element normalized - trimmed, lowercase, non-empty, comma-split at input, no duplicates within the record |
| stored file (`uploads/` folder entry) | name | string | PK - unique filename in the folder, equal to exactly one `picture.filename` |
| stored file | content | binary | not null; the image bytes; the record stores no size, MIME type or checksum, so those are re-derived from the file at request time |

Consistency notes: `picture` is the only collection, so there is no join table and no second row group to drift out of sync. `picture.filename` to `stored_file.name` is the only reference in the model, and it is unenforced (see I4). All queries - gallery, tag filter, random viewer, slideshow, affected-count - are linear scans of the in-memory array, which is viable only at this scale (7 records now, at most 200 added per import).

## Invariants and Constraints

**I1 - Picture identity: `id` is unique.**
Every element of the array must have a distinct `id`. The current implementation derives it as `int(time.time() * 1000)`, which is safe for one upload per human click and *not* safe for a loop: several ZIP entries processed inside the same millisecond receive the same `id`. That failure is silent - the gallery still renders, but `DELETE /api/pictures/<id>` removes the first match, `exclude_ids` in the random viewer excludes both records, and the per-picture tag editor writes to whichever record matches first. An import of 200 entries makes this near-certain, not hypothetical. Required invariant, mechanism unspecified: distinct `id` per record even for a batch of 200 entries created in one request, and `id` remains a JSON integer (not a string, not a UUID that breaks `<int:picture_id>`).

**I2 - Stored filename: unique, and independent of the archive path.**
`filename` is a basename inside `uploads/`; it contains no `/`, no `\`, no `..` and no drive letter, and it never equals another record's `filename`. The archive path is a property of the *transport*, never of the record: an entry `a/cat.png` and an entry `b/cat.png` become two records with two different ids and two different stored filenames (US-001 AC 9), and only the extension is carried over from the entry name - the current single upload already discards the original basename. An entry whose name would collide with an existing stored file becomes a *new* record with a *new* filename; the existing record and its tags are untouched (AC 10), because import must never merge or overwrite by name. `os.path.join(UPLOAD_FOLDER, archive_path)` with an entry named `../../x.png` escapes the folder, which is exactly the hazard AC 5 requires to be rejected rather than resolved. The same millisecond-derived collision that threatens `id` also threatens the filename, and there the consequence is worse: two imports in one tick target the same path, so one image's bytes replace the other's on disk while both records claim to exist. Verification after any import: `len({r['id']}) == len(data)` and `len({r['filename']}) == len(data)`.

**I3 - Tag values are normalized strings, ordered, and local to one picture.**
Each element of `tags[]` is the normalized form (trim, lowercase, split on comma, drop empty, de-duplicated within the record). An empty array is a legal and meaningful state - "untagged" - not a missing value: it matches the empty filter and matches no non-empty filter, which is what US-001 AC 2 requires. "None" is a display rendering, never a stored value. Because tag identity is string identity, three consequences follow: a tag used on zero pictures is a no-op (US-003 AC 9), a rename is a value substitution across records rather than a key update, and a rename onto an existing tag merges without duplicates (US-003 AC 2, 3). Renames intake the same normalization (`  Forest  ` becomes `forest`, AC 4) and a rename to a case/whitespace variant of itself is a no-op, not an error (AC 6). Merge must be deterministic - the first occurrence's position wins - so the persisted order does not churn between equivalent saves. No cross-record constraint applies: a tag may appear on any number of records, and within one record it may appear at most once. Underscores and internal spaces inside a tag are preserved; only commas and outer whitespace are separators.

**I4 - Referential integrity: no record may reference a missing file.**
Every `picture.filename` must resolve to a readable file inside `uploads/`; every file in `uploads/` should be referenced by a record. The two failure directions are not symmetric: a record without a file is a broken gallery tile the user sees, while a file without a record is invisible garbage that costs disk. The invariant to hold is therefore "no dangling record", with orphaned files tolerated. Nothing enforces this automatically - no database, no foreign key - and the current delete order removes the file and *then* rewrites `data.json`, so a crash in between leaves exactly the dangling record the invariant forbids. Any delete path must be sequenced so that invariant holds through a crash. Filenames must keep being resolved relative to `uploads/` (as `send_from_directory` already does, refusing paths that escape the folder); switching to raw absolute paths would re-open the traversal hole closed by AC 5.

**I5 - The store is replaced whole; no partial state is ever observable.**
`data.json` is one array, parsed in full and rewritten in full. US-003 AC 15 (all-or-nothing) and US-002 AC 12 (a cancelled edit leaves stored tags untouched) both require that a change be composed in memory and written once; a tag operation that rewrites the store per picture is not all-or-nothing. Tag-only operations never change the number of elements - no edit, rename or delete may add or remove a record (US-003 AC 1, 7, 14; US-002 AC 9) - because tag state lives inside records and has no independent existence to drift. Existing hazard: `load_data()` returns `[]` when JSON parsing fails, so a truncated file is silently presented as an empty archive and the next save makes the loss permanent. The model requires the persisted array to be either the complete old array or the complete new one; how that is achieved is an implementation decision.

**I6 - Import limits are gates, and the report never disagrees with the store.**
Two kinds of gate. *Whole-archive*, checked before any write: zip larger than 100 MB, more than 200 supported entries, extracted content over 500 MB, or an archive that cannot be read - all produce zero records, zero new files and a report with `imported_count = 0` (US-001 AC 6, 11, 12, 14). *Per-entry*, no rollback of siblings: unsupported extension, entry over 20 MB, zero-byte or undecodable image, or an entry path escaping `uploads/` - each produces one `ImportFailure{archive_path, reason}` and the other entries still import (AC 4, 5, 13). `imported_count` must equal the number of records actually added and `failed_count` must equal `len(failures[])`; a report may never claim success for a rejected entry (AC 4, 16). An empty or all-non-image archive reports 0 imported plus either the "no entries" message or a reason per entry (AC 7). Imported pictures are always created with `tags: []` - the import channel carries no tags and none may be inferred from folder names (AC 1, 15).
*Assumption to validate:* the byte figures treat 1 MB as 1 048 576 bytes (so 100 MB = 104 857 600, 20 MB = 20 971 520, 500 MB = 524 288 000). US-001 does not say MB or MiB; the difference is about 4.8 percent of the threshold. Confirm with the requirements owner before hard-coding the constants.

**I7 - Single user, no ownership, no timestamps, no schema version.**
Deliberate omissions: no `user_id`, no `created_at`, no `updated_at`, no `size`, no `content_type`, no `schema_version`. Without ownership there is no permission column and no loss-of-update conflict between editors, but also no audit trail of who changed what. `id` must not be read as a timestamp: the 7 existing ids happen to be epoch milliseconds, yet nothing in the model may depend on their numeric ordering or on their clock meaning - display order is array order. Without a version field, any future field must be optional and defaulted at read time, because the 7 existing records have exactly three keys and must not be migrated.

**I8 - The 7 existing records already satisfy every invariant.**
`data.json` holds 7 records, each `{id: integer, filename: "<epoch ms>.jpg", tags: [lowercase strings]}`: ids distinct, filenames distinct basenames with no separator, tag lists non-empty, lowercase, whitespace-free and duplicate-free. They load, filter and render unchanged. No migration script, no rewrite-on-read, and no new required field.

**I9 - Known, unsolved risk: read-modify-write has no lock.**
Load, mutate and save are three steps with no mutual exclusion. Two overlapping writes - a double-clicked upload, a gallery refresh racing an import, a delete during a tag save - can lose one whole update, since the later writer serializes a snapshot that lacks the earlier writer's record. No requirement covers this, and the model does not add a version column to solve it; the acceptable mitigation is to serialize writes inside the process. Recorded here so it is a known limitation rather than a surprise.

## Traceability

| Requirement area | Carried by |
|------------------|------------|
| US-001 AC 1, 15 (untagged import, persists) | I6, I5, I8 |
| US-001 AC 4, 7, 13, 16 (partial success, honest report) | I6 |
| US-001 AC 5, 8, 9, 10 (path safety, nested folders, duplicates, collisions) | I2, I4 |
| US-001 AC 6, 11, 12, 14 (whole-archive refusals) | I6 |
| US-001 AC 2 (untagged photos and filters) | I3 |
| US-001 AC 3 (single upload unchanged) | I1, I2, I3, I8 |
| US-002 AC 2-11 (per-picture edits, normalization, duplicates) | I3 |
| US-002 AC 12 (cancel leaves tags untouched) | I5 |
| US-003 AC 2, 3, 4, 6, 9 (rename merge, normalization, no-op) | I3 |
| US-003 AC 11 (affected count before confirming) | I3, [TagUsageSummary] |
| US-003 AC 1, 7, 14 (picture count unchanged, no file loss) | I5, I4 |
| US-003 AC 15 (all-or-nothing) | I5 |

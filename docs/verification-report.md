## Verification Report

Run date: 2026-11-14 — verification of branch `feature/trashcan`, which adds US-004
(trash, restore, permanent delete) and the new `tests/test_trashcan.py`. Scope: the full
suite in `tests/` (85 test functions / 108 collected cases).

| Gate | Result | Details |
|------|--------|---------|
| Unit‑test integrity | PASS | `.\.venv\Scripts\python.exe -m pytest -q` → `108 passed in 1.20s`, exit code 0. Zero failures or errors. |
| Build integrity | PASS | `.\.venv\Scripts\python.exe -m compileall -q -x "(\.venv\|__pycache__\|\.git)" .` → exit code 0. Port 5000 confirmed free before start; `app.py` served `GET http://127.0.0.1:5000/` → **HTTP 200 in 833 ms** (within the 5 s window). Flask's `debug=True` reloader child was terminated with the launcher's process tree; port 5000 confirmed **closed** afterwards. |
| Traceability | PASS | **82 / 85 test functions tagged = 96.47%** (threshold ≥ 0.75 ⇒ ≥ 64/85). Per file: `test_acceptance_gaps.py` 7/7, `test_tag_editing.py` 16/17, `test_trashcan.py` 20/20, `test_zip_import.py` 39/41. |
| Coverage (optional) | 93% | `.\.venv\Scripts\python.exe -m pytest -q --cov=app` → `app.py` 290 statements, 19 missed, **93%** line coverage (reporting threshold 85%); 108 passed, exit code 0. `.coverage` artifact deleted after the run. |

**Overall: VERIFIED**

### Notes

**US-004 coverage.** The new `tests/test_trashcan.py` contains **20 tagged test functions,
one for each acceptance criterion AC 1–20** of `docs/requirements/US-004-trashcan-soft-delete.md`.
Every function carries a `# AC-US-004-<nn>` tag (`01`–`20`), so every US-004 AC has at
least one executable test. The file uses the same `tmp_path` `data.json` / `uploads/`
fixtures as `tests/test_zip_import.py`, so real app data is never touched. Routes, status
codes (`200`/`404`/`409`) and error substrings asserted by the tests match
`docs/design/us-004-trashcan-sequence-diagram.md` (including "already in the trash",
"not in the trash", "no longer exists", and the unavailable-image refusal).

**Traceability before/after.** The previous run measured **62/65 = 95.38%** across three
modules. This run counts **82/85 = 96.47%**: the 20 fully tagged US-004 functions were
added, and the three intentionally untagged functions from the previous report remain
untagged. Threshold arithmetic: `ceil(0.75 × 85) = 64` tagged functions required; 82 present.

**Counting rule used.** One top-level `def test_...` (or `async def test_...`) in a
`tests/*.py` module counts as one test. A function is "tagged" when an `# AC-US-<n>`
comment appears inside its body (AST node line range, decorators included in the range).
`@pytest.mark.parametrize` cases are **not** expanded — hence 85 functions counted versus
108 collected/passing cases.

**Three intentionally untagged tests (not a defect).** These predate this task and were
left unmodified; adding a tag would either be a false trace link or would require editing
an existing module, which the US-004 test task prohibited.

| Test | Why no tag was added |
|------|----------------------|
| `tests/test_zip_import.py::test_corrupt_data_json_is_not_overwritten` | No AC covers recovery from a corrupt `data.json` (robustness/defensive behaviour outside the AC set). |
| `tests/test_zip_import.py::test_delete_removes_record_and_file` | Updated by the US-004 implementation commit to exercise soft delete then permanent delete, but it lives in `test_zip_import.py` and was intentionally not modified by the US-004 test task. AC 8 is separately covered by `test_trashcan.py::test_ac8_permanent_delete_removes_record_and_file_for_good`, so traceability is unaffected. |
| `tests/test_tag_editing.py::test_edge_editing_deleted_picture_returns_404_and_changes_nothing` | No AC describes editing a picture whose file was removed out-of-band (404 edge case). |

**Coverage detail.** `app.py`: 290 statements, 19 missed → 93% line coverage, above the
85% reporting threshold. Coverage is reported only; it is not a pass/fail gate.
`pytest-cov 7.1.0` was installed into the project `.venv` to run this optional gate; no
repository files were changed by that install.

**Data safety.** `data.json` was not modified (LastWriteTime still 2026-10-13 10:25:01)
and `uploads/` still holds its 7 files. The suite uses temporary directories, and the live
build check issued a single `GET /` with no writes. The only changes produced by this
session are the new `tests/test_trashcan.py` and this report; `compileall` may have
refreshed gitignored `__pycache__/` directories.

**Verdict rationale.** All three required gates (unit-test integrity, build integrity,
traceability) passed on captured output, and the optional coverage gate reports 93% against
an 85% threshold. No gate failed, so `feature/trashcan` with US-004 is **VERIFIED** for the
next milestone.

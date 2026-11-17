---
name: test
description: "Generates (or updates) pytest tests, runs them, and adds AC tags for traceability."
---
# Test Skill

## Overview
This skill is executed by the **tester** agent. It follows three phases:

1. **Planning** – prints a plan (what files will be created/modified, which commands will be run) and asks the user for approval (`question` tool). The skill does **not** modify anything until the user confirms.
2. **Generation / augmentation** – creates new test functions in `tests/` or updates existing ones, inserting an AC comment (`# AC‑US‑001‑03`) for each test that directly exercises an acceptance criterion. The skill only writes inside the `tests/` folder.
3. **Execution** – runs `pytest -q` (and optionally `pytest --cov=app`). The full output is captured and returned to the caller.

## Acceptance criteria for the skill
* All generated/updated test functions contain **exactly one** `# AC‑…` comment that matches an AC present in one of these user stories:
  * `docs/requirements/US-001-zip-bulk-upload.md` (tags `# AC-US-001-<n>`)
  * `docs/requirements/US-002-tag-editing-and-deletion.md` (tags `# AC-US-002-<n>`)
  * `docs/requirements/US-004-trashcan-soft-delete.md` (tags `# AC-US-004-<n>`, AC 1–20)
* For US-004, also read `docs/design/us-004-trashcan-sequence-diagram.md`: it defines the routes (`DELETE /api/pictures/<id>` is a soft delete; `GET /api/trash`, `POST /api/trash/<id>/restore`, `DELETE /api/trash/<id>`), the status codes (`404` = picture no longer exists, `409` = wrong state) and the expected error messages that tests should assert.
* Put new US-004 tests in a new file, `tests/test_trashcan.py`, using the same temporary `data.json` / `uploads/` fixtures as `tests/test_zip_import.py` so real data is never touched.
* The skill never writes outside the `tests/` folder.
* If a test fails, the skill returns a short description of the failure and a **git‑style diff** that would fix the failing assertion. The diff is **not applied** until the user explicitly approves.
* Do not edit tests that have already been created and pass without asking for permission. You are allowed to create a new test file to avoid this. 

## How to run
```text
@tester /test
```
The tester will load this skill, ask for approval, then perform the steps.

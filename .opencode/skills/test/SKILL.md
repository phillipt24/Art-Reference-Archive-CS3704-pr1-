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
* All generated/updated test functions contain **exactly one** `# AC‑…` comment that matches an AC present in `docs/requirements/US‑001‑zip‑bulk‑upload.md` or `US‑002‑tag‑editing‑and‑deletion.md`.
* The skill never writes outside the `tests/` folder.
* If a test fails, the skill returns a short description of the failure and a **git‑style diff** that would fix the failing assertion. The diff is **not applied** until the user explicitly approves.
* Do not edit tests that have already been created and pass without asking for permission. You are allowed to create a new test file to avoid this. 

## How to run
```text
@tester /test
```
The tester will load this skill, ask for approval, then perform the steps.

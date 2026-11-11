---
name: verify
description: "Runs quality‑gate checks (unit tests, build, traceability) and writes a verification report."
---
# Verify Skill

## Overview
Executed by the **verifier** agent. It implements the gates you defined and produces a markdown verification report.

### Gates
| Gate | Command | Pass condition |
|------|---------|----------------|
| Unit‑test integrity | `pytest -q` | Exit status 0 (no failures) |
| Build integrity | `python -m compileall .` **and** `python app.py` (responds HTTP 200 on `/` within 5 s) | Both commands exit 0 and the HTTP check succeeds |
| Traceability | parse `tests/*` for `# AC‑…` comments | (`# tagged tests` / `# total tests`) ≥ 0.75 |
| (Optional) Coverage | `pytest --cov=app` | Line coverage ≥ 85 % (reported only) |

## Procedure
1. **Plan step** – print a concise list of the commands that will be run and ask the user for a single “Yes/No” confirmation via the `question` tool. Do **not** run anything until the user answers “Yes”.
2. **Run each gate in order** – stop on the first failure and capture its output.
3. **If a gate fails** – produce a short explanation of what went wrong and a **suggested fix** (e.g. “Add missing AC tags”, “Fix failing test X”). The fix is **not applied** until the user explicitly approves.
4. **Write the report** – the only file the verifier may edit is `docs/verification-report.md`. The report follows the required table format:
   ```markdown
   ## Verification Report

   | Gate | Result | Details |
   |------|--------|---------|
   | Unit‑test integrity | PASS/FAIL | <details> |
   | Build integrity | PASS/FAIL | <details> |
   | Traceability | PASS/FAIL | <details> |
   | Coverage (optional) | <%> | <details> |
   
   **Overall: VERIFIED / NOT VERIFIED**
   ```
5. **Never edit** anything outside `docs/verification-report.md`. If a request would modify other files, raise an error.

## How to run
```text
@verifier /verify
```
The verifier will load this skill, request approval, then perform the checks and produce the report.

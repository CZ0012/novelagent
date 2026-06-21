# Blockers

Use this file for blockers that cannot be solved inside the current owner scope. Prefer handoffs for ordinary cross-agent work.

## Open Blockers

No open blockers.

## Blocker Template

```text
ID:
Task:
Owner:
Blocking condition:
Why it blocks:
Options:
Needed decision:
Status:
```

## Closed Blockers

### SG-002-BLOCKER-001

ID: SG-002-BLOCKER-001
Task: SG-002H
Owner: Test Creation Agent / Check Agent
Blocking condition: The configured KouriChat endpoint accepted the corrected request shape but returned repeated HTTP 429 `Service is busy` responses for `deepseek-v4-flash`.
Why it blocked: The private real-Agent smoke test could not complete the external LLM `write_draft` step with `deepseek-v4-flash`.
Resolution: Probed KouriChat `/v1/models` and tested alternate chat models. `gpt-4o-mini` returned HTTP 200 and completed the real LLM + private DOCX smoke test.
Status: closed

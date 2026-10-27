# Blockers

Use this file for blockers that cannot be solved inside the current owner scope. Prefer handoffs for ordinary cross-agent work.

## Open Blockers

No open blockers for the completed bounded acceptance. SG-031-BUDGET was explicitly approved and later raised to a shared total100CNY with no global call cap. Live acceptance is finished within that cap; no paid worker is running. Historical blocker records below are retained.

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

### SG-031-BUDGET — Pending live acceptance approval

Task: SG-031 final real-provider acceptance.
Owner: Main Agent.
Blocking condition: automatic approval review rejected the proposed up-to80paid-call DeepSeek Pro acceptance run because the earlier API authorization did not explicitly specify this scale or a cost cap.
Affected scope: the full real-model100chapter/200scene plan run only. Offline tests, UI verification and local packaging continue.
Prepared safe result: an isolated acceptance runner with80-call cap and30CNY conservative preflight reservation using verified official peak prices, balance checks, persistent unknown-call reservations and explicit pause behavior. Offline budget guard tests passed; no batch model call began.
Needed decision: the async user question asks approval for up to80calls with30CNY budget, or offline-only acceptance. Do not bypass the rejection with smaller indirect loops or another agent.
Status: closed — user explicitly approved up to80calls and30CNY, then requested consideration of4.1 Flash. Main uses Flash for the primary flow, with all comparison and acceptance calls sharing the same cap.

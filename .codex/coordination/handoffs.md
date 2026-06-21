# Cross-Agent Handoffs

Use this file when one agent discovers a problem that another agent must address. Handoffs should be concrete, branch-aware, and small enough to act on.

## Open Handoffs

No open handoffs.

## Handoff Template

```text
Task:
From:
Requested agent:
Source branch:
Relevant files:
Problem:
Expected change:
Contract boundary:
Verification:
Unblock condition:
Status:
```

## Closed Handoffs

### SG-003-HANDOFF-001

Task: SG-003D
From: Front Agent
Requested agent: Workflow / Backend Creation Agent
Source branch: `codex/sg-003-front-proposal-inbox`
Relevant files: `apps/web/src/App.tsx`, `apps/web/src/api.ts`, `apps/api/main.py`, `storygraph/stores/proposal_store.py`
Problem: The `协作草稿箱` UI needs explicit backend promotion routes before it can safely expose `转为场景草稿`, `抽取为候选事实`, and `提交 canon review` actions.
Expected change: Add permission-gated backend routes that promote accepted/non-terminal proposal content through existing Draft Store, CandidateFact, and ReviewService boundaries without direct Graph Store writes.
Contract boundary: `proposal_artifact_v1` remains non-canon; promotions must record proposal/version refs in derived audit metadata and preserve existing `candidate_fact_v1` and ReviewService semantics.
Verification: API tests prove proposal create/revise/review does not mutate Graph/Draft/Candidate stores, while explicit promotion routes mutate only their intended stores with required permission gates.
Resolution: Added accepted `scene_draft` proposal promotion to Draft Store, accepted `fact_draft` proposal promotion to pending CandidateFacts from a real source draft, and `scene_generation` `output_target=proposal_workspace`.
Status: closed

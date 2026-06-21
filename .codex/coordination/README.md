# Local Coordination Workspace

This directory is the shared Markdown workspace for asynchronous Codex development. It makes local planning, handoffs, blockers, decisions, and git branch state visible across agents.

These files are coordination artifacts only. They are not StoryGraph runtime state, canon state, workflow state, project settings, imported documents, or draft storage.

## Files

- `board.md`: task board with owners, status, acceptance criteria, and next action.
- `handoffs.md`: requests from one agent to another when a change crosses ownership boundaries.
- `blockers.md`: unresolved blockers that need Main Agent, user, or cross-agent decisions.
- `branches.md`: local git branch map for async work and review visibility.
- `decisions.md`: durable coordination or architecture decisions.

## Rules

- Main Agent owns the overall task board and closes tasks only after check/review state is clear.
- Any agent may add a handoff when it finds a problem outside its ownership.
- Blockers should be specific enough to unblock with a decision or implementation task.
- Decisions should be durable; ordinary task notes belong on the board or handoff file.
- Do not store secrets, API keys, private manuscript text, unreleased draft prose, or credentials here.
- Do not treat these files as evidence that runtime behavior works; Check Agent must verify through code, tests, builds, or API/UI smoke checks.

## Async Flow

1. Main Agent creates or updates a board item.
2. Main Agent assigns standing agents or a temporary Creation Agent.
3. The owner records the git branch in `branches.md`.
4. The owner implements or investigates the scoped task.
5. Cross-agent needs are written to `handoffs.md`.
6. Real blockers are written to `blockers.md`.
7. Check Agent verifies contracts, tests, build health, and safety boundaries.
8. Review Agent verifies that the result meets the user's intended goal.
9. Main Agent closes the board item and records durable decisions if needed.

## Git Visibility

Use git branches to show independent workstreams, not to hide uncertainty. Branch map entries should name the owner, base branch, scope, changed areas, review status, and merge target.

Preferred branch format:

```text
codex/sg-123-short-scope
```

Branches may remain local unless the user asks to push or open a pull request.

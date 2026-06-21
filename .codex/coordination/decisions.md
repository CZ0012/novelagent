# Coordination Decisions

This file records durable decisions about how Codex agents collaborate in this repository. It should not replace `docs/architecture.md` or `contracts/`.

## ADR-0001: Use Governance-Oriented Codex Development Agents

Date: 2026-06-21

Status: accepted

Decision:

The active Codex development roster is Main Agent, Review Agent, Check Agent, Front Agent, Contract Agent, and temporary Creation Agents. Older feature-module subagent files are retired. Product/runtime contract names such as Context Agent, Writing Agent, Canon Agent, Graph Agent, and QA Agent may remain in contracts as StoryGraph workflow module names, but they are not the current Codex development roster.

Rationale:

The project has moved from architecture setup into MVP implementation. The main coordination need is now planning, contract discipline, UI/API integration, verification, and async handoffs rather than one standing subagent per story workflow module.

## ADR-0002: Use Local Markdown Files For Async Agent State

Date: 2026-06-21

Status: accepted

Decision:

Agents use `.codex/coordination/board.md`, `handoffs.md`, `blockers.md`, `branches.md`, and `decisions.md` to communicate local asynchronous work state.

Rationale:

Frontend, backend, contract, and review work can progress on different timelines. Local Markdown files make ownership, blockers, and handoffs visible without treating chat history as the only source of coordination truth.

Constraints:

Coordination files must not contain secrets, API keys, private manuscript text, draft prose, runtime canon, workflow state, imported documents, or project settings.

## ADR-0003: Use Git Branches To Show Async Workstreams

Date: 2026-06-21

Status: accepted

Decision:

Use local git branches, preferably named `codex/sg-123-short-scope`, to show independent workstreams. Record branch ownership, scope, and review state in `.codex/coordination/branches.md`.

Rationale:

Branch visibility lets agents inspect diffs, compare implementations, and hand off work without blending unrelated changes into a single hidden working tree.

Constraints:

Branches may remain local unless the user asks for push or pull request work. Agents must not force-reset, discard user changes, or use git operations to bypass unresolved contract, review, or canon-safety concerns.

# Project Agent Instructions

## Scope

These instructions apply to the whole repository.

This repository is being prepared for the StoryGraph Agent project: a long-form fiction writing system driven by structured canon, graph retrieval, draft isolation, human review, and continuity checks.

## Current Phase

The project has moved from instruction and contract setup into MVP implementation.

Application source files are allowed when they are explicitly aligned with `docs/architecture.md` and the versioned contracts under `contracts/`. Keep implementation scoped to the StoryGraph Agent architecture and preserve the canon safety rules below.

## Architecture Source

The architecture source of truth is:

- `docs/architecture.md`

Before implementing future work, read that document and the relevant contract files under `contracts/`.

## Multi-Agent Workflow

Subagent role instructions live in:

- `.codex/agents/director.md`
- `.codex/agents/graph_agent.md`
- `.codex/agents/context_agent.md`
- `.codex/agents/writing_agent.md`
- `.codex/agents/canon_agent.md`
- `.codex/agents/qa_agent.md`

Use the Director as the coordination layer. The Director should split work, confirm contract boundaries, and keep other agents aligned with `docs/architecture.md`.

## Canon Safety Rules

- The Graph Store is the source of truth for canon state.
- Draft text, generated summaries, and model hypotheses must not directly mutate canon.
- Automated extraction may only produce `CandidateFact` records or proposed graph patches.
- A candidate fact becomes canon only after explicit human review.
- Every canon write must have provenance: source scene, source draft, rationale, reviewer decision, and event log entry.
- Vector search may assist retrieval, but it must never override graph canon.

## Contract Rules

- Treat files in `contracts/` as versioned boundaries between agents and future implementation modules.
- Keep contract changes small and explicit.
- When changing a contract, update all affected subagent instructions in the same task.
- Do not silently rename fields, statuses, node labels, edge labels, or report severities.

## Documentation Rules

- Prefer precise Markdown over implementation sketches.
- JSON examples are allowed in contract documents, but they are illustrative unless explicitly marked as required.
- Avoid adding code files while the project is still in the instruction-structure phase.

## Shell And File Writing Notes

This workspace uses PowerShell by default. Distinguish PowerShell from Windows PowerShell when documenting commands.

When writing multi-line raw content from PowerShell in future tasks, prefer single-quoted here-strings so `$`, backticks, braces, Markdown, JSON, YAML, and regexes are not interpolated unexpectedly.

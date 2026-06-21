# Codex Development Agent Roster

This directory defines the Codex development subagents for the repository. These are project-work roles, not the runtime StoryGraph workflow modules.

Current standing roles:

- `main_agent.md`: planning, task routing, async coordination, and git branch visibility.
- `review_agent.md`: product-goal and acceptance review.
- `check_agent.md`: code, contract, test, and compliance checks.
- `front_agent.md`: frontend, Chinese-first UX, and desktop/web interaction design.
- `contract_agent.md`: versioned contracts, API/schema boundaries, and protocol drift.
- `creation_agent.md`: template for temporary implementation agents created for a scoped task.

Contract documents may still name runtime modules such as Context Agent, Writing Agent, Canon Agent, Graph Agent, or QA Agent. Those names describe StoryGraph workflow producers and consumers. They do not override this Codex development roster.

Use `.codex/coordination/` for local Markdown task state, branch mapping, blockers, decisions, and cross-agent handoffs.

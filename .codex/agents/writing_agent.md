# Writing Agent

## Mission

Own scene-generation behavior for StoryGraph. The Writing Agent creates or revises draft prose from a valid Context Pack while respecting canon, POV, knowledge boundaries, and style constraints.

## Primary References

- `docs/architecture.md`
- `contracts/context_pack_v1.md`
- `contracts/continuity_report_v1.md`
- `contracts/workflow_run_v1.md`

## Responsibilities

- Define prompt constraints for scene drafting and revision.
- Generate only the requested scene or passage.
- Preserve POV limits and character knowledge boundaries.
- Include required scene elements from the Context Pack.
- Avoid introducing major new canon unless explicitly requested.
- Return draft artifacts through the workflow orchestrator instead of changing workflow state directly.
- Return draft text, short scene summary, and self-check notes when asked in future implementation work.

## Expected Outputs

- Prompt guidance.
- Drafting behavior rules.
- Revision rules based on continuity reports.
- Notes for style consistency and dialogue voice.

## Boundaries

- Do not write directly to the Graph Store.
- Do not create `CandidateFact` records; that belongs to Canon Agent.
- Do not ignore `must_not_violate` constraints.
- Do not reveal secrets that are outside the POV character's knowledge.
- Only add implementation that is scoped to the MVP architecture and versioned contracts.

## Required Drafting Discipline

When writing in future implementation work:

- Treat the Context Pack as the hard boundary.
- Ask the Director for clarification if required context is contradictory.
- Prefer local revision over wholesale rewrite when responding to QA reports.
- Keep literary expression flexible while preserving canon constraints.

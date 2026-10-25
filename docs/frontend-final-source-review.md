# Final frontend source review

Date: 2026-10-25
Owner: Front Agent
Scope: current 0.2.0 source on the shared SG-029/SG-030/SG-031 integration branch.

## Review scope

Reviewed collaboration controls, planning-run errors/recovery, explicit review/application, temporal corrections, scene-plan/knowledge/style evidence and DeepSeek thinking/effort settings against the versioned contracts. No browser interaction, paid provider call, private manuscript inspection or root acceptance-report change was performed.

## Substantive findings fixed

- The Context inspector omitted the supported approved scene plan, scene-entry knowledge boundaries, world rules and actual style evidence. Added a read-only ContextEvidence projection with explicit planning-versus-realized-fact wording, seed-payoff protection and stable provenance. API types now reflect the existing scene-plan envelope. Saved project style is labelled approved rather than suggested.
- Discussion could omit unsaved author text by excluding the saved Draft. The common inclusion policy, visible send control and request boundary now block dirty Draft sends consistently. Save and send remain separate exact-Draft actions.
- The source_changed planning pause code lacked localized guidance and left ordinary resume available. Added Chinese/English guidance and blocked immutable changed-source resume.

## Preserved boundaries

- Five scene Agent modes share the protected editor and exact saved Draft scope.
- Manual planning and autonomous staged planning remain distinct. Internal branch artifacts remain read-only; canon application requires exact accepted human approval.
- Whole-book review is described as blueprint plus scene summary/outcome/dependency/clue cross-checks with separate batch reviews. It does not claim to inspect unwritten prose.
- Polling is read-only. Unknown-call retry, budget increases, recheck-only, chosen-step restart and blueprint copying require explicit author actions. Copying does not start a paid run.
- Temporal entry/through projections preserve unknown and ambiguous states. Corrections use exact original saved text, UTF-8 hash and codepoint offsets; CRLF, non-BMP and repeated spans have regressions.
- Official DeepSeek thinking/effort controls preserve legacy omission, explicit clearing and frozen task snapshots. They never silently change provider, model or protocol.

## Actual verification

- Complete frontend suite: **28 files, 259 tests passed**.
- `npm run build`: passed (TypeScript and Vite production build).
- `git diff --check -- apps/web/src`: passed.
- Added regressions for plan intent versus realized facts, seed-payoff protection, entry knowledge/suspicion separation, snapshot names, approved style evidence, bilingual legacy packs and dirty/source-change guards.

This is source/test evidence only. Main Agent owns live-model quality, browser acceptance, packaging/release checks and overall goal closure.

## Coordination handoff

This agent has read-only access to `.codex`, so the requested role/coordination append was not written there. Main Agent may mirror the summary into its coordination record. Existing Front Agent instructions already require the dirty-state rule fixed above; retain explicit read-only Context Pack evidence and changed-source recovery semantics in future reviews.

## Live-UI follow-up

Main Agent found that an empty Context tab lacked its own build action. Added an explicit Build/Refresh Context button to both empty and populated inspector states, reusing the existing read-only context builder with busy/scene guards. No automatic provider call is introduced.

After this small follow-up: Context/localization focused suite **11 tests passed**, production build passed and diff checks passed. The complete **259-test** result above was obtained before this final action-button addition; the final added case was exercised in the focused run.

## Large-project inspector follow-up

Main Agent's real browser fixture with 100 Chapters/200 Scenes exposed an unbounded graph/timeline footer squeezing Context evidence to a 28px row. The active inspector panels now occupy one dedicated scrollable flexible row. Graph/timeline display is collapsed by default and bounded when expanded; all underlying nodes/scenes remain available. Inspector tab changes reset the shared viewport to its top without discarding editor or settings state.

After this layout fix: **14 focused markup/CSS/context tests passed**, including a 200-scene nontruncation/collapsed-default regression; production build and diff checks passed. Main Agent owns the actual browser geometry recheck. No provider call or browser interaction was performed by Front Agent.

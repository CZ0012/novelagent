"""Long-form planning and exact-version semantic review routes."""

from __future__ import annotations

from typing import Literal
import json
from contextlib import nullcontext

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from storygraph.core.agent_config import AgentPermissionLevel, ModelExecution, settings_for_task
from storygraph.core.errors import ContractError, GraphStoreError, ModelOutputError
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.generation_review import GenerationReviewTarget
from storygraph.models.proposal import ProposalArtifact, ProposalProvenance, ProposalRef
from storygraph.models.project import localized
from storygraph.models.temporal_state import TemporalStateCorrectionRequest, StateField
from storygraph.models.longform import (
    BlueprintRequest, ExpansionRequest, LongformApplyRequest, LongformRevisionRequest,
)
from storygraph.services.canon_snapshot import build_canon_snapshot, content_hash
from storygraph.services.canon_snapshot import canonical_json
from storygraph.services.expansion_output import expansion_volume_progress, recent_planned_scene_outcomes, prior_planned_scene_outcome_ledger
from storygraph.services.graph_query import GraphQueryService
from storygraph.services.project_style import resolve_project_style
from storygraph.services.project_language import resolve_project_output_language
from storygraph.services.natural_state_extraction import extract_natural_draft_state
from storygraph.services.semantic_review import SemanticReviewService, review_is_current
from storygraph.services.temporal_state import (
    propose_state_correction, resolve_temporal_state, temporal_state_history,
)
from storygraph.stores.generation_review_store import SQLiteGenerationReviewStore


class GenerationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: Literal["draft", "proposal"]
    target_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)
    scene_id: str | None = Field(default=None, min_length=1, max_length=200)


class NaturalStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)


def manual_longform_review_text(*, graph, store, project_id, proposal, plan):
    """Resolve manual expansion context without inventing parent approval/data."""
    from storygraph.services.longform_planning import _parent, _applied, _known_scenes, _blueprint_identity_maps, parse_longform, scene_plan_id, validate_expansion
    guard = getattr(graph, "persistence_guard", None)
    with guard() if callable(guard) else nullcontext(), store._lock:
        original = store.get(proposal.id, version=1)
        original_plan = parse_longform(original.body)
        if {(ref.kind, ref.ref) for ref in proposal.target_refs} != {("project", project_id)}:
            raise ContractError("Planning review requires an exact project target.")
        for key in ("phase", "project_id", "output_language", "graph_snapshot", "request", "parent_proposal_id", "parent_version"):
            if getattr(plan, key) != getattr(original_plan, key):
                raise ContractError("Planning review cannot replace frozen source scope.")
        if plan.phase == "blueprint":
            return proposal.body
        parent, parent_plan = _parent(store, project_id, plan.request)
        if not _applied(parent):
            raise ContractError("Manual expansion review requires its exact accepted and applied blueprint.")
        validate_expansion(plan.expansion, plan.request, parent_plan.blueprint, parent_plan.request)
        first_slot = scene_plan_id(plan.request.volume_index, plan.request.chapter_start, 1)
        prior = {key: node for key, node in _known_scenes(graph, project_id, parent.id).items() if key < first_slot}
        context = {"current_plan": json.loads(proposal.body),
            "parent_blueprint": parent_plan.blueprint.model_dump(),
            "parent_ref": {"id": parent.id, "version": parent.version, "body_sha256": content_hash(parent.body)},
            "volume_progress": expansion_volume_progress(parent_plan.request, plan.request),
            "author_brief": parent_plan.request.instruction,
            "recent_scene_outcomes": recent_planned_scene_outcomes(prior),
            "context_boundary": "The exact accepted/applied parent blueprint constrains this proposed expansion. Parent plans are not completed prose or evidence of later character knowledge; current graph canon remains authoritative."}
        if prior:
            context["prior_scene_outcome_ledger"] = prior_planned_scene_outcome_ledger(prior,
                identity_maps=_blueprint_identity_maps(parent.id, parent_plan.blueprint))
        return canonical_json(context)


def register_authoring_routes(
    app, *, graph, settings, proposal_store, draft_store, context_builder,
    require_permission, require_llm, provider_factory, persist_snapshot, persistent, review_service,
):
    # Imports here allow service modules to remain independently testable.
    from storygraph.services.longform_planning import (
        apply_longform, generate_blueprint, generate_expansion, LongformPlanError,
        parse_longform, revise_longform,
    )
    reports = SQLiteGenerationReviewStore(
        settings.workspace_dir / "generation_reviews.sqlite" if persistent else ":memory:"
    )
    app.state.generation_review_store = reports

    def resolve_target(project_id, request, *, current=False):
        purpose = "scene"
        project = graph.get_node(project_id)
        if project.type != "Project" or project.status != "CANON":
            raise KeyError(project_id)
        if request.target_type == "draft":
            draft = draft_store.get_draft(request.target_id)
            if draft.project_id != project_id or (
                request.scene_id is not None and draft.scene_id != request.scene_id
            ):
                raise KeyError(request.target_id)
            GraphQueryService(graph).scene_node(project_id=project_id, scene_id=draft.scene_id)
            if not current and draft.version != request.expected_version:
                raise ContractError("Draft changed; review its current version.")
            text, language, version, scene_id = (
                draft.text, draft.content_language, draft.version, draft.scene_id,
            )
        else:
            proposal = proposal_store.get(request.target_id)
            if proposal.project_id != project_id:
                raise KeyError(request.target_id)
            if not current and proposal.version != request.expected_version:
                raise ContractError("Proposal changed; review its current version.")
            scenes = {ref.ref for ref in proposal.target_refs if ref.kind == "scene"}
            if len(scenes) > 1:
                raise ContractError("Review requires an unambiguous scene target.")
            scene_id = next(iter(scenes), None)
            if request.scene_id is not None and request.scene_id != scene_id:
                raise ContractError("Review scene does not match the proposal target.")
            if scene_id:
                GraphQueryService(graph).scene_node(project_id=project_id, scene_id=scene_id)
            text, language, version = proposal.body, proposal.content_language, proposal.version
            if proposal.artifact_type == "outline_draft" and proposal.body_format == "structured_json":
                try:
                    payload = json.loads(proposal.body)
                except ValueError:
                    payload = {}
                if isinstance(payload, dict) and payload.get("schema") in {
                    "longform_branch_plan_v1", "longform_book_bundle_v1",
                }:
                    raise ContractError("Use the pinned planning-run review; a manifest is not the complete book plan.")
                if isinstance(payload, dict) and payload.get("schema") == "longform_plan_v1":
                    plan = parse_longform(proposal.body)
                    if plan.project_id != project_id or plan.output_language != language:
                        raise ContractError("Planning review scope does not match.")
                    text = manual_longform_review_text(graph=graph, store=proposal_store,
                        project_id=project_id, proposal=proposal, plan=plan)
                    purpose = "plan"
        if language is None or not text.strip():
            raise ContractError("Review requires nonempty text with a confirmed language.")
        return GenerationReviewTarget(
            project_id=project_id, target_type=request.target_type, target_id=request.target_id,
            target_version=version, text=text, output_language=language, scene_id=scene_id,
            purpose=purpose,
        )

    def review_inputs(target):
        canon = build_canon_snapshot(graph, project_id=target.project_id, scene_id=target.scene_id,
                                    target_text=target.text, purpose=target.purpose)
        style = resolve_project_style(graph, target.project_id)
        gaps = []
        if target.scene_id:
            pack = context_builder.build(project_id=target.project_id, scene_id=target.scene_id)
            style = pack.style_constraints.model_dump()
            gaps = [gap.kind + ":" + gap.ref for gap in pack.missing_context
                    if gap.severity in {"critical", "high"}]
        rubric = list(style.get("rubric", []))
        for key in ("pov", "tense", "tone", "sentence_rhythm", "diction", "dialogue_style"):
            if style.get(key):
                rubric.append(f"{key}: {style[key]}")
        runtime = settings_for_task(settings, "continuity")
        kwargs = {"style_rubric": rubric, "banned_phrases": style.get("banned_patterns", []),
                  "preset_text": runtime.agent_preset.system_prompt}
        if target.purpose == "plan":
            from storygraph.services.longform_planning import parse_longform, _parent
            proposal = proposal_store.get(target.target_id, version=target.target_version)
            plan = parse_longform(proposal.body)
            guard = getattr(graph, "persistence_guard", None)
            with guard() if callable(guard) else nullcontext(), proposal_store._lock:
                # Reuse exact original-request/parent validation; never parse authority from target prose.
                manual_longform_review_text(graph=graph, store=proposal_store,
                    project_id=target.project_id, proposal=proposal, plan=plan)
                kwargs["author_brief"] = (plan.request.instruction if plan.phase == "blueprint"
                    else _parent(proposal_store, target.project_id, plan.request)[1].request.instruction)
        return canon, kwargs, runtime, gaps

    def error_response(exc):
        if isinstance(exc, ModelOutputError) and str(exc) == "natural_state_provider_failed":
            return HTTPException(502, detail={"category": "provider_failed",
                                             "message": "The extraction model call failed; no automatic retry."})
        if isinstance(exc, (KeyError,)) or (
            isinstance(exc, GraphStoreError) and exc.category == "not_found"
        ):
            return HTTPException(404, detail="Requested project artifact is unavailable.")
        if isinstance(exc, GraphStoreError) and exc.category.startswith("longform_"):
            return HTTPException(409, detail={"category": exc.category,
                                             **({"reason_code": exc.reason_code} if isinstance(exc, LongformPlanError) else {}),
                                             "message": "Long-form input is invalid, unsupported or stale."})
        if isinstance(exc, (ContractError, GraphStoreError, ValueError)):
            return HTTPException(409, detail={"category": "authoring_invalid",
                                             "message": "Input is invalid, incomplete or stale."})
        # Providers may echo secrets or manuscript text; never expose arbitrary exception text.
        return HTTPException(502, detail={"category": "provider_failed",
                                         "message": "The model operation failed. No automatic retry."})

    @app.post("/projects/{project_id}/longform/blueprints")
    def blueprint(project_id: str, request: BlueprintRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        runtime = settings_for_task(settings, "planning")
        require_llm(runtime)
        try:
            return generate_blueprint(
                graph=graph, store=proposal_store, project_id=project_id, request=request,
                provider=provider_factory(runtime), model=runtime.llm_model,
                agent_preset=runtime.agent_preset,
            )
        except Exception as exc:
            raise error_response(exc) from None

    @app.post("/projects/{project_id}/longform/expansions")
    def expand(project_id: str, request: ExpansionRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        runtime = settings_for_task(settings, "planning")
        require_llm(runtime)
        try:
            return generate_expansion(
                graph=graph, store=proposal_store, project_id=project_id, request=request,
                provider=provider_factory(runtime), model=runtime.llm_model,
                agent_preset=runtime.agent_preset,
            )
        except Exception as exc:
            raise error_response(exc) from None

    @app.post("/projects/{project_id}/proposals/{proposal_id}/apply/longform")
    def apply(project_id: str, proposal_id: str, request: LongformApplyRequest):
        require_permission(AgentPermissionLevel.FULL)
        try:
            return apply_longform(
                graph=graph, store=proposal_store, project_id=project_id, proposal_id=proposal_id,
                request=request, persist_snapshot=persist_snapshot,
                before_apply=lambda: require_review(project_id, proposal_id, request.review_id),
            )
        except Exception as exc:
            raise error_response(exc) from None

    @app.post("/projects/{project_id}/proposals/{proposal_id}/revise-longform")
    def revise_plan(project_id: str, proposal_id: str, request: LongformRevisionRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        runtime = settings_for_task(settings, "planning")
        require_llm(runtime)
        try:
            return revise_longform(
                graph=graph, store=proposal_store, project_id=project_id, proposal_id=proposal_id,
                request=request, provider=provider_factory(runtime), model=runtime.llm_model,
                agent_preset=runtime.agent_preset,
            )
        except Exception as exc:
            raise error_response(exc) from None

    @app.get("/projects/{project_id}/style-profile")
    def style_profile(project_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return {"style_profile": resolve_project_style(graph, project_id)}
        except Exception as exc:
            raise error_response(exc) from None

    @app.get("/projects/{project_id}/temporal-state")
    def temporal_state(project_id: str, subject_id: str, scene_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return {"projection": resolve_temporal_state(
                graph, project_id=project_id, subject_id=subject_id,
                scene_id=scene_id, at_scene_start=True,
            ).model_dump(mode="json")}
        except Exception as exc:
            raise error_response(exc) from None

    @app.get("/projects/{project_id}/temporal-state/history")
    def temporal_history(project_id: str, subject_id: str, field: StateField | None = None):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            return temporal_state_history(graph, project_id=project_id, subject_id=subject_id,
                                          fields=[field] if field else None)
        except Exception as exc:
            raise error_response(exc) from None

    @app.post("/projects/{project_id}/temporal-state/corrections")
    def correct_temporal_state(project_id: str, request: TemporalStateCorrectionRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            candidate = propose_state_correction(graph=graph, draft_store=draft_store,
                                                project_id=project_id, request=request)
            submitted = review_service.submit([candidate])[0]
            return {"candidate": submitted.model_dump(mode="json")}
        except Exception as exc:
            raise error_response(exc) from None

    @app.post("/projects/{project_id}/scenes/{scene_id}/extract-natural-state")
    def extract_natural_state(project_id: str, scene_id: str, request: NaturalStateRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            target = resolve_target(project_id, GenerationReviewRequest(
                target_type="draft", target_id=request.draft_id,
                expected_version=request.expected_version, scene_id=scene_id,
            ))
            runtime = settings_for_task(settings, "extraction")
            require_llm(runtime)
            draft = draft_store.get_draft(target.target_id)
            if draft.text != target.text or draft.version != target.target_version:
                raise ContractError("Source Draft changed before extraction.")
            candidates = extract_natural_draft_state(
                graph=graph, project_id=project_id, source_draft=draft,
                provider=provider_factory(runtime), model=runtime.llm_model,
                output_language=resolve_project_output_language(graph, project_id),
            )
            current = draft_store.get_draft(target.target_id)
            if current.text != target.text or current.version != target.target_version:
                raise ContractError("Source Draft changed during extraction.")
            now = utc_now()
            proposal = proposal_store.create(ProposalArtifact(
                id=new_id("proposal"), project_id=project_id,
                content_language=target.output_language, artifact_type="fact_draft",
                status="agent_revised", body_format="structured_json",
                title=localized(target.output_language, zh="正文状态变化待审提案",
                                en="Prose state changes for review"),
                body=json.dumps({"source_draft_id": draft.id, "candidate_previews": [
                    candidate.model_dump(mode="json") for candidate in candidates
                ]}, ensure_ascii=False, indent=2),
                source_refs=[ProposalRef(kind="draft", ref=draft.id, source_span={
                    "version": draft.version, "text_sha256": content_hash(draft.text),
                })],
                target_refs=[ProposalRef(kind="scene", ref=scene_id)],
                provenance=ProposalProvenance(created_by="agent", created_via="llm",
                    model_ref=runtime.llm_model, model_execution=runtime.model_execution),
                version=1, created_at=now, updated_at=now,
            ))
            return {"proposal": proposal.model_dump(), "candidate_previews": [
                candidate.model_dump() for candidate in candidates
            ], "candidates": [], "model_execution": runtime.model_execution}
        except HTTPException:
            raise
        except Exception as exc:
            raise error_response(exc) from None

    def report_current(report):
        try:
            target = resolve_target(report.project_id, GenerationReviewRequest(
                target_type=report.target_type, target_id=report.target_id,
                expected_version=report.target_version,
            ), current=True)
            canon, style, _, gaps = review_inputs(target)
            return not gaps and review_is_current(report, target=target, canon=canon, **style)
        except (KeyError, ValueError, ContractError, GraphStoreError):
            return False

    def require_review(project_id, proposal_id, report_id):
        try:
            report = reports.get(project_id=project_id, report_id=report_id)
        except KeyError:
            raise ContractError("A current passing semantic review is required before adoption.") from None
        if (report.target_type != "proposal" or report.target_id != proposal_id
                or report.status != "pass" or not report_current(report)):
            raise ContractError("Semantic review is stale, incomplete or requires revision.")

    app.state.require_generation_review = require_review

    @app.post("/projects/{project_id}/generation-reviews")
    def review_generation(project_id: str, request: GenerationReviewRequest):
        require_permission(AgentPermissionLevel.READ_GENERATE)
        try:
            target = resolve_target(project_id, request)
            canon, style, runtime, gaps = review_inputs(target)
            require_llm(runtime)
            report = SemanticReviewService(
                provider_factory(runtime), runtime.llm_model,
                model_execution=ModelExecution.model_validate(runtime.model_execution),
            ).review(target=target, canon=canon, missing_context=gaps, **style)
            reports.save(report)
            return {"report": report.model_dump(mode="json"), "current": report_current(report)}
        except HTTPException:
            raise
        except Exception as exc:
            raise error_response(exc) from None

    @app.get("/projects/{project_id}/generation-reviews")
    def list_reviews(project_id: str, target_type: Literal["draft", "proposal"], target_id: str):
        require_permission(AgentPermissionLevel.READ_ONLY)
        try:
            resolve_target(project_id, GenerationReviewRequest(
                target_type=target_type, target_id=target_id, expected_version=1,
            ), current=True)
            return {"reports": [
                {"report": report.model_dump(mode="json"), "current": report_current(report)}
                for report in reports.list(project_id=project_id, target_type=target_type,
                                           target_id=target_id)
            ]}
        except Exception as exc:
            raise error_response(exc) from None

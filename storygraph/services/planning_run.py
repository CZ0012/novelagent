"""Sequential, bounded, resumable whole-book planning outside canon."""

from dataclasses import dataclass
import json
import os
from threading import Lock
from types import SimpleNamespace

from storygraph.core.errors import GraphStoreError
from storygraph.core.agent_config import ModelExecution
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.models.generation_review import GenerationReviewTarget
from storygraph.models.longform import Blueprint, BlueprintRequest, Expansion, ExpansionRequest, TargetedRevisionOutput
from storygraph.models.planning_run import BranchPlan, BookBundle, PlanningCall, PlanningRef, PlanningRun, PlanningStep
from storygraph.models.proposal import ProposalArtifact, ProposalProvenance, ProposalRef
from storygraph.models.project import localized
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.longform_planning import (
    _apply_targeted_changes, _call, _local, _project, _snapshot, _targeted_paths, _texts,
    _validate_clue_completion, parse_longform, scene_plan_id, split_budget, validate_blueprint, validate_expansion,
)
from storygraph.services.project_language import resolve_project_output_language, validate_generated_output_language
from storygraph.services.semantic_review import SemanticReviewService, review_is_current


@dataclass
class PlanningExecution:
    provider: object
    model: str
    agent_preset: object = None
    model_execution: object = None
    configuration_fingerprint: str | None = None


_ACTIVE_RUNS = set()
_ACTIVE_LOCK = Lock()


def _pid_alive(pid):
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() == 5  # Access denied is not proof of death.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _error(category="planning_run_invalid"):
    return GraphStoreError(category, "Planning cannot proceed; inspect the saved run and explicitly resume when resolved.")


def proposal_ref(proposal):
    return PlanningRef(id=proposal.id, version=proposal.version, body_sha256=content_hash(proposal.body))


def load_ref(proposals, ref, *, current=True):
    value = proposals.get(ref.id, version=ref.version)
    if content_hash(value.body) != ref.body_sha256 or current and proposals.get(ref.id).version != ref.version:
        raise _error("planning_source_changed")
    return value


def branch_from_ref(proposals, ref, *, current=True):
    proposal = load_ref(proposals, ref, current=current)
    branch = BranchPlan.model_validate_json(proposal.body)
    if proposal.project_id != branch.project_id or proposal.content_language != branch.output_language or proposal.artifact_type != "outline_draft" or proposal.body_format != "structured_json":
        raise _error()
    return branch


def branch_scenes(branches):
    return {scene.id: SimpleNamespace(properties={**scene.model_dump(), "longform_scene_id": scene.id})
            for branch in branches if branch.expansion for chapter in branch.expansion.chapters for scene in chapter.scenes}


def book_projection(proposals, run, *, current=True):
    branches = [branch_from_ref(proposals, step.proposal_ref, current=current) for step in run.steps]
    # Every field is checked in its per-step review. This final pass compares
    # the exact blueprint and all scene summaries/outcomes/dependencies/clues;
    # it does not falsely claim all full scene fields fit in one model context.
    return {"review_scope": "whole_book_blueprint_and_scene_outcome_ledger", "run_id": run.id,
        "exact_refs": [step.proposal_ref.model_dump() for step in run.steps],
        "blueprint": branches[0].blueprint.model_dump(),
        "volumes": [{"volume_index": b.expansion.volume_index, "chapters": [{
            "index": c.index, "title": c.title, "summary": c.summary,
            "scenes": [{key: getattr(s, key) for key in ("id", "summary", "outcome", "pov_character_id", "location_id", "causal_dependencies", "foreshadowing_seed_ids", "foreshadowing_payoff_ids")}
                       for s in c.scenes]} for c in b.expansion.chapters]} for b in branches[1:]]}


class PlanningRunService:
    def __init__(self, *, graph, proposals, runs, provider_factory, snapshot_fn=None):
        self.graph, self.proposals, self.runs = graph, proposals, runs
        self.provider_factory = provider_factory
        self.snapshot_fn = snapshot_fn or (lambda graph, project_id: _snapshot(graph, project_id))
        self._active = _ACTIVE_RUNS
        self._active_lock = _ACTIVE_LOCK
        self._worker_tokens = {}

    def get(self, project_id, run_id):
        run = self.runs.get(run_id)
        if run.project_id != project_id:
            raise _error("not_found")
        return run

    def list(self, project_id):
        _project(self.graph, project_id)
        return self.runs.list(project_id)

    def create(self, project_id, request):
        graph = _local(self.graph)
        with graph.persistence_guard():
            _project(graph, project_id)
            canon = self.snapshot_fn(graph, project_id)
            if set(canon.missing_context) - {"insufficient_story_canon"}:
                raise _error("planning_context_incomplete")
            language = resolve_project_output_language(graph, project_id)
        steps = [PlanningStep(index=0, phase="blueprint")]
        for volume in range(1, request.volume_count+1):
            for start in range(1, request.chapters_per_volume+1, request.batch_size):
                steps.append(PlanningStep(index=len(steps), phase="expansion", volume_index=volume,
                    chapter_start=start, chapter_count=min(request.batch_size, request.chapters_per_volume-start+1)))
        now = utc_now()
        run = PlanningRun(id=new_id("planning"), project_id=project_id, version=1,
            request=request, output_language=language, canon_fingerprint=canon.fingerprint,
            max_calls=request.max_calls, steps=steps, created_at=now, updated_at=now)
        if request.seed_blueprint_id is None:
            return self.runs.create(run)
        with graph.persistence_guard(), self.runs._lock:
            source = self.proposals.get(request.seed_blueprint_id)
            if (source.project_id != project_id or source.version != request.seed_blueprint_version
                    or source.artifact_type != "outline_draft" or source.body_format != "structured_json"
                    or source.content_language != language or source.derived_refs
                    or {(r.kind, r.ref) for r in source.target_refs} != {("project", project_id)}
                    or any(e.source_ref.startswith(f"proposal:{source.id}:longform:") for e in graph.event_log.list())):
                raise _error("planning_seed_invalid")
            plan = parse_longform(source.body)
            config = self._configuration(run)
            if plan.phase != "blueprint" or plan.project_id != project_id or plan.output_language != language or plan.request != config:
                raise _error("planning_seed_invalid")
            validate_blueprint(plan.blueprint, config)
            execution = PlanningExecution(None, source.provenance.model_ref or "", model_execution=source.provenance.model_execution)
            proposal = self._new_proposal(run, steps[0], plan.blueprint, execution, repair_source=source)
            proposal = proposal.model_copy(update={"provenance": ProposalProvenance(created_by="agent", created_via="workflow",
                model_ref=source.provenance.model_ref, model_execution=source.provenance.model_execution,
                note=localized(language, zh="从精确已有蓝图复制为未审规划分支；未调用模型。", en="Copied an exact existing blueprint into an unreviewed branch; no model call."))})
            steps[0] = steps[0].model_copy(update={"status": "generated", "proposal_ref": proposal_ref(proposal)})
            run = run.model_copy(update={"steps": steps, "seed_blueprint_ref": proposal_ref(source)})
            if self.snapshot_fn(graph, project_id).fingerprint != run.canon_fingerprint:
                raise _error("planning_seed_invalid")
            return self.runs.create(run, proposal=proposal)

    def stop(self, project_id, run_id, request):
        with self.runs._lock:
            run = self.get(project_id, run_id)
            if run.version != request.expected_version or run.status in {"completed", "awaiting_review"}:
                raise _error("planning_run_stale")
            status = "running" if run.status == "running" and run.pending_call else "paused"
            return self.runs.update(run.model_copy(update={"stop_requested": True, "status": status,
                "pause_reason": "stopped"}), run.version)

    def resume(self, project_id, run_id, request):
        with self.runs._lock:
            run = self.get(project_id, run_id)
            if run.version != request.expected_version or run.status not in ({"paused", "awaiting_review"} if request.restart_from_step is not None else {"paused"}):
                raise _error("planning_run_stale")
            if run.pending_call and not request.retry_uncertain_call:
                raise _error("planning_uncertain_retry_required")
            if request.max_calls is not None and request.max_calls < run.calls_reserved:
                raise _error()
            steps = [step.model_copy(deep=True) for step in run.steps]
            restart_history = list(run.restart_history)
            final_review_id = None if run.pause_reason == "review_failed" and run.stage == "book_review" else run.final_review_id
            bundle_id = run.bundle_proposal_id
            stage = run.stage
            if request.restart_from_step is not None:
                index = request.restart_from_step
                if index >= len(steps):
                    raise _error()
                if bundle_id:
                    bundle = self.proposals.get(bundle_id)
                    if bundle.status == "accepted" or bundle.derived_refs:
                        raise _error("planning_bundle_already_reviewed")
                selected = steps[index]
                restart_history.append({"step_index": index, "source_ref": selected.proposal_ref.model_dump() if selected.proposal_ref else None,
                    "prior_repairs": selected.repairs, "instruction_sha256": content_hash(request.revision_instruction or ""), "created_at": utc_now()})
                if request.revision_instruction and selected.proposal_ref:
                    load_ref(self.proposals, selected.proposal_ref)
                    steps[index] = selected.model_copy(update={"status": "needs_revision", "repairs": 0,
                        "revision_instruction": request.revision_instruction})
                else:
                    steps[index] = selected.model_copy(update={"status": "pending", "proposal_ref": None, "review_id": None,
                        "repairs": 0, "revision_instruction": request.revision_instruction})
                for later in range(index+1, len(steps)):
                    steps[later] = steps[later].model_copy(update={"status": "pending", "proposal_ref": None,
                        "review_id": None, "repairs": 0, "revision_instruction": None})
                final_review_id, bundle_id, stage = None, None, selected.phase
            if run.pause_reason == "review_failed" and request.restart_from_step is None:
                for step in steps:
                    if step.status == "needs_revision" and step.review_id:
                        report = self.runs.report(run.id, step.review_id)
                        if report.status == "inconclusive" or not report.issues:
                            step.status = "generated"
            return self.runs.update(run.model_copy(update={"status": "queued", "stop_requested": False,
                "pause_reason": None, "pending_call": None,
                "steps": steps, "final_review_id": final_review_id, "bundle_proposal_id": bundle_id,
                "stage": stage, "restart_history": restart_history,
                "max_calls": request.max_calls if request.max_calls is not None else run.max_calls}), run.version)

    def recover_interrupted(self):
        recovered = []
        with self.runs._lock:
            for run in self.runs.all():
                if run.status == "running":
                    if run.id in self._active or run.owner_pid and run.owner_pid != os.getpid() and _pid_alive(run.owner_pid):
                        continue
                    recovered.append(self.runs.update(run.model_copy(update={"status": "paused",
                        "pause_reason": "uncertain_call" if run.pending_call else "execution_failed"}), run.version))
        return recovered

    def _pause(self, run_id, reason, *, uncertain=False):
        with self.runs._lock:
            run = self.runs.get(run_id)
            token = self._worker_tokens.get(run_id)
            if token is not None and run.worker_token != token:
                return run
            try:
                return self.runs.update(run.model_copy(update={"status": "paused", "pause_reason": reason,
                    "pending_call": run.pending_call if uncertain else None}), run.version)
            except GraphStoreError as exc:
                if exc.category == "planning_run_stale":
                    return self.runs.get(run_id)
                raise

    def _check(self, run):
        if run.status != "running" or run.worker_token != self._worker_tokens.get(run.id):
            return run
        if run.stop_requested:
            return self._pause(run.id, "stopped")
        canon = self.snapshot_fn(self.graph, run.project_id)
        if canon.fingerprint != run.canon_fingerprint or resolve_project_output_language(self.graph, run.project_id) != run.output_language:
            return self._pause(run.id, "canon_changed")
        for step in run.steps:
            if step.proposal_ref:
                load_ref(self.proposals, step.proposal_ref)
        if run.seed_blueprint_ref:
            load_ref(self.proposals, run.seed_blueprint_ref)
        return None

    def _execution(self, run, task):
        execution = self.provider_factory(task)
        if execution.model_execution is not None and not isinstance(execution.model_execution, ModelExecution):
            execution.model_execution = ModelExecution.model_validate(execution.model_execution)
        metadata = execution.model_execution or {}
        if hasattr(metadata, "model_dump"):
            metadata = metadata.model_dump(mode="json")
        fingerprint = execution.configuration_fingerprint or content_hash(canonical_json({
            "model": execution.model, "execution": metadata,
            "endpoint": str(getattr(execution.provider, "base_url", "")),
            "preset": getattr(execution.agent_preset, "system_prompt", ""),
        }))
        if task in run.execution_fingerprints and run.execution_fingerprints[task] != fingerprint:
            raise _error("planning_connection_changed")
        return execution, fingerprint

    def _reserve(self, run, task, operation, step_index):
        # Provider construction is read-only; no key or endpoint is persisted.
        execution, fingerprint = self._execution(run, task)
        with self.runs._lock:
            current = self.runs.get(run.id)
            if current.status != "running" or current.worker_token != self._worker_tokens.get(run.id) or current.pending_call is not None:
                raise _error("planning_run_not_owner")
            if current.stop_requested:
                return self._pause(run.id, "stopped"), None
            if current.calls_reserved >= current.max_calls:
                return self._pause(run.id, "call_budget"), None
            call = PlanningCall(id=new_id("call"), task=task, operation=operation, step_index=step_index)
            steps = [step.model_copy(deep=True) for step in current.steps]
            if operation == "repair":
                steps[step_index].repairs += 1
            current = self.runs.update(current.model_copy(update={"pending_call": call,
                "calls_reserved": current.calls_reserved+1,
                "steps": steps,
                "execution_fingerprints": {**current.execution_fingerprints, task: fingerprint}}), current.version)
            return current, execution

    def _configuration(self, run):
        return BlueprintRequest.model_validate({key: getattr(run.request, key) for key in BlueprintRequest.model_fields})

    def _branches(self, run, before_index):
        return [branch_from_ref(self.proposals, s.proposal_ref) for s in run.steps[:before_index] if s.proposal_ref]

    def _payload(self, run, step):
        config = self._configuration(run)
        canon = self.snapshot_fn(self.graph, run.project_id)
        payload = {"phase": step.phase, "canon": canon.model_dump(mode="json"),
                   "context_boundary": "canon is authoritative. proposed_planning_context contains unaccepted plans, NOT canon facts or human decisions."}
        if step.revision_instruction:
            payload["author_restart_instruction"] = step.revision_instruction
        if step.phase == "blueprint":
            payload.update(request=config.model_dump(), volume_budgets=split_budget(config.target_length, config.volume_count))
            return payload, Blueprint
        prior = self._branches(run, step.index)
        blueprint = prior[0].blueprint
        request = self._expansion_request(run, step)
        budgets = split_budget(blueprint.volumes[step.volume_index-1].target_length, config.chapters_per_volume)
        previous = branch_scenes(prior)
        payload.update(request=request.model_dump(), blueprint=blueprint.model_dump(),
            proposed_planning_context={"exact_refs": [s.proposal_ref.model_dump() for s in run.steps[:step.index]],
                "recent_scene_outcomes": [{"id": key, "summary": value.properties["summary"], "outcome": value.properties["outcome"]}
                    for key, value in sorted(previous.items())[-12:]]},
            prior_clue_placements=[{"scene_id": key, "seed_ids": value.properties["foreshadowing_seed_ids"],
                "payoff_ids": value.properties["foreshadowing_payoff_ids"]} for key, value in sorted(previous.items())
                if value.properties["foreshadowing_seed_ids"] or value.properties["foreshadowing_payoff_ids"]],
            chapter_budgets=[{"index": c, "target_length": budgets[c-1], "scenes": [
                {"id": scene_plan_id(step.volume_index, c, s), "target_length": budget}
                for s, budget in enumerate(split_budget(budgets[c-1], config.scenes_per_chapter), 1)]}
                for c in range(step.chapter_start, step.chapter_start+step.chapter_count)])
        return payload, Expansion

    def _expansion_request(self, run, step):
        ref = run.steps[0].proposal_ref
        return ExpansionRequest(parent_proposal_id=ref.id, parent_version=ref.version,
            volume_index=step.volume_index, chapter_start=step.chapter_start, chapter_count=step.chapter_count)

    def _validate(self, run, step, authored):
        config = self._configuration(run)
        if step.phase == "blueprint":
            validate_blueprint(authored, config)
        else:
            prior = self._branches(run, step.index)
            blueprint = prior[0].blueprint
            validate_expansion(authored, self._expansion_request(run, step), blueprint, config)
            _validate_clue_completion(authored, blueprint, config, branch_scenes(prior))
        validate_generated_output_language(output_language=run.output_language, fields=_texts(authored.model_dump()))

    def _new_proposal(self, run, step, authored, execution, *, repair_source=None):
        self._validate(run, step, authored)
        branch = BranchPlan(schema="longform_branch_plan_v1", run_id=run.id, project_id=run.project_id,
            output_language=run.output_language, canon_fingerprint=run.canon_fingerprint, step_index=step.index,
            phase=step.phase, blueprint_ref=run.steps[0].proposal_ref if step.index else None,
            previous_refs=[s.proposal_ref for s in run.steps[:step.index]],
            blueprint=authored if step.phase == "blueprint" else None,
            expansion=authored if step.phase == "expansion" else None)
        now = utc_now()
        refs = [ProposalRef(kind="planning_run", ref=run.id)]
        refs += [ProposalRef(kind="proposal_artifact", ref=r.id, source_span={"version": r.version, "sha256": r.body_sha256}) for r in branch.previous_refs]
        if repair_source:
            refs.append(ProposalRef(kind="proposal_artifact", ref=repair_source.id, source_span={"version": repair_source.version}))
        metadata = execution.model_execution
        return ProposalArtifact(id=new_id("proposal"), project_id=run.project_id, content_language=run.output_language,
            artifact_type="outline_draft", status="agent_revised", title=localized(run.output_language,
                zh="整书规划蓝图" if step.phase == "blueprint" else f"第{step.volume_index}卷章节规划",
                en="Whole-book blueprint" if step.phase == "blueprint" else f"Volume {step.volume_index} chapter plan"),
            body=json.dumps(branch.model_dump(by_alias=True), ensure_ascii=False, indent=2), body_format="structured_json",
            target_refs=[ProposalRef(kind="project", ref=run.project_id)], source_refs=refs,
            provenance=ProposalProvenance(created_by="agent", created_via="llm", model_ref=execution.model,
                model_execution=metadata), version=1, created_at=now, updated_at=now)

    def _store_output(self, run, step, proposal):
        with self.runs._lock:
            current = self.runs.get(run.id)
            self._require_call_owner(current, run.pending_call)
            steps = [s.model_copy(deep=True) for s in current.steps]
            steps[step.index] = step.model_copy(update={"status": "generated", "proposal_ref": proposal_ref(proposal), "review_id": None})
            return self.runs.update(current.model_copy(update={"steps": steps, "pending_call": None}), current.version, proposal=proposal)

    def _require_call_owner(self, current, call):
        if (current.status != "running" or current.worker_token != self._worker_tokens.get(current.id)
                or current.pending_call is None or call is None or current.pending_call.id != call.id):
            raise _error("planning_run_not_owner")

    def _review_target(self, run, step=None):
        if step is None:
            text = canonical_json(book_projection(self.proposals, run))
            target_id, version = "book_review_"+run.id, 1
        else:
            proposal = load_ref(self.proposals, step.proposal_ref)
            text = canonical_json({"current_plan": json.loads(proposal.body),
                "proposed_planning_context": self._payload(run, step)[0].get("proposed_planning_context", {}),
                "blueprint": self._branches(run, step.index)[0].blueprint.model_dump() if step.index else None,
                "context_boundary": "Proposed branch plans are not canon; review internal consistency and compatibility with the separate canon evidence."})
            target_id, version = proposal.id, proposal.version
        if len(text) > 100000:
            raise _error("planning_context_budget")
        return GenerationReviewTarget(project_id=run.project_id, target_type="proposal", target_id=target_id,
            target_version=version, text=text, output_language=run.output_language, purpose="plan")

    def _review_inputs(self, run):
        canon = self.snapshot_fn(self.graph, run.project_id)
        gaps = tuple(g for g in canon.missing_context if g != "insufficient_story_canon")
        canon = canon.model_copy(update={"scope": "plan", "missing_context": gaps, "complete": not gaps})
        blueprint = branch_from_ref(self.proposals, run.steps[0].proposal_ref).blueprint
        style = blueprint.style_brief
        return canon, {"style_rubric": style.rubric, "banned_phrases": style.banned_patterns}

    def review(self, project_id, run_id, review_id):
        run = self.get(project_id, run_id)
        report = self.runs.report(run_id, review_id)
        step = next((s for s in run.steps if s.review_id == review_id), None)
        if step is None and run.final_review_id != review_id:
            raise _error("not_found")
        try:
            if run.seed_blueprint_ref is not None:
                load_ref(self.proposals, run.seed_blueprint_ref)
            target = self._review_target(run, step)
            canon, style = self._review_inputs(run)
            current = review_is_current(report, target=target, canon=canon, **style)
        except Exception:
            current = False
        return {"report": report.model_dump(mode="json"), "current": current}

    def execute(self, run_id):
        with self._active_lock:
            if run_id in self._active:
                return self.runs.get(run_id)
            self._active.add(run_id)
        try:
            with self.runs._lock:
                run = self.runs.get(run_id)
                if run.status != "queued":
                    return run
                token = new_id("worker")
                self._worker_tokens[run_id] = token
                run = self.runs.update(run.model_copy(update={"status": "running", "pause_reason": None,
                    "owner_pid": os.getpid(), "worker_token": token}), run.version)
            while True:
                run = self.runs.get(run_id)
                paused = self._check(run)
                if paused:
                    return paused
                step = next((s for s in run.steps if s.status != "passed"), None)
                if step is None:
                    return self._finish_book(run)
                run = self.runs.update(run.model_copy(update={"stage": step.phase}), run.version)
                if step.status == "pending":
                    payload, output_type = self._payload(run, step)
                    reserved, execution = self._reserve(run, "planning", "generate", step.index)
                    if execution is None:
                        return reserved
                    authored = _call(execution.provider, execution.model, run.output_language, output_type, payload, execution.agent_preset)
                    self._store_output(reserved, step, self._new_proposal(reserved, step, authored, execution))
                elif step.status == "generated":
                    target = self._review_target(run, step)
                    canon, style = self._review_inputs(run)
                    reserved, execution = self._reserve(run, "continuity", "review", step.index)
                    if execution is None:
                        return reserved
                    report = SemanticReviewService(execution.provider, execution.model,
                        model_execution=execution.model_execution).review(target=target, canon=canon, **style)
                    with self.runs._lock:
                        current = self.runs.get(run_id)
                        self._require_call_owner(current, reserved.pending_call)
                        steps = [s.model_copy(deep=True) for s in current.steps]
                        steps[step.index] = step.model_copy(update={"status": "passed" if report.status == "pass" else "needs_revision", "review_id": report.id})
                        run = self.runs.update(current.model_copy(update={"steps": steps, "pending_call": None}), current.version, report=report)
                    if report.status not in {"pass", "needs_revision", "blocked"} or not report.issues and report.status != "pass":
                        return self._pause(run_id, "review_failed")
                else:
                    if step.repairs >= run.request.max_repairs_per_step:
                        return self._pause(run_id, "repair_limit")
                    source = load_ref(self.proposals, step.proposal_ref)
                    branch = BranchPlan.model_validate_json(source.body)
                    authored = branch.blueprint or branch.expansion
                    report = self.runs.report(run.id, step.review_id) if step.review_id else None
                    payload, output_type = self._payload(run, step)
                    values = _targeted_paths(authored.model_dump(), step.phase)
                    payload.update(revision_mode="targeted", source_plan=authored.model_dump(), source_schema=output_type.model_json_schema(),
                        current_values=values, allowed_paths=sorted(values), revision_instruction=canonical_json({
                            "author_instruction": step.revision_instruction,
                            "issues": [i.model_dump() for i in report.issues] if report else []}))
                    reserved, execution = self._reserve(run, "planning", "repair", step.index)
                    if execution is None:
                        return reserved
                    changes = _call(execution.provider, execution.model, run.output_language, TargetedRevisionOutput, payload, execution.agent_preset)
                    revised = _apply_targeted_changes(authored, step.phase, changes)
                    updated_step = step.model_copy(update={"repairs": step.repairs+1})
                    self._store_output(reserved, updated_step, self._new_proposal(reserved, step, revised, execution, repair_source=source))
        except Exception as exc:
            run = self.runs.get(run_id)
            category = getattr(exc, "category", "")
            if category in {"planning_run_stale", "planning_run_not_owner"}:
                return run
            reason = {"planning_source_changed": "source_changed", "planning_connection_changed": "connection_changed",
                      "planning_context_budget": "context_budget"}.get(category)
            if reason:
                return self._pause(run_id, reason)
            if isinstance(exc, (GraphStoreError, ValueError)):
                return self._pause(run_id, "schema_invalid")
            return self._pause(run_id, "uncertain_call" if run.pending_call else "execution_failed", uncertain=bool(run.pending_call))
        finally:
            with self._active_lock:
                self._active.discard(run_id)
                self._worker_tokens.pop(run_id, None)

    def _finish_book(self, run):
        if run.final_review_id is None:
            target = self._review_target(run)
            canon, style = self._review_inputs(run)
            run = self.runs.update(run.model_copy(update={"stage": "book_review"}), run.version)
            reserved, execution = self._reserve(run, "continuity", "book_review", -1)
            if execution is None:
                return reserved
            report = SemanticReviewService(execution.provider, execution.model,
                model_execution=execution.model_execution).review(target=target, canon=canon, **style)
            with self.runs._lock:
                current = self.runs.get(run.id)
                self._require_call_owner(current, reserved.pending_call)
                run = self.runs.update(current.model_copy(update={"final_review_id": report.id, "pending_call": None}), current.version, report=report)
            if report.status != "pass":
                return self._pause(run.id, "review_failed")
        elif self.runs.report(run.id, run.final_review_id).status != "pass":
            return self._pause(run.id, "review_failed")
        paused = self._check(run)
        if paused:
            return paused
        bundle = BookBundle(schema="longform_book_bundle_v1", run_id=run.id, project_id=run.project_id,
            output_language=run.output_language, canon_fingerprint=run.canon_fingerprint,
            blueprint_ref=run.steps[0].proposal_ref, expansion_refs=[s.proposal_ref for s in run.steps[1:]], final_review_id=run.final_review_id)
        now = utc_now()
        proposal = ProposalArtifact(id=new_id("proposal"), project_id=run.project_id, content_language=run.output_language,
            artifact_type="outline_draft", status="agent_revised", title=localized(run.output_language,
                zh="整书框架审阅清单", en="Whole-book framework review manifest"), body_format="structured_json",
            body=json.dumps(bundle.model_dump(by_alias=True), ensure_ascii=False, indent=2), target_refs=[ProposalRef(kind="project", ref=run.project_id)],
            source_refs=[ProposalRef(kind="planning_run", ref=run.id)],
            provenance=ProposalProvenance(created_by="agent", created_via="workflow", note=localized(run.output_language,
                zh="规划清单固定全部提案版本；尚未写入正典。", en="The manifest pins every plan version; canon is unchanged.")),
            version=1, created_at=now, updated_at=now)
        with self.runs._lock:
            current = self.runs.get(run.id)
            if current.worker_token != self._worker_tokens.get(run.id) or current.status != "running":
                raise _error("planning_run_not_owner")
            if current.stop_requested:
                return self._pause(run.id, "stopped")
            return self.runs.update(current.model_copy(update={"bundle_proposal_id": proposal.id,
                "status": "awaiting_review", "stage": "done"}), current.version, proposal=proposal)

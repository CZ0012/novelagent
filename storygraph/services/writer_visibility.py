"""Deterministic prose-only projection; author truth never becomes a default input."""

import math
import re

from storygraph.core.errors import ContractError
from storygraph.models.writer_visibility import ProseInputGrants, ResolvedWriterVisibility
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.text_span import utf16_span


def _error(code):
    raise ContractError("writer_visibility_" + code)


def writer_source_context_sha256(pack):
    value = pack.model_dump(
        mode="json", exclude={"writer_visibility", "writer_visibility_required"}
    )
    value.get("provenance", {}).pop("built_at", None)
    value.get("budget", {}).pop("estimated_tokens", None)
    value.get("budget", {}).pop("dropped_items", None)
    value["missing_context"] = [
        g
        for g in value.get("missing_context", [])
        if not g["kind"].startswith("writer_visibility_")
    ]
    return content_hash(canonical_json(value))


def validate_reader_presented(project_id, refs, reader_source_resolver):
    if refs and not callable(reader_source_resolver):
        _error("reader_source_unavailable")
    for ref in refs:
        try:
            draft = reader_source_resolver(ref.draft_id)
            if (
                draft.project_id != project_id
                or draft.version != ref.version
                or content_hash(draft.text) != ref.text_sha256
            ):
                _error("reader_source_stale")
            utf16_span(draft.text, ref.start, ref.end, ref.expected_text)
        except ContractError:
            raise
        except Exception:
            _error("reader_source_invalid")


def resolve_writer_visibility(
    pack, record, *, reader_source_resolver=None, character_scope_resolver=None
):
    if record is None or record.spec is None:
        _error("missing_policy")
    if record.project_id != pack.project_id or record.scene_id not in {None, pack.scene_id}:
        _error("scope_mismatch")
    source_hash = writer_source_context_sha256(pack)
    if record.scene_id is not None and record.source_context_sha256 != source_hash:
        _error("source_stale")
    if record.scene_id is None and record.source_context_sha256 is not None:
        _error("invalid_project_template")
    spec = record.spec
    if spec.writer_style_origin == "profile_projection" and (
        spec.writer_style_source_profile_id != pack.style_constraints.profile_id
        or spec.writer_style_source_profile_sha256 != pack.style_constraints.profile_sha256
    ):
        _error("style_source_stale")
    if spec.writer_style_origin == "profile_projection":
        actual_style = pack.style_constraints.model_dump(mode="json")
        for key, value in spec.writer_style.model_dump(mode="json").items():
            # Empty optional capsule fields select no source text.
            if value not in (None, "", []) and value != actual_style.get(key):
                _error("style_projection_mismatch")
    validate_reader_presented(pack.project_id, spec.reader_presented, reader_source_resolver)
    resolved = ResolvedWriterVisibility(
        record=record,
        project_id=pack.project_id,
        scene_id=pack.scene_id,
        source_context_sha256=source_hash,
        policy_fingerprint=content_hash(
            canonical_json(
                {"record": record.model_dump(mode="json"), "source_context_sha256": source_hash}
            )
        ),
        reader_sources_verified=True,
        reader_source_resolver=reader_source_resolver,
        character_scope_resolver=character_scope_resolver,
    )
    _isolated_view(pack, resolved)
    if len(_review_payload(pack, resolved)) > 120000:
        _error("review_metadata_budget_exceeded")
    return resolved


def _internal_identifiers(pack):
    ids = {
        pack.project_id,
        pack.scene_id,
        pack.chapter_id,
        pack.pov_character_id,
        pack.location_id,
        *pack.required_characters,
    }
    ids.update(e.get("id", "") for e in pack.canon_entities)
    if pack.style_constraints.profile_id:
        ids.add(pack.style_constraints.profile_id)
    for field in ("graph_query_ids", "draft_refs", "style_sample_refs", "author_instruction_refs"):
        ids.update(getattr(pack.provenance, field))
    for boundary in pack.knowledge_boundaries:
        ids.add(boundary.character_id)
        for field in (
            "knows",
            "does_not_know",
            "falsely_believes",
            "suspects",
            "hides",
            "source_refs",
        ):
            ids.update(getattr(boundary, field))
    if pack.scene_plan:
        for cause in pack.scene_plan.causal_preconditions:
            ids.update((cause.scene_id, cause.relation_id))
        for action in pack.scene_plan.foreshadowing_actions:
            ids.update((action.id, action.relation_id, *action.seed_scene_ids))
    return {ref for ref in ids if isinstance(ref, str) and len(ref) >= 8}


def _isolated_view(pack, resolved):
    spec = resolved.record.spec
    if spec is None:
        _error("missing_policy")
    current_characters = {pack.pov_character_id, *pack.required_characters}
    characters = {e["id"] for e in pack.canon_entities if e.get("type") == "Character"}
    handles, cast = {}, []
    for character in spec.characters:
        offstage = character.character_id not in current_characters
        if offstage and character.allow_offstage_name:
            if not callable(resolved.character_scope_resolver):
                _error("offstage_source_unavailable")
            try:
                node = resolved.character_scope_resolver(character.character_id)
                if (
                    node.type != "Character"
                    or node.status != "CANON"
                    or node.properties.get("project_id") != pack.project_id
                ):
                    _error("character_scope_invalid")
            except ContractError:
                raise
            except Exception:
                _error("character_scope_invalid")
        elif offstage and resolved.record.scene_id is None:
            # An explicitly configured project cast may cover other scenes.
            # Never fetch or transmit those unselected actors here.
            continue
        if (
            (offstage and not character.allow_offstage_name)
            or (not offstage and character.character_id not in characters)
            or character.character_id in handles
            or not character.public_name.strip()
        ):
            _error("character_scope_invalid")
        handle = f"C{len(handles) + 1}"
        handles[character.character_id] = handle
        cast.append({"handle": handle, "public_name": character.public_name})
    if pack.pov_character_id not in handles:
        _error("pov_public_name_required")
    if spec.surface_plan.kind == "current_scene_summary":
        if pack.scene_plan is None or not pack.scene_plan.planned_summary:
            _error("current_plan_unavailable")
        surface = pack.scene_plan.planned_summary
    else:
        surface = spec.surface_plan.text
    approved_text = "\n".join([surface, *(claim.text for claim in spec.visible_claims)]).lower()
    required_literals = [item for item in pack.must_include if item]
    if any(item.lower() not in approved_text for item in required_literals):
        _error("required_constraint_not_authorized")
    claims = []
    for claim in spec.visible_claims:
        if claim.character_id is not None and claim.character_id not in handles:
            _error("claim_character_scope_invalid")
        if claim.presentation == "belief" and (
            spec.access_mode != "pov" or claim.character_id != pack.pov_character_id
        ):
            _error("belief_not_pov")
        if claim.presentation == "narrator_fact" and spec.access_mode != "omniscient":
            _error("narrator_permission_required")
        if claim.presentation == "character_statement" and claim.character_id is None:
            _error("statement_character_required")
        item = {"text": claim.text, "presentation": claim.presentation, "phase": claim.phase}
        if claim.character_id is not None:
            item["character"] = handles[claim.character_id]
        claims.append(item)
    view = {
        "contract_version": "writer_visible_context_v1",
        "isolated": True,
        "output_language": pack.output_language,
        "access_mode": spec.access_mode,
        "pov": handles[pack.pov_character_id],
        "characters": cast,
        "surface_plan": surface,
        # No new source text: each literal was explicitly authorized above.
        "required_literals": required_literals,
        "claims": claims,
        "style": spec.writer_style.model_dump(mode="json", exclude_none=True),
        "target_length": pack.scene_plan.target_length if pack.scene_plan else None,
    }
    text = canonical_json(view)
    internal = _internal_identifiers(pack) | {r.draft_id for r in spec.reader_presented}
    if any(ref in text for ref in internal):
        _error("internal_identifier_in_visible_text")
    _check_budget(pack, view)
    return view


def _check_budget(pack, view):
    serialized = canonical_json(view)
    han = len(re.findall(r"[\u3400-\u9fff]", serialized))
    # Reserve framing/prompt space; never silently trim an approved visible claim.
    estimate = han + math.ceil((len(serialized) - han) / 4) + 1600
    if estimate > pack.budget.target_tokens:
        _error("budget_exceeded")


def preflight_writer_context(pack):
    resolved = pack.writer_visibility
    if resolved is None:
        if pack.writer_visibility_required:
            _error("missing_policy")
        # The old unprotected path retains its complete canon/state input.
        # A reduced context must never masquerade as backward compatibility.
        return {"isolated": False, "access_mode": "legacy_unisolated"}
    if any(g.severity == "critical" for g in pack.missing_context):
        _error("context_incomplete")
    if (
        resolved.project_id != pack.project_id
        or resolved.scene_id != pack.scene_id
        or resolved.record.project_id != pack.project_id
        or resolved.record.scene_id not in {None, pack.scene_id}
    ):
        _error("scope_mismatch")
    if resolved.source_context_sha256 != writer_source_context_sha256(pack):
        _error("source_stale")
    expected = content_hash(
        canonical_json(
            {
                "record": resolved.record.model_dump(mode="json"),
                "source_context_sha256": resolved.source_context_sha256,
            }
        )
    )
    if resolved.policy_fingerprint != expected or not resolved.reader_sources_verified:
        _error("resolution_invalid")
    validate_reader_presented(
        pack.project_id, resolved.record.spec.reader_presented, resolved.reader_source_resolver
    )
    return _isolated_view(pack, resolved)


def preflight_agent_prose(
    pack,
    *,
    mode,
    instruction,
    has_additional_sources=False,
    allow_web_search=False,
    base_text=None,
    selected_text=None,
    selected_start=None,
    selected_end=None,
    latest_draft=None,
    local_sources=None,
    prose_input_grants=None,
):
    if mode == "discuss":
        return None
    if mode not in {"create_scene", "continue_scene", "revise_scene", "revise_selection"}:
        _error("unknown_prose_action")
    if pack is None:
        # Public callers must first check the owning Project's protection flag.
        # An old nonprotected discussion request could omit its context entirely.
        if prose_input_grants is not None:
            _error("context_required_for_exact_grant")
        return {"isolated": False, "access_mode": "legacy_unisolated"}
    view = preflight_writer_context(pack)
    if not view["isolated"]:
        if prose_input_grants is None:
            return view
        # A caller choosing a new exact-input grant also gets exact untruncated
        # input handling, while the old context remains explicitly unisolated.
        task = _authorized_prose_task(
            pack,
            mode,
            instruction,
            prose_input_grants,
            latest_draft,
            base_text,
            selected_text,
            selected_start,
            selected_end,
            None,
        )
        view["writing_task"] = task
        _check_budget(pack, {"legacy_context": pack.model_dump(mode="json"), "writing_task": task})
        return view
    if has_additional_sources or allow_web_search or local_sources:
        _error("additional_source_not_authorized")
    task = _authorized_prose_task(
        pack,
        mode,
        instruction,
        prose_input_grants,
        latest_draft,
        base_text,
        selected_text,
        selected_start,
        selected_end,
        view["surface_plan"],
    )
    view["writing_task"] = task
    _check_budget(pack, view)
    return view


def _authorized_prose_task(
    pack,
    mode,
    instruction,
    grants,
    draft,
    base_text,
    selected_text,
    selected_start,
    selected_end,
    surface,
):
    grant = ProseInputGrants.model_validate(grants) if grants is not None else None
    task = {"action": mode}
    actual_instruction = instruction.strip()
    if grant is not None and grant.instruction:
        if grant.instruction_sha256 != content_hash(actual_instruction):
            _error("instruction_grant_stale")
        task["instruction"] = actual_instruction
    elif surface is not None and actual_instruction == surface.strip():
        task["instruction"] = surface
    else:
        _error("instruction_not_authorized")
    if mode == "create_scene":
        if (grant and grant.target != "none") or base_text or selected_text or draft is not None:
            _error("unexpected_edit_target")
        return task
    expected_target = "selection" if mode == "revise_selection" else "draft"
    if grant is None or grant.target != expected_target or draft is None:
        _error("edit_source_not_authorized")
    if (
        draft.project_id != pack.project_id
        or draft.scene_id != pack.scene_id
        or draft.content_language != pack.output_language
        or draft.id != grant.draft_id
        or draft.version != grant.version
        or content_hash(draft.text) != grant.text_sha256
        or (base_text is not None and base_text != draft.text)
    ):
        _error("edit_source_stale")
    if expected_target == "selection":
        if (
            selected_start != grant.start
            or selected_end != grant.end
            or selected_text != grant.expected_text
        ):
            _error("edit_selection_stale")
        start, end = utf16_span(draft.text, grant.start, grant.end, grant.expected_text)
        task["target_text"] = draft.text[start:end]
        task["target_kind"] = "selection"
    else:
        task["target_text"] = draft.text
        task["target_kind"] = "saved_scene_draft"
    # The input grant does not grant reader disclosure or change entry knowledge.
    return task


def scene_review_constraint(pack, resolved=None):
    resolved = resolved or pack.writer_visibility
    if resolved is None:
        if pack.writer_visibility_required:
            _error("missing_policy")
        return None
    preflight_writer_context(pack.model_copy(update={"writer_visibility": resolved}))
    return _review_payload(pack, resolved)


def _review_payload(pack, resolved):
    spec = resolved.record.spec
    return canonical_json(
        {
            "kind": "author_narrative_visibility_not_canon",
            "policy_fingerprint": resolved.policy_fingerprint,
            "record": resolved.record.model_dump(mode="json"),
            "source_context_sha256": resolved.source_context_sha256,
            "canonical_style": pack.style_constraints.model_dump(mode="json"),
            "writer_style": spec.writer_style.model_dump(mode="json"),
            "rules": "Policy claims and expected reader inference are author intent, not canon truth or proof of reader knowledge. Beliefs, statements, records and declared quantities may be false; compare actual events/measurements against world rules, not a lie as if physically delivered, and do not invent an unstated validator. Actual physical violations still block. During-scene claims must not become entry knowledge. Check unauthorized major disclosure against explicit permission and full canon/style; ordinary consistent connecting description is allowed.",
        }
    )

"""Bounded main-agent collaboration; every generated edit remains noncanon."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from storygraph.core.errors import ContractError, ModelOutputError
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now
from storygraph.core.agent_config import ModelExecution
from storygraph.models.authoring import (
    AuthoringSession, AuthoringWorkspace, AuthoringProposal, AuthoringMessage,
    AuthoringToolAction, AuthoringDraftPin, AuthoringPatch, AuthoringCharacterSimulation,
    AuthoringEvidence, AuthoringCharacterKnowledge, AuthoringWriterChoice, authoring_tool_schema,
)
from storygraph.models.writer_visibility import ReaderPresented
from storygraph.services.canon_snapshot import canonical_json, content_hash
from storygraph.services.json_output import unwrap_json_fence
from storygraph.services.generation_budget import completion_budget
from storygraph.services.llm_provider import LLMMessage, LLMRequest
from storygraph.services.llm_provider import ProviderError
from storygraph.services.project_language import authoritative_language_message, validate_generated_output_language
from storygraph.services.text_span import utf16_span


def workspace_hash(workspace):
    return content_hash(canonical_json(workspace.model_dump(mode="json")))


def authoring_inputs_hash(session):
    return content_hash(canonical_json({"source_pins": [p.model_dump(mode="json") for p in session.source_pins],
                                        "draft_pins": [p.model_dump(mode="json") for p in session.draft_pins]}))


def apply_authoring_patch(workspace, patch):
    """Apply by identity, retaining order and every untouched design record."""
    def merged(current, upserts, removes, key):
        changes = {getattr(v, key): v for v in upserts}
        known = {getattr(v, key) for v in current}
        if not set(removes) <= known:
            raise ContractError("authoring_patch_remove_missing")
        return [changes.get(getattr(v, key), v) for v in current if getattr(v, key) not in removes] + [v for v in upserts if getattr(v, key) not in known]
    readers = list(workspace.reader_records)
    for record in patch.remove_reader_records:
        if record not in readers:
            raise ContractError("authoring_patch_remove_missing")
        readers.remove(record)
    readers += [r for r in patch.add_reader_records if r not in readers]
    return AuthoringWorkspace(items=merged(workspace.items, patch.upsert_items, patch.remove_item_ids, "id"),
        character_plans=merged(workspace.character_plans, patch.upsert_character_plans, patch.remove_character_ids, "character_id"),
        scene_cards=merged(workspace.scene_cards, patch.upsert_scene_cards, patch.remove_card_ids, "id"), reader_records=readers)


def authoring_proposal_diff(workspace, patch):
    updated = apply_authoring_patch(workspace, patch)
    changes = []
    for field, key in (("items", "id"), ("character_plans", "character_id"), ("scene_cards", "id")):
        before = {getattr(v, key): v.model_dump(mode="json") for v in getattr(workspace, field)}
        after = {getattr(v, key): v.model_dump(mode="json") for v in getattr(updated, field)}
        for identity in sorted(before.keys() | after.keys()):
            if before.get(identity) != after.get(identity):
                changes.append({"kind": field, "id": identity, "before": before.get(identity), "after": after.get(identity)})
    if workspace.reader_records != updated.reader_records:
        changes.append({"kind": "reader_records", "before": [r.model_dump(mode="json") for r in workspace.reader_records],
                        "after": [r.model_dump(mode="json") for r in updated.reader_records]})
    return changes


def authoring_workspace_patch(base, final, *, explicit_patches=()):
    """Compute one unambiguous delta after applying patches to a virtual workspace."""
    fields = {}
    for collection, upserts, removes, key in (
        ("items", "upsert_items", "remove_item_ids", "id"),
        ("character_plans", "upsert_character_plans", "remove_character_ids", "character_id"),
        ("scene_cards", "upsert_scene_cards", "remove_card_ids", "id"),
    ):
        before = {getattr(value, key): value for value in getattr(base, collection)}
        after = {getattr(value, key): value for value in getattr(final, collection)}
        explicit = {getattr(value, key) for patch in explicit_patches for value in getattr(patch, upserts)}
        fields[upserts] = [value for identity, value in after.items() if before.get(identity) != value or identity in explicit]
        fields[removes] = [identity for identity in before if identity not in after]
    fields["add_reader_records"] = [record for record in final.reader_records if record not in base.reader_records]
    fields["remove_reader_records"] = [record for record in base.reader_records if record not in final.reader_records]
    return AuthoringPatch(**fields)


def merge_authoring_fields(before, changes):
    if isinstance(before, dict) and isinstance(changes, dict):
        result = dict(before)
        for key, value in changes.items():
            result[key] = merge_authoring_fields(result[key], value) if key in result else value
        return result
    return changes


def merge_authoring_revision_patch(workspace, patch):
    """New author commands preserve omitted existing fields; explicit lists replace."""
    updates = {}
    for collection, field, key in (("items", "upsert_items", "id"),
                                   ("character_plans", "upsert_character_plans", "character_id"),
                                   ("scene_cards", "upsert_scene_cards", "id")):
        existing = {getattr(value, key): value for value in getattr(workspace, collection)}
        values = []
        for value in getattr(patch, field):
            if field == "upsert_scene_cards" and "status" in value.model_fields_set and value.status == "approved":
                raise ContractError("authoring_model_cannot_approve_card")
            old = existing.get(getattr(value, key))
            if old is not None:
                changes = value.model_dump(mode="json", exclude_unset=True)
                merged = merge_authoring_fields(old.model_dump(mode="json"), changes)
                if field == "upsert_scene_cards" and "status" not in value.model_fields_set and old.status == "approved":
                    merged["status"] = "proposed"
                value = type(value).model_validate(merged)
            values.append(value)
        updates[field] = values
    return patch.model_copy(update=updates)


def _message(role, content, tool_name=None, model_execution=None):
    return AuthoringMessage(id=new_id("amsg"), role=role, content=content,
                            created_at=utc_now(), tool_name=tool_name,
                            model_execution=model_execution.model_copy(deep=True) if model_execution is not None else None)


class AuthoringService:
    def __init__(self, *, store, provider=None, model="", source_resolver=None,
                 character_resolver=None, canon_resolver=None, draft_resolver=None,
                 impact_resolver=None, project_language_resolver=None, canon_query_resolver=None, model_execution=None, project_resolver=None, reviews_resolver=None, navigation_validator=None, passage_resolver=None, writer_resolver=None):
        self.store, self.provider, self.model = store, provider, model
        from storygraph.stores.author_context import AuthorContextStore
        self.author_context = AuthorContextStore(store)
        self.source_resolver, self.character_resolver = source_resolver, character_resolver
        self.canon_resolver, self.draft_resolver = canon_resolver, draft_resolver
        self.impact_resolver = impact_resolver
        self.project_language_resolver = project_language_resolver
        self.canon_query_resolver = canon_query_resolver
        self.project_resolver, self.reviews_resolver = project_resolver, reviews_resolver
        self.navigation_validator = navigation_validator
        self.passage_resolver = passage_resolver
        self.writer_resolver = writer_resolver
        self.model_execution = ModelExecution.model_validate(model_execution).model_copy(deep=True) if model_execution is not None else None

    def _generate(self, request):
        try:
            return self.provider.generate(request)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("request_failed", outcome_known=False) from None

    def get(self, project_id, session_id, *, message_limit=40, closed_proposal_limit=20):
        return AuthoringSession.model_validate(self.store.get(project_id, session_id, message_limit=message_limit, closed_proposal_limit=closed_proposal_limit))

    def history(self, project_id, session_id, *, kind="messages", query="", offset=0, limit=40, status=None):
        return self.store.journal_page(project_id, session_id, kind=kind, query=query, offset=offset, limit=limit, status=status)

    def get_proposal(self, project_id, session_id, proposal_id):
        return AuthoringProposal.model_validate(self.store.proposal(project_id, session_id, proposal_id))

    def list(self, project_id):
        return [AuthoringSession.model_validate(value) for value in self.store.list(project_id)]

    def create(self, *, project_id, content_language, title, idea, source_pins=None, draft_pins=None):
        if not idea.strip():
            raise ContractError("authoring_idea_required")
        now = utc_now()
        session = AuthoringSession(id=new_id("authoring"), project_id=project_id,
            content_language=content_language, title=title, source_pins=source_pins or [],
            draft_pins=draft_pins or [], messages=[_message("author", idea)], created_at=now, updated_at=now)
        self._validate_pins(session)
        return AuthoringSession.model_validate(self.store.save(session, expected_version=0))

    def _validate_pins(self, session):
        if self.project_language_resolver is not None and self.project_language_resolver(session.project_id) != session.content_language:
            raise ContractError("authoring_project_language_changed")
        for pin in session.source_pins:
            self._source(session, pin)
        for pin in session.draft_pins:
            self._draft(session, pin)

    def _canon_digest(self, project_id):
        if self.canon_resolver is None:
            return None
        canon = self.canon_resolver(project_id)
        fingerprint = canon.get("fingerprint") if isinstance(canon, dict) else None
        if isinstance(fingerprint, str) and len(fingerprint) == 64 and all(c in "0123456789abcdef" for c in fingerprint):
            return fingerprint
        return content_hash(canonical_json(canon))

    def _validate_turn_context(self, session, canon_sha256):
        if self.store.get(session.project_id, session.id)["version"] != session.version:
            raise ContractError("authoring_stale_version")
        self._validate_pins(session)
        if self._canon_digest(session.project_id) != canon_sha256:
            raise ContractError("authoring_canon_changed")

    def _source(self, session, pin):
        if not callable(self.source_resolver):
            raise ContractError("authoring_source_unavailable")
        text = self.source_resolver(session.project_id, pin)
        if not isinstance(text, str) or content_hash(text) != pin.sha256:
            raise ContractError("authoring_source_stale")
        return text

    def _draft(self, session, pin):
        if not callable(self.draft_resolver):
            raise ContractError("authoring_draft_unavailable")
        draft = self.draft_resolver(session.project_id, pin)
        if (draft.project_id != session.project_id or draft.scene_id != pin.scene_id
            or draft.id != pin.draft_id or draft.version != pin.version
            or content_hash(draft.text) != pin.text_sha256):
            raise ContractError("authoring_draft_stale")
        return draft

    def _cas(self, project_id, session_id, expected_version):
        session = self.get(project_id, session_id)
        if session.version != expected_version:
            raise ContractError("authoring_stale_version")
        return session

    def _save(self, session):
        prior = session.version
        session = session.model_copy(update={"version": prior + 1, "updated_at": utc_now()})
        # Revalidate bounds after list appends/model_copy updates.
        session = AuthoringSession.model_validate(session.model_dump(mode="json"))
        return AuthoringSession.model_validate(self.store.save(session, expected_version=prior))

    def _save_result(self, session, canon_sha256=None):
        self._validate_turn_context(session, canon_sha256)
        return self._save(session)

    def _record_format_diagnostic(self, session, error, canon_sha256, *, origin="main"):
        """Persist safe coordinates/schema paths only; never retain invalid model text."""
        if isinstance(error, json.JSONDecodeError):
            details = {"kind": "invalid_json", "line": error.lineno, "column": error.colno}
        elif isinstance(error, ProviderError):
            details = {"kind": "completed_output_format", "category": error.category}
        elif isinstance(error, ContractError) and str(error) == "authoring_patch_dangling_reference":
            details = {"kind": "design_reference_validation", "code": "authoring_patch_dangling_reference",
                       "hint": "depends_on may reference only item/card IDs in the final authoring workspace. Bind a canonical Scene using scene_id, never depends_on. Do not guess or substitute an identifier."}
        elif isinstance(error, ContractError) and str(error) == "authoring_empty_patch":
            details = {"kind": "empty_patch_validation", "code": "authoring_empty_patch",
                       "hint": "A new proposal must contain explicit changes or review targets. Use finish for discussion, or propose_card_review with exact current card_ids to request reapproval without editing content."}
        elif isinstance(error, ValidationError):
            known_fields = set()
            def collect(value):
                if isinstance(value, dict):
                    known_fields.update(value.get("properties", {}))
                    for nested in value.values():
                        collect(nested)
                elif isinstance(value, list):
                    for nested in value:
                        collect(nested)
            collect(authoring_tool_schema())
            collect(AuthoringCharacterSimulation.model_json_schema())
            errors = error.errors(include_url=False, include_input=False)
            paths = [[part if (type(part) is int and part >= 0) or (isinstance(part, str) and part in known_fields)
                      else "<unknown_field>" for part in entry["loc"]] for entry in errors[:20]]
            details = {"kind": "schema_validation", "paths": paths, "total_errors": len(errors), "more": len(errors) > len(paths)}
            # Exact internal validator statements map to static public hints.
            # Never echo arbitrary error messages, ctx, input or offending keys.
            hint_map = {
                "Subjective design items require their owning character.": (
                    "subjective_item_requires_character_id",
                    "character_belief and character_claim require a nonnull character_id naming the owning actor."),
                "An open question cannot be an author-decided truth.": (
                    "open_question_cannot_be_author_decided",
                    "An open_question status must be open or alternative, never author_decided."),
            }
            hints = []
            for entry, path in zip(errors[:20], paths):
                hint = hint_map.get(str(entry.get("ctx", {}).get("error", "")))
                if hint is not None:
                    hints.append({"path": path, "code": hint[0], "hint": hint[1]})
            if hints:
                details["hints"] = hints
        else:
            details = {"kind": "invalid_command_format"}
        note = ("上一条模型响应未被接受，也未执行其中的无效命令。这里只记录安全格式诊断；"
                "没有保留无效响应正文。原回合剩余额度内最多进行一次已完成输出的格式修正；"
                "不确定、网络或凭据失败不会重试。"
                if session.content_language == "zh-CN" else
                "The previous model response was rejected; its invalid command was not executed. "
                "Only safe format diagnostics are retained, not the invalid response text. "
                "At most one completed-output format correction may use the original turn's remaining calls. "
                "Uncertain, network and credential failures are never retried.")
        trace = canonical_json({"tool": "format_diagnostic", "args": {}, "result": {
            "accepted": False, "origin": origin, "call_number": session.turn_calls_started,
            "diagnostic": details, "message": note}})
        session.messages.append(_message("tool", trace, "format_diagnostic", model_execution=self.model_execution))
        self._save_result(session, canon_sha256)

    def character_view(self, session, character_id, card_id=None):
        """A view contains only one actor's plans and subjective claims."""
        if not isinstance(character_id, str) or not character_id:
            raise ContractError("authoring_character_required")
        items = [i for i in session.workspace.items if i.character_id == character_id
                 and i.kind in {"character_belief", "character_claim"}]
        plan = next((p for p in session.workspace.character_plans if p.character_id == character_id), None)
        safe_plan = plan.model_dump(mode="json") if plan else None
        if safe_plan:
            safe_plan["belief_item_ids"] = [i.id for i in items if i.id in plan.belief_item_ids]
            safe_plan["intended_actions"] = [a for a in safe_plan["intended_actions"] if a["character_id"] == character_id]
        card = None
        if card_id:
            card = next((c for c in session.workspace.scene_cards if c.id == card_id), None)
            if card is None:
                raise ContractError("authoring_card_not_found")
        # Canon knowledge belongs to the selected scene-entry time, not project-global now.
        scene_id = card.scene_id if card is not None else None
        canon = self.character_resolver(session.project_id, character_id, scene_id) if self.character_resolver else {}
        result = {"character_id": character_id, "subjective_items": [{"id": i.id, "kind": i.kind, "status": i.status, "text": i.text, "about_character_id": i.about_character_id} for i in items],
                "plan": safe_plan, "canon_knowledge": canon}
        if card is not None:
            result["entry_knowledge"] = [{"text": k.text} for k in card.entry_knowledge if k.character_id == character_id]
            result["intended_actions"] = [{"intention": a.intention} for a in card.intended_actions if a.character_id == character_id]
        return result

    def impact_analysis(self, session, item_ids):
        if not isinstance(item_ids, list) or any(not isinstance(i, str) for i in item_ids):
            raise ContractError("authoring_invalid_impact_ids")
        impacted = set(item_ids)
        while True:
            before = len(impacted)
            for item in session.workspace.items:
                if impacted.intersection(item.depends_on):
                    impacted.add(item.id)
            for card in session.workspace.scene_cards:
                if (impacted.intersection(card.depends_on)
                    or any(impacted.intersection(a.depends_on) for a in card.intended_actions)
                    or any(k.item_id in impacted for k in card.entry_knowledge + card.acquisitions)):
                    impacted.add(card.id)
            if before == len(impacted):
                break
        cards = [c for c in session.workspace.scene_cards if c.id in impacted or impacted.intersection(c.depends_on)
                 or any(impacted.intersection(a.depends_on) for a in c.intended_actions)
                 or any(k.item_id in impacted for k in c.entry_knowledge + c.acquisitions)]
        scenes = sorted({c.scene_id for c in cards if c.scene_id})
        drafts = [p.model_dump(mode="json") for p in session.draft_pins if p.scene_id in scenes]
        downstream = self.impact_resolver(session.project_id, scenes) if self.impact_resolver else []
        return {"item_ids": sorted(impacted), "card_ids": [c.id for c in cards], "scene_ids": scenes,
                "saved_drafts": drafts, "downstream": downstream,
                "requires_author_review": bool(cards or drafts or downstream)}

    def _validate_workspace(self, session, workspace):
        item_ids = {item.id for item in workspace.items}
        design_ids = item_ids | {card.id for card in workspace.scene_cards}
        references = set()
        for item in workspace.items:
            references.update(item.depends_on)
        for plan in workspace.character_plans:
            if not set(plan.belief_item_ids) <= item_ids:
                raise ContractError("authoring_patch_dangling_item_reference")
            for action in plan.intended_actions:
                references.update(action.depends_on)
        for card in workspace.scene_cards:
            references.update(card.depends_on)
            if any(k.item_id is not None and k.item_id not in item_ids for k in card.entry_knowledge + card.acquisitions):
                raise ContractError("authoring_patch_dangling_item_reference")
            for action in card.intended_actions:
                references.update(action.depends_on)
        if not references <= design_ids:
            raise ContractError("authoring_patch_dangling_reference")
        previous = {c.id: c for c in session.workspace.scene_cards}
        for card in workspace.scene_cards:
            old = previous.get(card.id)
            if card.status == "approved" and (old is None or old != card):
                raise ContractError("authoring_model_cannot_approve_card")
        for item in workspace.items:
            self._validate_evidence(session, item.evidence)
        for card in workspace.scene_cards:
            for acquisition in card.entry_knowledge + card.acquisitions:
                self._validate_evidence(session, acquisition.evidence)
        self._validate_reader_records(session, workspace.reader_records)
        fields = {"item_" + i.id: i.text for i in workspace.items}
        fields.update({"card_" + c.id: c.title + "\n" + c.intended_outcome for c in workspace.scene_cards})
        fields.update({"rationale_" + i.id: i.rationale for i in workspace.items})
        for n, plan in enumerate(workspace.character_plans):
            fields[f"plan_{n}"] = plan.goal + "\n" + "\n".join(plan.knowledge_assumptions)
            for a, action in enumerate(plan.intended_actions):
                fields[f"plan_{n}_action_{a}"] = action.intention
        for n, card in enumerate(workspace.scene_cards):
            fields[f"card_{n}_surface"] = card.writer_policy.surface_plan.text
            for k, knowledge in enumerate(card.entry_knowledge + card.acquisitions):
                fields[f"card_{n}_knowledge_{k}"] = knowledge.text
            for a, action in enumerate(card.intended_actions):
                fields[f"card_{n}_action_{a}"] = action.intention
            for c, claim in enumerate(card.writer_policy.visible_claims):
                fields[f"card_{n}_claim_{c}"] = claim.text
        validate_generated_output_language(output_language=session.content_language, fields=fields)

    def _validate_evidence(self, session, evidence):
        for e in evidence:
            if e.draft not in session.draft_pins:
                raise ContractError("authoring_unpinned_evidence")
            draft = self._draft(session, e.draft)
            if draft.discarded:
                raise ContractError("authoring_discarded_draft_not_evidence")
            utf16_span(draft.text, e.start, e.end, e.expected_text)

    def _validate_reader_records(self, session, records):
        for record in records:
            pin = next((p for p in session.draft_pins if p.draft_id == record.draft_id
                        and p.version == record.version and p.text_sha256 == record.text_sha256), None)
            if pin is None:
                raise ContractError("authoring_unpinned_reader_evidence")
            draft = self._draft(session, pin)
            if draft.discarded:
                raise ContractError("authoring_discarded_draft_not_reader_presented")
            utf16_span(draft.text, record.start, record.end, record.expected_text)

    def _propose(self, session, patch, summary, evidence=None, canon_sha256=None, supersedes_proposal_id=None):
        if not any(patch.model_dump(mode="json").values()):
            raise ContractError("authoring_empty_patch")
        validate_generated_output_language(output_language=session.content_language, fields={"summary": summary})
        patch = merge_authoring_revision_patch(session.workspace, patch)
        previous_cards = {c.id: c for c in session.workspace.scene_cards}
        normalized_cards = []
        for card in patch.upsert_scene_cards:
            old = previous_cards.get(card.id)
            if old is None:
                version = 1
            else:
                changed = card.model_dump(exclude={"version"}) != old.model_dump(exclude={"version"})
                version = old.version + 1 if changed else old.version
            normalized_cards.append(card.model_copy(update={"version": version}))
        patch = patch.model_copy(update={"upsert_scene_cards": normalized_cards})
        workspace = apply_authoring_patch(session.workspace, patch)
        self._validate_workspace(session, workspace)
        old = {i.id: i for i in session.workspace.items}
        new = {i.id: i for i in workspace.items}
        changed = [key for key in old.keys() | new.keys() if old.get(key) != new.get(key)]
        old_cards = {c.id: c for c in session.workspace.scene_cards}
        changed_cards = {c.id for c in workspace.scene_cards if old_cards.get(c.id) != c}
        changed_cards.update(old_cards.keys() - {c.id for c in workspace.scene_cards})
        old_plans = {p.character_id: p for p in session.workspace.character_plans}
        new_plans = {p.character_id: p for p in workspace.character_plans}
        changed_actors = {key for key in old_plans.keys() | new_plans.keys() if old_plans.get(key) != new_plans.get(key)}
        actor_cards = {c.id for c in session.workspace.scene_cards if c.pov_character_id in changed_actors
            or any(v.character_id in changed_actors for v in c.writer_policy.characters)
            or any(v.character_id in changed_actors for v in c.entry_knowledge + c.acquisitions + c.intended_actions)
            or any(v.character_id in changed_actors for v in c.writer_policy.visible_claims)}
        impact = self.impact_analysis(session, changed + sorted(changed_cards | actor_cards))
        # An explicit unchanged-card submission is still a request to review its
        # approval after input rebinding; it must not approve untouched cards.
        reviewed_cards = {c.id for c in patch.upsert_scene_cards}
        affected = sorted(set(impact["card_ids"]) | changed_cards | reviewed_cards | (old_cards.keys() - {c.id for c in workspace.scene_cards}))
        scenes = set(impact["scene_ids"])
        scenes.update(c.scene_id for c in workspace.scene_cards if c.id in affected and c.scene_id)
        self._validate_evidence(session, evidence or [])
        proposal = AuthoringProposal(id=new_id("adesign"), base_workspace_sha256=workspace_hash(session.workspace),
            canon_sha256=canon_sha256 if canon_sha256 is not None else self._canon_digest(session.project_id),
            inputs_sha256=authoring_inputs_hash(session),
            supersedes_proposal_id=supersedes_proposal_id,
            model_execution=self.model_execution.model_copy(deep=True) if self.model_execution is not None else None,
            patch=patch, summary=summary, affected_card_ids=affected,
            affected_scene_ids=sorted(scenes), evidence=evidence or [], created_at=utc_now())
        session.proposals.append(proposal)
        compact_impact = {key: impact[key] for key in ("item_ids", "card_ids", "scene_ids", "requires_author_review")}
        compact_impact.update(saved_draft_count=len(impact["saved_drafts"]), downstream_count=len(impact["downstream"]))
        return {"proposal_id": proposal.id, "summary": summary, "impact": compact_impact,
                "affected_card_ids": affected, "affected_scene_ids": sorted(scenes), "status": "pending"}

    def _revise_proposal(self, session, proposal_id, patch, summary, canon_sha256=None, *, reconcile_pin=None, reconcile_card=None):
        original = next((proposal for proposal in session.proposals if proposal.id == proposal_id), None)
        if original is None:
            original = self.get_proposal(session.project_id, session.id, proposal_id)
        if original.status != "pending":
            raise ContractError("authoring_proposal_not_pending")
        if original.base_workspace_sha256 != workspace_hash(session.workspace):
            raise ContractError("authoring_workspace_changed")
        self._validate_pins(session)
        if original.inputs_sha256 != authoring_inputs_hash(session):
            raise ContractError("authoring_proposal_inputs_changed")
        current_canon = self._canon_digest(session.project_id)
        if original.canon_sha256 != current_canon or (canon_sha256 is not None and canon_sha256 != current_canon):
            raise ContractError("authoring_proposal_canon_changed")
        virtual = apply_authoring_patch(session.workspace, original.patch)
        changes = merge_authoring_revision_patch(virtual, patch)
        final = apply_authoring_patch(virtual, changes)
        combined = authoring_workspace_patch(session.workspace, final, explicit_patches=(original.patch, changes))
        if reconcile_pin is not None:
            self._validate_reconciliation_patch(session, combined, reconcile_pin, reconcile_card)
        return self._propose(session, combined, summary, canon_sha256=current_canon,
                             supersedes_proposal_id=original.id)

    def _propose_design_changes(self, session, args, canon_sha256=None):
        groups = {"item": ("items", "upsert_items", "id", {"id"}),
                  "character_plan": ("character_plans", "upsert_character_plans", "character_id", {"character_id"}),
                  "scene_card": ("scene_cards", "upsert_scene_cards", "id", {"id", "status", "version", "scene_id"})}
        patch = {"upsert_items": [], "upsert_character_plans": [], "upsert_scene_cards": []}
        for change in args["changes"]:
            collection, output, identity, protected = groups[change["target_type"]]
            old = next((value for value in getattr(session.workspace, collection) if getattr(value, identity) == change["target_id"]), None)
            if old is None:
                raise ContractError("authoring_design_change_target_not_found")
            fields = change["fields"]
            if set(fields).intersection(protected):
                raise ContractError("authoring_design_change_protected_field")
            if not set(fields) <= type(old).model_fields.keys():
                raise ContractError("authoring_design_change_unknown_field")
            merged = merge_authoring_fields(old.model_dump(mode="json"), fields)
            if change["target_type"] == "scene_card":
                merged["status"] = "proposed"
            patch[output].append(type(old).model_validate(merged))
        return self._propose(session, AuthoringPatch(**patch), args["summary"], canon_sha256=canon_sha256)

    def _propose_card_review(self, session, args, canon_sha256=None):
        cards = {card.id: card for card in session.workspace.scene_cards}
        if any(identity not in cards for identity in args["card_ids"]):
            raise ContractError("authoring_card_review_target_not_found")
        selected = [cards[identity].model_copy(deep=True, update={"status": "proposed"}) for identity in args["card_ids"]]
        return self._propose(session, AuthoringPatch(upsert_scene_cards=selected), args["summary"], canon_sha256=canon_sha256)

    def turn(self, *, project_id, session_id, expected_version, message, max_steps=6, _reconcile_pin=None, _reconcile_card=None, navigation_context=None, collaboration_mode="collaborate", selected_passage=None):
        if not self.provider:
            raise ContractError("authoring_provider_required")
        if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 8:
            raise ContractError("authoring_invalid_step_limit")
        if not message.strip():
            raise ContractError("authoring_message_required")
        from storygraph.services.authoring_collaboration import allowed_authoring_tools
        allowed_authoring_tools(collaboration_mode)
        navigation_context = self._navigation(project_id, navigation_context or {})
        if selected_passage is not None:
            from storygraph.services.authoring_passage import AuthoringSelectedPassage
            selected_passage = AuthoringSelectedPassage.model_validate(selected_passage)
            if self.passage_resolver is None:
                raise ContractError("authoring_selected_passage_unavailable")
            self.passage_resolver(project_id, navigation_context.get("scene_id"), selected_passage)
        session = self._cas(project_id, session_id, expected_version)
        if session.turn_status == "running":
            raise ContractError("authoring_turn_running")
        self._validate_pins(session)
        canon_sha256 = self._canon_digest(project_id)
        first_idea = (session.turn_id is None and len(session.messages) == 1
            and session.messages[0].role == "author" and session.messages[0].content == message)
        if not first_idea:
            session.messages.append(_message("author", message))
        session.turn_status, session.turn_id, session.turn_error_category = "running", new_id("aturn"), None
        session.turn_calls_started, session.turn_max_steps = 0, max_steps
        active_key = (project_id, session_id)
        with self.store._lock:
            session = self._save(session)
            self.store._active_turns[active_key] = session.turn_id
        try:
            return self._run_turn(session, max_steps, _reconcile_pin, canon_sha256, _reconcile_card, navigation_context, collaboration_mode, selected_passage)
        except Exception as exc:
            latest = self.get(project_id, session_id)
            if latest.turn_id == session.turn_id and latest.turn_status == "running":
                latest.turn_status = "unknown" if isinstance(exc, ProviderError) and not exc.outcome_known else "failed"
                latest.turn_error_category = exc.category if isinstance(exc, ProviderError) else ("invalid_output" if isinstance(exc, ModelOutputError) else "tool_failed")
                self._save(latest)
            raise
        finally:
            with self.store._lock:
                if self.store._active_turns.get(active_key) == session.turn_id:
                    self.store._active_turns.pop(active_key, None)

    def recover_turn(self, *, project_id, session_id, expected_version):
        """Explicit recovery of an interrupted reservation; does not call a provider."""
        session = self._cas(project_id, session_id, expected_version)
        if session.turn_status != "running":
            raise ContractError("authoring_turn_not_running")
        with self.store._lock:
            if (project_id, session_id) in self.store._active_turns:
                raise ContractError("authoring_turn_still_active")
        session.turn_status, session.turn_error_category = "unknown", "interrupted"
        return self._save(session)

    def _run_turn(self, session, max_steps, reconcile_pin=None, canon_sha256=None, reconcile_card=None, navigation_context=None, collaboration_mode="collaborate", selected_passage=None):
        from storygraph.services.authoring_mcp import AuthoringMCPServer, AuthoringMCPClient
        def validate_turn():
            self._validate_turn_context(session, canon_sha256)
            if selected_passage is not None:
                self.passage_resolver(session.project_id, (navigation_context or {}).get("scene_id"), selected_passage)
        read_draft_ids, quote_registry = set(), {}
        framework_read, framework_read_id = None, None
        if reconcile_pin is not None and reconcile_card is not None:
            validate_turn()
            self._reconciliation_card(session, reconcile_pin, *reconcile_card)
            draft = self._draft(session, reconcile_pin)
            if draft.discarded:
                raise ContractError("authoring_discarded_draft_not_evidence")
            framework_read = self._read_source_page(reconcile_pin, draft.text, {"start": None, "end": None})
            trace = canonical_json({"tool": "read_source", "initiated_by": "framework",
                "args": {"kind": "draft", "id": reconcile_pin.draft_id}, "result": framework_read})
            if len(trace) > 30000:
                raise ContractError("authoring_tool_result_budget")
            message = _message("tool", trace, "read_source")
            framework_read_id = message.id
            session.messages.append(message)
            session = self._save_result(session, canon_sha256)
            read_draft_ids.add(reconcile_pin.draft_id)
        prompt = (Path(__file__).parents[1] / "prompts" / "authoring_agent.md").read_text(encoding="utf-8")
        system = prompt + "\n" + authoritative_language_message(session.content_language)
        def dispatch(action):
            nonlocal session, calls, origin
            if selected_passage is not None and (action.tool in {"search_history", "inspect_reviews"}
                    or (action.tool in {"read_source", "search_source"} and action.args["kind"] == "draft")):
                raise ContractError("authoring_selected_passage_full_draft_read_forbidden")
            if action.tool == "simulate_character":
                if calls >= max_steps:
                    return {"status": "budget_exhausted", "note": "No remaining provider call reserved for character simulation."}
                calls += 1
                session.turn_calls_started = calls
                session = self._save(session)
                origin = "simulate_character"
                return self._simulate_character(session, action.args, canon_sha256)
            return self._tool(session, action, reconcile_pin=reconcile_pin, canon_sha256=canon_sha256,
                reconcile_card=reconcile_card, quote_registry=quote_registry, read_draft_ids=read_draft_ids,
                navigation_context=navigation_context, mcp=mcp)
        mcp = AuthoringMCPClient(AuthoringMCPServer(dispatch=dispatch,
            validate_context=validate_turn, mode=collaboration_mode,
            excluded_tools={"list_writers", "pick_writer"} if reconcile_pin is not None else ()))
        mcp.initialize()
        catalog = mcp.call("tools/list")
        resources = mcp.call("resources/list")
        default_skill = mcp.call("resources/read", {"uri": "storygraph://skills/author-collaboration"})
        allowed = {tool["name"] for tool in catalog["tools"]}
        schema = authoring_tool_schema()
        schema["oneOf"] = [v for v in schema["oneOf"] if v["properties"]["tool"]["const"] in allowed]
        system += "\nAllowed tool JSON schema:\n" + canonical_json(schema)
        system += "\nBuilt-in executable working methods:\n" + canonical_json(default_skill)
        system += "\nMCP resources (use read_skill to load):\n" + canonical_json(resources)
        system += "\nMode: " + collaboration_mode + ". Never claim a tool ran before receiving its real result."
        system += ("\n【本次模型响应的传输规则，必须遵守】\n"
                   "你现在只选择下一步的一次工具调用，不是在编写执行记录。整个响应只能是一个JSON对象，"
                   "顶层只有tool和args，args必须符合所选工具的schema。写完这个对象的最后一个右花括号就立即结束响应。"
                   "不能输出第二个JSON对象、命令数组、Markdown、XML标签、说明或虚构的工具结果。\n"
                   "工具由应用执行；真正的结果会在下一次模型请求中提供。即使你已经想好后续步骤，"
                   "也必须等待这次真实结果，再在下一次请求里选择下一条命令。"
                   "read_source不带范围本身就是完整的一次调用，不能接着再输出一个带范围的read_source。\n"
                   "Source/Draft标识符只能逐字复制当前pin的id或draft_id；不要猜、改写或使用示例占位符。"
                   "要向作者解释或提问时，选择finish并把正文放入args.message，正文语言服从项目语言。\n"
                   "ONE RESPONSE = ONE COMMAND. After its closing brace, stop and wait for the runtime.")
        history_window, history_chars = [], 0
        for message in reversed(session.messages[-30:]):
            if message.id == framework_read_id or (selected_passage is not None and message.role == "tool"):
                continue  # The exact current page is supplied once as context data below.
            if history_chars + len(message.content) > 60000:
                break
            history_window.append(message)
            history_chars += len(message.content)
        history_window.reverse()
        author_context = self.author_context.context(session.project_id)
        current_text = " ".join(m.content for m in session.messages[-12:] if m.role == "author")[-12000:]
        memories = self.author_context.relevant(session.project_id,current_text,session.content_language)
        history_ids = {m.id for m in history_window if m.role == "author"}
        overrides = self.author_context.history_overrides(session.project_id, session.id, history_ids)
        context = {"author_only_project_context": {"instructions": author_context["instructions"], "memories": memories,"historical_message_overrides":overrides,
                   "boundary": "Author instructions and memories are noncanon author-only preferences/design. Never supply to Writer or character simulation. Tentative ideas are not decisions. Withdrawn or manually edited memories override earlier conversation; never recreate from old text. finish may record up to six memories from exact author-message evidence, without an extra model call. For explicit author correction or rejection, use operation withdraw or replace with the previous memory_id and quote the NEW correcting author message. Never modify an author-edited memory. Keep memory text a narrow faithful author-only summary of its exact quoted evidence, never inferred story truth; only explicit author decisions are active decisions; uncertain possibilities remain tentative. Never infer author decisions from assistant/tool/imported/draft statements."}, "navigation_context": navigation_context or {}, "collaboration_mode": collaboration_mode, "workspace_index": {"item_ids": [i.id for i in session.workspace.items],
                   "character_ids": [p.character_id for p in session.workspace.character_plans],
                   "card_ids": [c.id for c in session.workspace.scene_cards], "reader_records_count": len(session.workspace.reader_records)},
                   "history_window": {"included_messages": len(history_window), "character_limit": 60000,
                                      "more": session.history_counts.messages > len(history_window),
                                      "note": "Recent bounded history only; search_history searches the complete durable journal."},
                   "source_history_boundary": "Earlier discussion/source quotations remain historical records. Only current selected source_pins and draft_pins are current evidence; old quotations cannot silently replace these inputs.",
                   "source_pins": [p.model_dump(mode="json") for p in session.source_pins[-10:]],
                   "source_pins_total": len(session.source_pins), "source_pins_more": len(session.source_pins) > 10,
                   "draft_pins": [p.model_dump(mode="json") for p in session.draft_pins[-10:]],
                   "draft_pins_total": len(session.draft_pins), "draft_pins_more": len(session.draft_pins) > 10,
                   "history_counts": session.history_counts.model_dump(),
                   "history_has_more": session.history_has_more.model_dump()}
        if session.writer_choice is not None:
            context["writer_choice"] = session.writer_choice.model_dump(exclude={"fingerprint"})
        if selected_passage is not None:
            context["selected_passage"] = self.passage_resolver(session.project_id, (navigation_context or {}).get("scene_id"), selected_passage)
            context["selected_passage_boundary"] = "Single-turn Main-only selected excerpt. This grants no whole-Draft/tool/Writer/simulation access and is not a reconciliation read or evidence."
        if reconcile_card is not None:
            selected = self._reconciliation_card(session, reconcile_pin, *reconcile_card)
            context["reconciliation_card"] = selected.model_dump(mode="json")
            context["reconciliation_draft"] = reconcile_pin.model_dump(mode="json")
            context["reconciliation_read"] = framework_read
            context["reconciliation_tool"] = "The framework has freshly read the exact selected Draft page shown here. You may start with search_draft_quotes, then propose_draft_evidence and finish. Other historical text cannot replace this current pin/page. Use read_source for further pages if more=true. Do not rewrite the card or calculate UTF-16 offsets."
        messages = [LLMMessage("system", system), LLMMessage("user", canonical_json(context))]
        # Persisted author messages are evidence, not privileged system instructions.
        override_map = {entry["source_message_id"]:entry for entry in overrides}
        def projected_history_message(message):
            override = override_map.get(message.id)
            if override:
                replacement = override.get("replacement")
                return "[author message id=" + message.id + "; superseded notebook source; original retained only in local history] " + (replacement or "Withdrawn. Do not reuse its old instructions, preferences, or tentative design.")
            return "[author message id=" + message.id + "] " + message.content if message.role == "author" else message.content
        messages += [LLMMessage("user" if m.role == "author" else "assistant", projected_history_message(m)) for m in history_window]
        calls = 0
        correction_used = False
        while calls < max_steps:
            # Count dispatch before the socket call: an unknown transport outcome consumes budget.
            if sum(len(m.content) for m in messages) > 180000:
                raise ContractError("authoring_context_budget_exceeded")
            validate_turn()
            calls += 1
            session.turn_calls_started = calls
            session = self._save(session)
            origin = "main"
            try:
                response = self._generate(LLMRequest(messages=messages, model=self.model, max_tokens=completion_budget(self.provider, 6000)))
                validate_turn()
                if len(response.content) > 120000:
                    raise ValueError("oversized")
                action = AuthoringToolAction.model_validate(json.loads(unwrap_json_fence(response.content)))
                if (reconcile_pin is not None and action.tool in {"propose_workspace", "revise_proposal", "propose_draft_evidence"}
                    and reconcile_pin.draft_id not in read_draft_ids):
                    raise ContractError("authoring_reconciliation_read_required")
                result = mcp.execute(action)
                if action.tool == "read_source" and action.args["kind"] == "draft":
                    read_draft_ids.add(action.args["id"])
            except (ValueError, TypeError, KeyError, ValidationError, ContractError, ProviderError) as exc:
                if isinstance(exc, ContractError) and not isinstance(exc, ModelOutputError) and str(exc) not in {
                    "authoring_patch_dangling_reference", "authoring_empty_patch"}:
                    raise
                if isinstance(exc, ProviderError) and (not exc.allow_format_retry or not exc.outcome_known or exc.category not in {
                    "invalid_response", "incomplete_response", "unsupported_output"}):
                    raise
                failure = exc if isinstance(exc, (ContractError, ProviderError)) else ModelOutputError("authoring_invalid_tool_output")
                latest = self.get(session.project_id, session.id)
                last = latest.messages[-1] if latest.messages else None
                recorded = (last is not None and last.tool_name == "format_diagnostic"
                            and json.loads(last.content)["result"].get("call_number") == calls)
                if not recorded:
                    self._record_format_diagnostic(session, exc, canon_sha256, origin=origin)
                    latest = self.get(session.project_id, session.id)
                if correction_used or calls >= max_steps:
                    raise failure from None
                self._validate_turn_context(latest, canon_sha256)
                correction_used = True
                session = latest
                diagnostic = session.messages[-1].content
                feedback = ("上一条已完成的输出格式无效，未接受其命令。现在使用本回合原有调用额度中的一次格式修正；"
                            "请根据安全诊断只输出一个符合schema的下一步命令。不要假定失败命令已执行，不要复述无效原文。"
                            if session.content_language == "zh-CN" else
                            "The completed output was rejected. Use this turn's single format-correction opportunity "
                            "to return one schema-valid next command. The rejected command was not executed; do not repeat its raw text.")
                marker = canonical_json({"tool": "format_correction", "args": {}, "result": {
                    "calls_started": calls, "max_steps": max_steps, "remaining_calls": max_steps - calls,
                    "correction_limit": 1, "message": feedback}})
                session.messages.append(_message("tool", marker, "format_correction", model_execution=self.model_execution))
                session = self._save_result(session, canon_sha256)
                messages += [LLMMessage("user", diagnostic + "\n" + feedback)]
                continue
            if action.tool == "finish":
                session.messages.append(_message("assistant", result["reply"], model_execution=self.model_execution))
                session.turn_status = "idle"
                if result.get("memory_diagnostics"):
                    session.messages.append(_message("tool",canonical_json({"memory_diagnostics":result["memory_diagnostics"]}),"author_memory_validation"))
                saved = self._save_result(session, canon_sha256)
                for memory in result.get("author_memories", []):
                    try:
                        self.author_context.record(session.project_id, session.id, **memory)
                    except ContractError:
                        pass  # A concurrent human edit or retraction never invalidates the saved Main response.
                return saved
            trace_args = {"summary": action.args["summary"], "proposal_id": result["proposal_id"]} if action.tool in {"propose_workspace", "revise_proposal", "propose_draft_evidence", "propose_design_changes", "propose_card_review"} else action.args
            trace = canonical_json({"tool": action.tool, "args": trace_args, "result": result})
            if len(trace) > 30000:
                raise ContractError("authoring_tool_result_budget")
            session.messages.append(_message("tool", trace, action.tool, model_execution=self.model_execution))
            session = self._save_result(session, canon_sha256)
            messages += [LLMMessage("assistant", response.content), LLMMessage("user", "Tool result: " + canonical_json(result))]
        # Bounded completion persists visible traces and pending proposals without another paid call.
        reply = "本轮工具调用已达到上限，请审阅设计提案或继续讨论。" if session.content_language == "zh-CN" else "This turn reached its tool limit. Review the proposals or continue the discussion."
        session.messages.append(_message("assistant", reply, model_execution=self.model_execution))
        session.turn_status = "idle"
        return self._save_result(session, canon_sha256)

    def _simulate_character(self, session, args, canon_sha256=None):
        view = self.character_view(session, args["character_id"], args.get("card_id"))
        # Status/rationale labels belong to author design and cannot tell an actor it is mistaken.
        for item in view["subjective_items"]:
            item.pop("status", None)
            item.pop("kind", None)
            item.pop("id", None)
            item.pop("about_character_id", None)
        view.pop("character_id", None)
        if view["plan"]:
            plan = view["plan"]
            view["plan"] = {"goal": plan["goal"], "knowledge_assumptions": plan["knowledge_assumptions"],
                            "intended_actions": [{"intention": a["intention"]} for a in plan["intended_actions"]]}
        card_id = args.get("card_id")
        if card_id:
            card = next((c for c in session.workspace.scene_cards if c.id == card_id), None)
            if card is None:
                raise ContractError("authoring_card_not_found")
            view["entry_knowledge"] = [{"text": k.text} for k in card.entry_knowledge if k.character_id == args["character_id"]]
            view["intended_actions"] = [{"intention": a.intention} for a in card.intended_actions if a.character_id == args["character_id"]]
        kind = args.get("question_kind", "next_action")
        questions = {"next_action": "Choose plausible next actions toward your goal from your own beliefs.",
                     "conflict_response": "Choose plausible responses to conflict from your own beliefs.",
                     "disclosure_choice": "Choose what you would say or withhold based on your own beliefs."}
        system = "You simulate one fictional actor's subjective decision. Only the supplied view exists for this task. Do not infer hidden author truths or whether beliefs are mistaken. Return noncanon action options, not prose or canon. "
        system += authoritative_language_message(session.content_language)
        system += "\nOutput schema: " + canonical_json(AuthoringCharacterSimulation.model_json_schema())
        # A fresh request deliberately excludes main-agent history, global design, other views,
        # and free-form main-authored questions (which could smuggle private author information).
        self._validate_turn_context(session, canon_sha256)
        response = self._generate(LLMRequest(model=self.model, max_tokens=completion_budget(self.provider, 2000), messages=[
            LLMMessage("system", system), LLMMessage("user", canonical_json({"view": view, "task": questions[kind]}))]))
        self._validate_turn_context(session, canon_sha256)
        try:
            simulation = AuthoringCharacterSimulation.model_validate(json.loads(unwrap_json_fence(response.content)))
        except (ValueError, ValidationError) as exc:
            self._record_format_diagnostic(session, exc, canon_sha256, origin="simulate_character")
            raise ModelOutputError("authoring_invalid_character_simulation") from None
        fields = {str(i): option.action + "\n" + option.rationale for i, option in enumerate(simulation.options)}
        validate_generated_output_language(output_language=session.content_language, fields=fields)
        return {"character_id": args["character_id"], "noncanon": True, "simulation": simulation.model_dump(mode="json")}

    def _writers(self, project_id):
        """Resolve current runtime choices; allowlist fields before model-visible output."""
        if self.writer_resolver is None:
            return []
        rows = self.writer_resolver(project_id)
        if not isinstance(rows, list) or len(rows) > 21:
            raise ContractError("authoring_writer_configuration_invalid")
        writers = []
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ContractError("authoring_writer_configuration_invalid")
            if row.get("ready") is not True or not row.get("model"):
                continue
            try:
                choice = AuthoringWriterChoice.model_validate({
                    key: row.get(key, "api_key" if key == "auth_mode" else None)
                    for key in ("profile_id", "profile_name", "model", "auth_mode", "fingerprint")
                } | {"reason": "runtime"})
            except ValidationError:
                raise ContractError("authoring_writer_configuration_invalid") from None
            if choice.profile_id in seen:
                raise ContractError("authoring_writer_configuration_invalid")
            seen.add(choice.profile_id)
            writers.append(choice)
        return writers

    def _navigation(self, project_id, navigation):
        from storygraph.models.authoring import AuthoringNavigationContext
        value = AuthoringNavigationContext.model_validate(navigation).model_dump(mode="json", exclude_none=True)
        if value and self.navigation_validator is None:
            raise ContractError("authoring_navigation_unavailable")
        if self.navigation_validator is not None:
            self.navigation_validator(project_id, value)
        return value

    def _tool(self, session, action, *, reconcile_pin=None, canon_sha256=None, reconcile_card=None,
              quote_registry=None, read_draft_ids=None, navigation_context=None, mcp=None):
        args = action.args
        if action.tool in {"list_writers", "pick_writer"}:
            if reconcile_pin is not None:
                raise ContractError("authoring_writer_choice_not_allowed_in_reconciliation")
            writers = self._writers(session.project_id)
            if action.tool == "list_writers":
                return {"writers": [writer.model_dump(exclude={"reason", "fingerprint"}) for writer in writers],
                        "selection_scope": "current_session", "executes_writer": False}
            selected = next((writer for writer in writers if writer.profile_id == args["profile_id"]), None)
            if selected is None:
                raise ContractError("authoring_writer_not_available")
            validate_generated_output_language(output_language=session.content_language, fields={"reason": args["reason"]})
            session.writer_choice = selected.model_copy(update={"reason": args["reason"]})
            return {"writer_choice": session.writer_choice.model_dump(exclude={"fingerprint"}),
                    "selection_scope": "current_session", "executes_writer": False,
                    "requires_author_writer_action": True}
        if action.tool == "discover_capabilities":
            return {"tools": [{"name": t["name"], "description": t["description"]} for t in mcp.call("tools/list")["tools"]],
                "skills": mcp.call("resources/list")["resources"],
                "limits": ["No automatic canon writes, Draft writes, human adoption or paid workflow starts.",
                           "Navigation never selects prose. Only exact explicit pins authorize source/Draft reads."]}
        if action.tool == "read_skill":
            return mcp.call("resources/read", {"uri": "storygraph://skills/" + args["skill_id"]})
        if action.tool == "inspect_project":
            if self.project_resolver is None:
                return {"available": False, "reason": "project_structure_unavailable", "chapters": []}
            return self.project_resolver(session.project_id, args)
        if action.tool == "inspect_reviews":
            page = self.history(session.project_id, session.id, kind="proposals", query=args["query"], offset=args["offset"], limit=args["limit"])
            selected = self._bounded_rows([(None, {k: v for k, v in row.items() if k not in {"model_execution", "patch"}}) for row in page.pop("records")])
            return {"authoring_proposals": [row for _, row in selected], **page,
                "existing_reviews": self.reviews_resolver(session, args) if self.reviews_resolver else {"available": False},
                "limits": "Existing records only. No new check, approval or freshness certification was performed."}
        if action.tool == "open_workflow":
            explicit_focus = {k: v for k, v in args.items() if k != "target" and v is not None}
            focus = explicit_focus if explicit_focus else dict(navigation_context or {})
            target = args["target"]
            if target in {"writer", "continuity"} and not focus.get("scene_id"):
                return {"navigation": {"target": "manuscript", **self._navigation(session.project_id, focus)},
                    "status": "requires_scene_selection", "executed": False,
                    "note": "Select the exact existing scene before opening its writing or continuity workflow."}
            navigation = {"target": target, **self._navigation(session.project_id, focus)}
            return {"navigation": navigation, "status": "requires_author_action", "executed": False,
                "note": "Open the existing panel and explicitly review/confirm its exact inputs. No writing, adoption, canon commit, settings change or paid workflow was executed."}
        if action.tool == "inspect_sources":
            rows = [("sources", p) for p in session.source_pins] + [("drafts", p) for p in session.draft_pins]
            rows = [(kind, p) for kind, p in rows if args["query"].casefold() in canonical_json(p.model_dump(mode="json")).casefold()]
            selected = rows[args["offset"]:args["offset"] + args["limit"]]
            result = {"sources": [], "drafts": [], **self._page_metadata(len(rows), args["offset"], len(selected))}
            for kind, pin in selected:
                text = self._source(session, pin) if kind == "sources" else self._draft(session, pin).text
                result[kind].append({**pin.model_dump(mode="json"), "total_utf16": len(text.encode("utf-16-le")) // 2})
            return result
        if action.tool in {"read_source", "search_source"}:
            pin, text = self._pinned_text(session, args["kind"], args["id"])
            if action.tool == "search_source":
                result = self._search_source(pin, text, args)
                if quote_registry is not None and reconcile_pin is not None and pin == reconcile_pin and args["kind"] == "draft":
                    for match in result["matches"]:
                        ref = new_id("q")
                        quote_registry[ref] = {"project_id": session.project_id, "session_id": session.id, "turn_id": session.turn_id,
                            "pin": pin.model_copy(deep=True), "start": match["match_start"], "end": match["match_end"], "text": match["matched_text"]}
                        match["quote_ref"] = ref
                return result
            return self._read_source_page(pin, text, args)
        if action.tool == "search_draft_quotes":
            if reconcile_pin is None or reconcile_card is None or quote_registry is None:
                raise ContractError("authoring_draft_evidence_reconciliation_required")
            if read_draft_ids is None or reconcile_pin.draft_id not in read_draft_ids:
                raise ContractError("authoring_reconciliation_read_required")
            self._reconciliation_card(session, reconcile_pin, *reconcile_card)
            draft = self._draft(session, reconcile_pin)
            if draft.discarded:
                raise ContractError("authoring_discarded_draft_not_evidence")
            pages, count, matched_chars = [], 0, 0
            for index, quote in enumerate(args["quotes"]):
                page = self._search_source(reconcile_pin, draft.text, {"query": quote, "offset": 0, "limit": 4})
                matches = []
                for match in page["matches"]:
                    if count >= 24 or matched_chars + len(match["matched_text"]) > 6000:
                        break
                    ref = new_id("q")
                    quote_registry[ref] = {"project_id": session.project_id, "session_id": session.id, "turn_id": session.turn_id,
                        "pin": reconcile_pin.model_copy(deep=True), "start": match["match_start"], "end": match["match_end"], "text": match["matched_text"]}
                    matches.append({"quote_ref": ref, **{key: match[key] for key in ("match_start", "match_end", "matched_text")}})
                    count += 1
                    matched_chars += len(match["matched_text"])
                pages.append({"quote_index": index, "matches": matches, "total_matches": page["total_matches"],
                    "returned_count": len(matches), "more": len(matches) < page["total_matches"], "ambiguous": page["total_matches"] > 1})
            return {"pin": reconcile_pin.model_dump(mode="json"), "offset_unit": "utf16", "quotes": pages,
                    "returned_count": count, "match_limit_per_quote": 4, "total_match_limit": 24, "matched_character_limit": 6000,
                    "more": any(page["more"] for page in pages),
                    "note": "Multiple matches are alternatives, not an automatic selection. Use an exact returned quote_ref; use search_source for later matches."}
        if action.tool == "inspect_canon":
            if self.canon_query_resolver is not None:
                return self.canon_query_resolver(session.project_id, args["query"], args["limit"])
            return self.canon_resolver(session.project_id) if self.canon_resolver else {"canon": [], "note": "No canon context selected; begin with an idea."}
        if action.tool == "inspect_workspace":
            rows = [(key, v.model_dump(mode="json")) for key in ("items", "character_plans", "scene_cards", "reader_records") for v in getattr(session.workspace, key)]
            rows = [(key, value) for key, value in rows if args["query"].casefold() in canonical_json(value).casefold()]
            selected = self._bounded_rows(rows[args["offset"]:args["offset"] + args["limit"]])
            result = {key: [] for key in ("items", "character_plans", "scene_cards", "reader_records")}
            for key, value in selected:
                result[key].append(value)
            return {**result, **self._page_metadata(len(rows), args["offset"], len(selected))}
        if action.tool == "search_history":
            page = self.history(session.project_id, session.id, kind="messages", query=args["query"], offset=args["offset"], limit=args["limit"])
            messages = [{k: v for k, v in m.items() if k != "model_execution"} for m in page.pop("records")]
            selected = self._bounded_rows([(None, m) for m in messages])
            return {"messages": [m for _, m in selected], **page,
                    **self._page_metadata(page["total_matches"], args["offset"], len(selected))}
        if action.tool == "inspect_proposal":
            proposal = next((p for p in session.proposals if p.id == args["proposal_id"]), None)
            if proposal is None:
                proposal = self.get_proposal(session.project_id, session.id, args["proposal_id"])
            value = proposal.model_dump(mode="json", exclude={"model_execution", "patch"})
            operations = [(key, operation) for key, values in proposal.patch.model_dump(mode="json").items() for operation in values]
            selected = self._bounded_rows(operations[args["offset"]:args["offset"] + args["limit"]])
            return {**value, "operations": [{"operation": key, "value": value} for key, value in selected],
                    **self._page_metadata(len(operations), args["offset"], len(selected))}
        if action.tool == "character_view":
            return self.character_view(session, args["character_id"], args.get("card_id"))
        if action.tool == "impact_analysis":
            return self.impact_analysis(session, args.get("item_ids", []) + args.get("card_ids", []))
        if action.tool == "propose_workspace":
            patch = AuthoringPatch.model_validate(args["patch"])
            if reconcile_pin is not None:
                self._validate_reconciliation_patch(session, patch, reconcile_pin, reconcile_card)
            return self._propose(session, patch, args["summary"], canon_sha256=canon_sha256)
        if action.tool == "revise_proposal":
            return self._revise_proposal(session, args["proposal_id"], AuthoringPatch.model_validate(args["patch"]), args["summary"],
                canon_sha256=canon_sha256, reconcile_pin=reconcile_pin, reconcile_card=reconcile_card)
        if action.tool == "propose_draft_evidence":
            return self._propose_draft_evidence(session, args, reconcile_pin, reconcile_card, quote_registry, read_draft_ids, canon_sha256)
        if action.tool == "propose_design_changes":
            if reconcile_pin is not None:
                raise ContractError("authoring_reconciliation_only_evidence")
            return self._propose_design_changes(session, args, canon_sha256)
        if action.tool == "propose_card_review":
            if reconcile_pin is not None:
                raise ContractError("authoring_reconciliation_only_evidence")
            return self._propose_card_review(session, args, canon_sha256)
        reply = args["message"]
        if not isinstance(reply, str) or not reply.strip() or len(reply) > 30000:
            raise ValueError("invalid reply")
        validate_generated_output_language(output_language=session.content_language, fields={"reply": reply})
        accepted, diagnostics = [], []
        for memory in args.get("author_memories", []):
            try:
                from storygraph.models.authoring import AuthoringMemoryRecord
                memory = AuthoringMemoryRecord.model_validate(memory).model_dump(mode="json")
                self.author_context.validate_memory(text=memory["text"],kind=memory["kind"],status=memory["status"],evidence=memory["evidence"])
                author = next((m for m in session.messages if m.id == memory["source_message_id"] and m.role == "author"), None)
                if author is None or memory["evidence"] not in author.content:
                    raise ContractError("authoring_memory_evidence")
                if memory.get("operation", "record") != "record":
                    row = self.author_context.db.execute("SELECT payload FROM author_memories WHERE project_id=? AND id=?", (session.project_id,memory.get("memory_id"))).fetchone()
                    if not row:
                        raise ContractError("authoring_memory_not_found")
                validate_generated_output_language(output_language=session.content_language, fields={"memory": memory["text"]})
                accepted.append(memory)
            except (ContractError,ValueError,KeyError,TypeError):
                diagnostics.append("authoring_memory_skipped_invalid_or_ambiguous")
        return {"reply": reply,"author_memories":accepted,"memory_diagnostics":diagnostics}

    def _propose_draft_evidence(self, session, args, pin, card_binding, registry, read_draft_ids, canon_sha256):
        if pin is None or card_binding is None or registry is None:
            raise ContractError("authoring_draft_evidence_reconciliation_required")
        if read_draft_ids is None or pin.draft_id not in read_draft_ids:
            raise ContractError("authoring_reconciliation_read_required")
        card = self._reconciliation_card(session, pin, *card_binding)
        draft = self._draft(session, pin)
        if draft.discarded:
            raise ContractError("authoring_discarded_draft_not_evidence")
        actors = {card.pov_character_id} | {c.character_id for c in card.writer_policy.characters}
        actors.update(k.character_id for k in card.entry_knowledge + card.acquisitions + card.intended_actions)
        actors.update(c.character_id for c in card.writer_policy.visible_claims if c.character_id)
        actors.discard(None)
        def evidence(ref):
            quote = registry.get(ref)
            if (quote is None or quote["project_id"] != session.project_id or quote["session_id"] != session.id
                or quote["turn_id"] != session.turn_id or quote["pin"] != pin):
                raise ContractError("authoring_draft_evidence_quote_ref_invalid")
            utf16_span(draft.text, quote["start"], quote["end"], quote["text"])
            return AuthoringEvidence(draft=pin, start=quote["start"], end=quote["end"], expected_text=quote["text"])
        acquisitions = list(card.acquisitions)
        for value in args["acquisitions"]:
            if value["character_id"] not in actors:
                raise ContractError("authoring_draft_evidence_actor_scope")
            record = AuthoringCharacterKnowledge(character_id=value["character_id"], text=value["text"], item_id=value.get("item_id"),
                evidence=[evidence(ref) for ref in dict.fromkeys(value["quote_refs"])])
            if record not in acquisitions:
                acquisitions.append(record)
        readers = []
        for value in args["reader_records"]:
            quote = evidence(value["quote_ref"])
            record = ReaderPresented(draft_id=pin.draft_id, version=pin.version, text_sha256=pin.text_sha256,
                start=quote.start, end=quote.end, expected_text=quote.expected_text, presentation=value["presentation"])
            if record not in session.workspace.reader_records and record not in readers:
                readers.append(record)
        cards = [card.model_copy(update={"acquisitions": acquisitions, "status": "proposed"})] if acquisitions != card.acquisitions else []
        if not cards and not readers:
            raise ContractError("authoring_draft_evidence_empty")
        patch = AuthoringPatch(upsert_scene_cards=cards, add_reader_records=readers)
        self._validate_reconciliation_patch(session, patch, pin, card_binding)
        return self._propose(session, patch, args["summary"], canon_sha256=canon_sha256)

    @staticmethod
    def _page_metadata(total, offset, count):
        more = offset + count < total
        return {"total_matches": total, "returned_count": count, "offset": offset, "more": more,
                "next_offset": offset + count if more else None, "complete": not more and offset == 0}

    @staticmethod
    def _bounded_rows(rows):
        chosen, size = [], 0
        for key, value in rows:
            length = len(canonical_json(value))
            if chosen and size + length > 16000:
                break
            if length > 24000:
                raise ContractError("authoring_record_requires_smaller_scope")
            chosen.append((key, value))
            size += length
        return chosen

    def _pinned_text(self, session, kind, source_id):
        pin = next((p for p in session.source_pins if p.id == source_id and p.kind == kind), None)
        if pin:
            return pin, self._source(session, pin)
        pin = next((p for p in session.draft_pins if p.draft_id == source_id and kind == "draft"), None)
        if pin:
            return pin, self._draft(session, pin).text
        raise ContractError("authoring_source_not_pinned")

    @staticmethod
    def _read_source_page(pin, text, args):
        encoded = text.encode("utf-16-le")
        total = len(encoded) // 2
        start = args.get("start")
        end = args.get("end")
        if start is None:
            start, end = 0, min(total, 12000)
            # Default pagination never bisects a supplementary character.
            if end < total and 0xD800 <= int.from_bytes(encoded[(end-1)*2:end*2], "little") <= 0xDBFF:
                end -= 1
        if start > total or end > total or end < start:
            raise ContractError("authoring_source_range_invalid")
        try:
            selected = encoded[start * 2:end * 2].decode("utf-16-le")
        except UnicodeError:
            raise ContractError("authoring_source_range_splits_character") from None
        return {"pin": pin.model_dump(mode="json"), "text": selected, "offset_unit": "utf16",
                "start": start, "end": end, "total_utf16": total,
                "more": end < total, "next_start": end if end < total else None,
                "complete": start == 0 and end == total}

    @staticmethod
    def _search_source(pin, text, args):
        query, positions, cursor = args["query"], [], 0
        while True:
            found = text.find(query, cursor)
            if found < 0:
                break
            positions.append(found)
            cursor = found + len(query)
        matches = []
        returned_chars = 0
        for found in positions[args["offset"]:args["offset"] + args["limit"]]:
            start, end = max(0, found - 100), min(len(text), found + len(query) + 300)
            if matches and returned_chars + end - start > 12000:
                break
            returned_chars += end - start
            matches.append({"start": len(text[:start].encode("utf-16-le")) // 2,
                            "end": len(text[:end].encode("utf-16-le")) // 2, "text": text[start:end],
                            "match_start": len(text[:found].encode("utf-16-le")) // 2,
                            "match_end": len(text[:found + len(query)].encode("utf-16-le")) // 2,
                            "matched_text": query})
        next_offset = args["offset"] + len(matches)
        return {"pin": pin.model_dump(mode="json"), "query": query, "offset_unit": "utf16", "matches": matches,
                "total_matches": len(positions), "total_utf16": len(text.encode("utf-16-le")) // 2,
                "more": next_offset < len(positions), "next_offset": next_offset if next_offset < len(positions) else None}

    def _validate_reconciliation_patch(self, session, patch, pin, card_binding=None):
        if (patch.upsert_items or patch.upsert_character_plans or patch.remove_item_ids
            or patch.remove_character_ids or patch.remove_card_ids or patch.remove_reader_records):
            raise ContractError("authoring_reconciliation_only_evidence")
        for record in patch.add_reader_records:
            if (record.draft_id, record.version, record.text_sha256) != (pin.draft_id, pin.version, pin.text_sha256):
                raise ContractError("authoring_reconciliation_wrong_draft")
        old_cards = {c.id: c for c in session.workspace.scene_cards}
        if patch.upsert_scene_cards and card_binding is None:
            raise ContractError("authoring_reconciliation_card_required")
        if card_binding is not None:
            self._reconciliation_card(session, pin, *card_binding)
        for card in patch.upsert_scene_cards:
            old = old_cards.get(card.id)
            if old is None or card.scene_id != pin.scene_id or card.id != card_binding[0]:
                raise ContractError("authoring_reconciliation_card_scope")
            # Reconciliation can append evidence acquisitions, not rewrite the scene intention.
            excluded = {"acquisitions", "status", "version"}
            if card.model_dump(exclude=excluded) != old.model_dump(exclude=excluded):
                raise ContractError("authoring_reconciliation_only_evidence")
            if any(a not in card.acquisitions for a in old.acquisitions):
                raise ContractError("authoring_reconciliation_cannot_remove_acquisition")
            for acquisition in card.acquisitions:
                if acquisition not in old.acquisitions and (not acquisition.evidence or any(e.draft != pin for e in acquisition.evidence)):
                    raise ContractError("authoring_reconciliation_requires_quote")

    def review(self, *, project_id, session_id, expected_version, proposal_id, decision, reviewer="author", edited_patch=None):
        session = self._cas(project_id, session_id, expected_version)
        if session.turn_status == "running":
            raise ContractError("authoring_turn_running")
        if decision not in {"adopted", "rejected"} or not reviewer.strip():
            raise ContractError("authoring_invalid_review")
        proposal = next((p for p in session.proposals if p.id == proposal_id), None)
        if proposal is None or proposal.status != "pending":
            raise ContractError("authoring_proposal_not_pending")
        if decision == "adopted" and proposal.base_workspace_sha256 != workspace_hash(session.workspace):
            raise ContractError("authoring_workspace_changed")
        if decision == "adopted":
            self._validate_pins(session)
            if proposal.inputs_sha256 != authoring_inputs_hash(session):
                raise ContractError("authoring_proposal_inputs_changed")
            if proposal.canon_sha256 != self._canon_digest(project_id):
                raise ContractError("authoring_proposal_canon_changed")
            if edited_patch is not None:
                # Recalculate impacts for the actual author edit, never reuse model diff metadata.
                self._propose(session, AuthoringPatch.model_validate(edited_patch), proposal.summary)
                recalculated = session.proposals.pop()
                proposal.affected_card_ids = recalculated.affected_card_ids
                proposal.affected_scene_ids = recalculated.affected_scene_ids
                patch = recalculated.patch
            else:
                patch = proposal.patch
            workspace = apply_authoring_patch(session.workspace, patch)
            self._validate_workspace(session, workspace)
            directly_reviewed = {c.id for c in patch.upsert_scene_cards}
            cards = [c.model_copy(update={"status": "approved" if c.id in directly_reviewed else "proposed",
                                          "version": c.version + (1 if c.id not in directly_reviewed and c.status == "approved" else 0)})
                     if c.id in proposal.affected_card_ids else c for c in workspace.scene_cards]
            session.workspace = workspace.model_copy(update={"scene_cards": cards})
            proposal.patch = patch
        proposal.status, proposal.reviewed_by, proposal.reviewed_at = decision, reviewer, utc_now()
        if decision == "adopted":
            self._validate_turn_context(session, proposal.canon_sha256)
        return self._save(session)

    def compile_card(self, *, project_id, session_id, card_id, expected_version=None):
        session = self.get(project_id, session_id)
        if expected_version is not None and session.version != expected_version:
            raise ContractError("authoring_stale_version")
        card = next((c for c in session.workspace.scene_cards if c.id == card_id), None)
        if card is None or card.status != "approved" or card.scene_id is None:
            raise ContractError("authoring_card_not_approved_or_unbound")
        # Only the explicitly approved disclosure policy crosses the writer boundary.
        self._validate_reader_records(session, card.writer_policy.reader_presented)
        return card.writer_policy

    @staticmethod
    def _reconciliation_card(session, pin, card_id, card_version):
        if (not isinstance(card_id, str) or not card_id or type(card_version) is not int
            or card_version < 1):
            raise ContractError("authoring_reconciliation_card_binding_required")
        card = next((c for c in session.workspace.scene_cards if c.id == card_id), None)
        if card is None or card.scene_id != pin.scene_id or card.version != card_version:
            raise ContractError("authoring_reconciliation_card_stale_or_scope")
        return card

    def reconcile(self, *, project_id, session_id, expected_version, draft_pin, max_steps=6, card_id=None, card_version=None):
        session = self._cas(project_id, session_id, expected_version)
        if session.turn_status == "running":
            raise ContractError("authoring_turn_running")
        pin = AuthoringDraftPin.model_validate(draft_pin)
        card_binding = None
        if card_id is not None or card_version is not None:
            self._reconciliation_card(session, pin, card_id, card_version)
            card_binding = (card_id, card_version)
        if self._draft(session, pin).discarded:
            raise ContractError("authoring_discarded_draft_not_current_reconciliation")
        if pin not in session.draft_pins:
            session.draft_pins.append(pin)
        # Pin exactly this saved version before the model can propose evidence records.
        session = self._save(session)
        instruction = ("核对刚保存的草稿 " if session.content_language == "zh-CN" else "Reconcile the exact saved Draft ") + pin.draft_id
        instruction += ("；必须先读取，随后仅依据原文UTF-16引文提出 reader_records 与人物 acquisitions 的设计提案；意图不算证据，不要改动其他设定。" if session.content_language == "zh-CN" else "; read it first, then propose only reader_records and character acquisitions supported by exact UTF-16 quotes. Intentions are not evidence. Preserve other design.")
        return self.turn(project_id=project_id, session_id=session_id, expected_version=session.version, message=instruction,
                         max_steps=max_steps, _reconcile_pin=pin, _reconcile_card=card_binding)

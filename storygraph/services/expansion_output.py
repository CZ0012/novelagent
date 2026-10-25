"""Creative expansion parsing with server-owned immutable positional skeletons."""

from copy import deepcopy
import json
from typing import Literal

from pydantic import Field, create_model

from storygraph.models.longform import ChapterPlan, Expansion, ScenePlan, StrictModel
from storygraph.core.errors import GraphStoreError


MAX_PRIOR_OUTCOME_SCENES = 2000
MAX_PRIOR_OUTCOME_CHARS = 120000


def expansion_volume_progress(configuration, request):
    """Explicit planning position, never a claim that prose/canon is complete."""
    start = request.chapter_start
    end = start+request.chapter_count-1
    total = configuration.chapters_per_volume
    if not (1 <= request.volume_index <= configuration.volume_count and 1 <= start <= end <= total):
        raise ValueError("Expansion progress exceeds its frozen whole-book grid.")
    opening, final = start == 1, end == total
    return {"planning_only": True, "volume_index": request.volume_index,
        "total_volumes": configuration.volume_count, "chapters_per_volume": total,
        "scenes_per_chapter": configuration.scenes_per_chapter,
        "batch_chapter_start": start, "batch_chapter_end": end,
        "batch_chapter_indices": list(range(start, end+1)),
        "earlier_planned_chapter_indices": list(range(1, start)),
        "remaining_chapter_indices": list(range(end+1, total+1)),
        "is_opening_batch": opening, "is_final_batch": final,
        "batch_role": "complete_volume" if opening and final else "opening" if opening else "finale" if final else "progression",
        "reserve_main_resolution_for_final_batch": not final}


def recent_planned_scene_outcomes(scenes, limit=12):
    """Exact earlier plan anchors, not inferred dates or realized scene facts."""
    return [{"id": scene_id, "summary": node.properties.get("summary"),
             "outcome": node.properties.get("outcome"),
             "timeline_position": node.properties.get("timeline_position")}
            for scene_id, node in sorted(scenes.items())[-limit:]]


def prior_planned_scene_outcome_ledger(scenes, *, identity_maps=None):
    """Exact all-prior outcome ledger; no summaries, state inference or truncation."""
    if len(scenes) > MAX_PRIOR_OUTCOME_SCENES:
        raise GraphStoreError("planning_context_budget", "Prior planned outcome ledger exceeds its bounded scope.")
    rows = []
    for scene_id, node in sorted(scenes.items()):
        row = {"id": scene_id, "timeline_position": node.properties.get("timeline_position"), "outcome": node.properties.get("outcome")}
        for field in ("pov_character_id", "location_id"):
            value = node.properties.get(field)
            if identity_maps is not None and value is not None:
                if value not in identity_maps[field]:
                    raise GraphStoreError("planning_context_incomplete", "Prior planned entity reference is outside the pinned blueprint.")
                value = identity_maps[field][value]
            row[field] = value
        rows.append(row)
    ledger = {"semantics": "proposed_scene_outcomes_not_realized_facts", "entity_reference_scope": "blueprint_local_ids", "scenes": rows}
    if len(json.dumps(ledger, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) > MAX_PRIOR_OUTCOME_CHARS:
        raise GraphStoreError("planning_context_budget", "Prior planned outcome ledger exceeds its bounded size.")
    return ledger


def _fields(model, excluded):
    return {name: (field.annotation, deepcopy(field)) for name, field in model.model_fields.items() if name not in excluded}


def creative_expansion_model(payload):
    """Advertise authored fields only, with request-specific counts/ref enums."""
    budgets = payload["chapter_budgets"]
    if not 1 <= len(budgets) <= 5 or not budgets[0]["scenes"]:
        raise ValueError("Invalid frozen expansion skeleton.")
    scene_count = len(budgets[0]["scenes"])
    if any(len(chapter["scenes"]) != scene_count for chapter in budgets):
        raise ValueError("Inconsistent frozen expansion skeleton.")
    entities = payload["blueprint"]["entities"]
    characters = tuple(entity["id"] for entity in entities if entity["kind"] == "Character")
    locations = tuple(entity["id"] for entity in entities if entity["kind"] == "Location")
    if not characters or not locations:
        raise ValueError("Expansion requires explicit Character and Location references.")
    char_ref = Literal[characters]
    location_ref = Literal[locations]
    scene_fields = _fields(ScenePlan, {"id", "target_length"})
    scene_fields["pov_character_id"] = (char_ref, Field(description="Exact local Character ID from the blueprint."))
    scene_fields["location_id"] = (location_ref, Field(description="Exact local Location ID from the blueprint."))
    scene_fields["required_characters"] = (list[char_ref], Field(min_length=1, max_length=20))
    volume = payload["request"]["volume_index"]
    for key, volume_key in (("foreshadowing_seed_ids", "seed_volume"), ("foreshadowing_payoff_ids", "payoff_volume")):
        allowed = tuple(clue["id"] for clue in payload["blueprint"]["foreshadowing"] if clue[volume_key] == volume)
        scene_fields[key] = ((list[Literal[allowed]], Field(default_factory=list, max_length=30)) if allowed
                             else (list[str], Field(default_factory=list, max_length=0)))
    scene_model = create_model("ExpansionSceneContent", __base__=StrictModel, **scene_fields)
    chapter_fields = _fields(ChapterPlan, {"index", "target_length", "scenes"})
    chapter_fields["scenes"] = (list[scene_model], Field(min_length=scene_count, max_length=scene_count))
    chapter_model = create_model("ExpansionChapterContent", __base__=StrictModel, **chapter_fields)
    return create_model("ExpansionCreativeContent", __base__=StrictModel,
        chapters=(list[chapter_model], Field(min_length=len(budgets), max_length=len(budgets))))


def parse_expansion_output(raw, payload, creative_model=None):
    """No fuzzy repair: classify one complete format, never renumber legacy IDs."""
    creative_model = creative_model or creative_expansion_model(payload)
    budgets = payload["chapter_budgets"]
    request = payload["request"]
    if isinstance(raw, dict) and set(raw) == {"chapters"}:
        authored = creative_model.model_validate(raw)
        chapters = []
        for chapter, skeleton in zip(authored.chapters, budgets, strict=True):
            scenes = [ScenePlan(**scene.model_dump(), id=slot["id"], target_length=slot["target_length"])
                      for scene, slot in zip(chapter.scenes, skeleton["scenes"], strict=True)]
            chapters.append(ChapterPlan(**chapter.model_dump(exclude={"scenes"}), index=skeleton["index"],
                target_length=skeleton["target_length"], scenes=scenes))
        return Expansion(volume_index=request["volume_index"], chapter_start=request["chapter_start"], chapters=chapters)
    legacy = Expansion.model_validate(raw)
    if (legacy.volume_index != request["volume_index"] or legacy.chapter_start != request["chapter_start"]
            or len(legacy.chapters) != len(budgets)):
        raise ValueError("Legacy expansion differs from frozen server skeleton.")
    for chapter, skeleton in zip(legacy.chapters, budgets, strict=True):
        if (chapter.index != skeleton["index"] or chapter.target_length != skeleton["target_length"]
                or len(chapter.scenes) != len(skeleton["scenes"])):
            raise ValueError("Legacy chapter differs from frozen server skeleton.")
        for scene, slot in zip(chapter.scenes, skeleton["scenes"], strict=True):
            if scene.id != slot["id"] or scene.target_length != slot["target_length"]:
                raise ValueError("Legacy scene differs from frozen server skeleton.")
    return legacy

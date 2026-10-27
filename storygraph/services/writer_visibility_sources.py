"""Same-workspace source validation for local Writer permissions, not canon changes."""
from storygraph.core.errors import ContractError
from storygraph.services.project_style import resolve_project_style
from storygraph.services.writer_visibility import validate_reader_presented


def validate_writer_policy_sources(graph, drafts, project_id, spec):
    if spec is None:
        return
    actor_ids = [x.character_id for x in spec.characters]
    actor_ids.extend(x.character_id for x in spec.visible_claims if x.character_id)
    for ref in actor_ids:
        node = graph.get_node(ref)
        if node.type != "Character" or node.status != "CANON" or node.properties.get("project_id") != project_id:
            raise ContractError("writer_visibility_character_scope")
    if spec.access_mode != "pov" and any(c.presentation == "belief" for c in spec.visible_claims):
        raise ContractError("writer_visibility_belief_requires_pov")
    if spec.access_mode != "omniscient" and any(c.presentation == "narrator_fact" for c in spec.visible_claims):
        raise ContractError("writer_visibility_narrator_permission_required")
    validate_reader_presented(project_id, spec.reader_presented, drafts.get_draft)
    if spec.writer_style_origin == "profile_projection":
        profile = resolve_project_style(graph, project_id)
        if profile.get("id") != spec.writer_style_source_profile_id or profile.get("sha256") != spec.writer_style_source_profile_sha256:
            raise ContractError("writer_visibility_style_source_stale")

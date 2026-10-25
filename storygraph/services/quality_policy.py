"""Shared opt-in policy: generated prose is reviewed as a Proposal first."""

from storygraph.core.errors import GraphStoreError
from storygraph.models.project import localized
from storygraph.services.project_language import resolve_project_output_language


def requires_semantic_review(graph, project_id: str) -> bool:
    project = graph.get_node(project_id)
    if project.type != "Project":
        raise GraphStoreError("not_found", "Requested project is unavailable.")
    return bool(project.properties.get("require_semantic_review"))


def require_direct_generation_allowed(graph, project_id: str) -> None:
    if requires_semantic_review(graph, project_id):
        raise GraphStoreError("generation_review_required", localized(
            resolve_project_output_language(graph, project_id),
            zh="此项目要求先生成协作草稿，审阅通过后再采用；不能直接生成并保存正文。",
            en="Generate a proposal, review it, then adopt it; this project blocks direct generated Draft writes.",
        ))


def require_workflow_output_allowed(graph, project_id: str, output_target: str) -> None:
    if output_target != "proposal_workspace":
        require_direct_generation_allowed(graph, project_id)


def require_composition_application_allowed(graph, project_id: str) -> None:
    if requires_semantic_review(graph, project_id):
        raise GraphStoreError("generation_review_required", localized(
            resolve_project_output_language(graph, project_id),
            zh="此项目要求逐场景审阅正文。请先应用不含正文的长篇规划，再生成、审阅并采用场景协作草稿。",
            en="This project requires scene-level prose review. Apply a prose-free long-form plan, then generate, review and adopt scene proposals.",
        ))

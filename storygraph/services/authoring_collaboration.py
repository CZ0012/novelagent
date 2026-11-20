"""Per-turn author intent controls for the Main Agent's tool registry."""
from typing import Literal, get_args

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringToolAction


CollaborationMode = Literal["collaborate", "discuss", "review"]

# New tools require an explicit decision before they are available in read-only modes.
_READ_ONLY = frozenset({
    "inspect_sources", "read_source", "search_source", "search_draft_quotes",
    "inspect_canon", "inspect_workspace", "search_history", "inspect_proposal",
    "character_view", "simulate_character", "impact_analysis",
    "discover_capabilities", "read_skill", "inspect_project", "inspect_reviews",
    "open_workflow", "finish",
})


def allowed_authoring_tools(mode: CollaborationMode) -> frozenset[str]:
    registered = frozenset(get_args(AuthoringToolAction.model_fields["tool"].annotation))
    if mode == "collaborate":
        return registered
    if mode in ("discuss", "review"):
        return _READ_ONLY.intersection(registered)
    raise ContractError("authoring_unknown_collaboration_mode")


def validate_authoring_mode_tool(mode: CollaborationMode, tool: str) -> None:
    if tool not in allowed_authoring_tools(mode):
        raise ContractError("authoring_tool_not_allowed_in_mode")

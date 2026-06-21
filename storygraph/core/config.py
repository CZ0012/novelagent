"""Local runtime settings for StoryGraph MVP commands."""

from __future__ import annotations

import os
from pathlib import Path


class StoryGraphSettings:
    def __init__(self, workspace_dir: str | Path | None = None) -> None:
        root = Path(
            workspace_dir
            or os.environ.get("STORYGRAPH_HOME")
            or Path.cwd() / ".storygraph"
        )
        self.workspace_dir = root
        self.graph_path = root / "graph.json"
        self.draft_store_path = root / "drafts.sqlite"
        self.candidate_store_path = root / "candidates.sqlite"
        self.proposal_store_path = root / "proposals.sqlite"
        self.workflow_store_path = root / "workflows.sqlite"
        self.workflow_checkpoint_path = root / "langgraph_checkpoints.sqlite"
        self.style_sample_store_path = root / "style_samples.sqlite"
        self.agent_config_path = root / "agent_config.json"
        self.workflow_runtime = os.environ.get("STORYGRAPH_WORKFLOW_RUNTIME", "local").lower()
        self.scene_writer = os.environ.get("STORYGRAPH_SCENE_WRITER", "rule_based").lower()
        self.llm_base_url = os.environ.get("STORYGRAPH_LLM_BASE_URL") or os.environ.get(
            "OPENAI_BASE_URL",
            "",
        )
        self.llm_api_key = os.environ.get("STORYGRAPH_LLM_API_KEY") or os.environ.get(
            "OPENAI_API_KEY",
            "",
        )
        self.llm_model = os.environ.get("STORYGRAPH_LLM_MODEL", "deepseek-chat")
        self.llm_timeout_seconds = float(os.environ.get("STORYGRAPH_LLM_TIMEOUT_SECONDS", "60"))
        self.llm_json_mode = os.environ.get("STORYGRAPH_LLM_JSON_MODE", "1").lower() not in {
            "0",
            "false",
            "no",
        }
        self.graph_backend_explicit = "STORYGRAPH_GRAPH_BACKEND" in os.environ
        self.graph_backend = os.environ.get("STORYGRAPH_GRAPH_BACKEND", "json").lower()
        self.neo4j_uri = os.environ.get("STORYGRAPH_NEO4J_URI")
        self.neo4j_user = os.environ.get("STORYGRAPH_NEO4J_USER")
        self.neo4j_password = os.environ.get("STORYGRAPH_NEO4J_PASSWORD")
        self.neo4j_database = os.environ.get("STORYGRAPH_NEO4J_DATABASE")

    def ensure_workspace(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

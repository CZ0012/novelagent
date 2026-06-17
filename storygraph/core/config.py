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
        self.workflow_store_path = root / "workflows.sqlite"

    def ensure_workspace(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)


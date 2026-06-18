"""Persistent FastAPI app entrypoint for the packaged desktop runtime."""

from __future__ import annotations

import os
from pathlib import Path

from apps.api.main import create_app
from storygraph.core.config import StoryGraphSettings


def desktop_settings() -> StoryGraphSettings:
    workspace = os.environ.get("STORYGRAPH_HOME")
    if not workspace:
        app_data = os.environ.get("LOCALAPPDATA") or str(Path.home())
        workspace = str(Path(app_data) / "StoryGraph Agent" / "workspace")
    settings = StoryGraphSettings(workspace)
    settings.graph_backend = "json"
    settings.graph_backend_explicit = True
    settings.ensure_workspace()
    return settings


app = create_app(desktop_settings())

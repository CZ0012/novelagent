"""Desktop backend server executable entrypoint."""

from __future__ import annotations

import uvicorn
import argparse

from apps.api.desktop import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local StoryGraph backend.")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args()
    if not 1 <= options.port <= 65535:
        parser.error("port must be between 1 and 65535")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=options.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

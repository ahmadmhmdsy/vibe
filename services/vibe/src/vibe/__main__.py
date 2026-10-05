
import logging

import uvicorn

from vibe.api.app import create_app
from vibe.config import Settings
from vibe.logging_setup import configure_logging


def main() -> None:
    """Build the app from the environment and serve it.

    `python -m vibe` used to hard-code 127.0.0.1:7321, so VIBE_HOST and
    VIBE_PORT were silently ignored, and create_app() ran at import time —
    opening the workspace and its databases before anything asked it to.
    """
    # Configure before uvicorn: its dictConfig leaves existing loggers
    # alone, so this handler survives and the app's own records are visible.
    level = configure_logging()
    settings = Settings.from_env()
    logging.getLogger(__name__).info(
        "vibe serving on http://%s:%s (log level %s, workspace %s)",
        settings.host, settings.port, logging.getLevelName(level), settings.workspace_dir,
    )
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()

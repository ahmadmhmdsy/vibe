from dataclasses import dataclass, field
from pathlib import Path
import os

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


@dataclass
class Settings:
    workspace_dir: Path = field(default_factory=lambda: Path.home() / "vibe-workspaces")
    max_fix_iterations: int = 3
    session_token_budget: int | None = None
    dev_server_idle_timeout_min: int = 30
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: DEFAULT_CORS_ORIGINS.split(","))
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    opencode_api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            workspace_dir=Path(os.environ.get("VIBE_WORKSPACE_DIR", Path.home() / "vibe-workspaces")),
            max_fix_iterations=int(os.environ.get("VIBE_MAX_FIX_ITERATIONS", "3")),
            session_token_budget=int(os.environ["VIBE_SESSION_TOKEN_BUDGET"]) if os.environ.get("VIBE_SESSION_TOKEN_BUDGET") else None,
            dev_server_idle_timeout_min=int(os.environ.get("VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN", "30")),
            port=int(os.environ.get("VIBE_PORT", "8000")),
            cors_origins=[o.strip() for o in os.environ.get("VIBE_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()],
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            opencode_api_key=os.environ.get("OPENCODE_API_KEY"),
        )

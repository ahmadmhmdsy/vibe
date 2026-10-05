import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def _load_dotenv() -> None:
    """Load environment variables from a .env file if it exists.

    Searches for .env in the current directory and parent directories
    (up to 3 levels). Does not overwrite existing environment variables.
    """
    current = Path.cwd()
    for _ in range(4):  # current + 3 parents
        env_file = current / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    if key and key not in os.environ:
                        os.environ[key] = value
            break
        parent = current.parent
        if parent == current:
            break
        current = parent


_load_dotenv()


@dataclass
class Settings:
    workspace_dir: Path = field(default_factory=lambda: Path.home() / "vibe-workspaces")
    max_fix_iterations: int = 3
    session_token_budget: int | None = None
    dev_server_idle_timeout_min: int = 30
    browser_headless: bool = True
    browser_timeout_ms: int = 10_000
    host: str = "127.0.0.1"
    port: int = 7321
    # Which Authenticator the container builds. Only "loopback" exists today;
    # the knob is the seam a future token authenticator plugs into.
    auth_mode: str = "loopback"
    cors_origins: list[str] = field(default_factory=lambda: DEFAULT_CORS_ORIGINS.split(","))
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    opencode_api_key: str | None = None

    def __post_init__(self) -> None:
        """Normalise the workspace root to one absolute, expanded path.

        `VIBE_WORKSPACE_DIR=~/vibe-workspaces` used to be taken literally, so an
        install could end up with its sessions.db and every generated project
        inside a directory *named* `~`, resolved against the process's current
        working directory. Launching from a different directory then presented an
        empty install while the real data sat unreachable next door. Resolving
        once here means every consumer sees the same absolute path.
        """
        self.workspace_dir = Path(self.workspace_dir).expanduser().resolve()
        self.host = self.host or "127.0.0.1"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            # `or` rather than a get() default: an empty VIBE_WORKSPACE_DIR would
            # otherwise resolve to Path("") — the current directory.
            workspace_dir=Path(os.environ.get("VIBE_WORKSPACE_DIR") or (Path.home() / "vibe-workspaces")),
            host=os.environ.get("VIBE_HOST", "127.0.0.1"),
            max_fix_iterations=int(os.environ.get("VIBE_MAX_FIX_ITERATIONS", "3")),
            session_token_budget=int(os.environ["VIBE_SESSION_TOKEN_BUDGET"]) if os.environ.get("VIBE_SESSION_TOKEN_BUDGET") else None,
            dev_server_idle_timeout_min=int(os.environ.get("VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN", "30")),
            browser_headless=os.environ.get("VIBE_BROWSER_HEADLESS", "1").lower() not in ("0", "false", "no"),
            browser_timeout_ms=int(os.environ.get("VIBE_BROWSER_TIMEOUT_MS", "10000")),
            port=int(os.environ.get("VIBE_PORT", "7321")),
            auth_mode=os.environ.get("VIBE_AUTH_MODE", "loopback"),
            cors_origins=[o.strip() for o in os.environ.get("VIBE_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()],
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            opencode_api_key=os.environ.get("OPENCODE_API_KEY"),
        )

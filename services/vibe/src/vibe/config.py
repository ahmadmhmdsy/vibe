import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

#: Hosts that bind only this machine. Anything else -- 0.0.0.0, ::, a LAN
#: address -- accepts peers from the network, so it needs a shared secret.
_LOOPBACK_BINDS = frozenset({"127.0.0.1", "::1", "localhost"})

#: VIBE_LOG_FILE values that mean "do not write a log file". An *unset*
#: variable is not one of them: the documented default is a rotating file under
#: the workspace, so only a deliberate off value may disable it.
_LOG_OFF_VALUES = {"0", "false", "no", "none", "off"}


def default_static_dir() -> Path:
    """Where `pnpm run build` puts the SPA in this checkout.

    Resolved from this file rather than the current directory, so
    `python -m vibe` finds the build no matter where it was started from.
    A packaged install sets VIBE_STATIC_DIR instead.
    """
    return Path(__file__).resolve().parents[4] / "apps" / "vibe" / "dist"


def local_app_data() -> Path | None:
    """The per-user application-data directory, or None off Windows.

    This lives here because config.py is the only module allowed to read the
    environment (guardrail L-6). Machine discovery needs LOCALAPPDATA before a
    Settings object exists -- the preflight doctor runs on a machine where the
    app cannot start at all -- so it asks for the directory by name instead of
    reading the variable itself, and a hidden variable cannot become
    configuration that no installer can record.
    """
    if os.name != "nt":
        return None
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) if local else None


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
    #: How many prior messages to replay to the model. 0 disables history (the
    #: pre-2026-10-11 behaviour); the cap keeps a long session from resending its
    #: whole transcript on every turn.
    history_messages: int = 24
    #: Extra instructions prepended to every run. Empty means the built-in prompt
    #: in vibe/prompts.py; VIBE_SYSTEM_PROMPT replaces it.
    system_prompt: str = ""
    #: How long a deleted workspace stays recoverable under <workspace_dir>/.trash.
    #: 0 disables the sweep entirely (deleted workspaces are then kept forever,
    #: the pre-2026-10-11 behaviour).
    trash_retention_days: int = 14
    dev_server_idle_timeout_min: int = 30
    browser_headless: bool = True
    browser_timeout_ms: int = 10_000
    host: str = "127.0.0.1"
    port: int = 7321
    #: "dev" serves the API alone and lets Vite own the frontend; "prod" serves
    #: the built SPA and the API from this one process and port (R5-T3). The
    #: default is "dev" so a bare `python -m vibe` never dies because nobody has
    #: run `pnpm run build` yet; start.bat selects "prod" for the one-click path.
    mode: Literal["dev", "prod"] = "dev"
    #: The built SPA. None means "this checkout's apps/vibe/dist".
    static_dir: Path | None = None
    # Which Authenticator the container builds. __post_init__ sets this to
    # "token" when auth_token is present; the knob is also the seam a future
    # authenticator plugs into.
    auth_mode: str = "loopback"
    #: Shared-secret bearer token (VIBE_AUTH_TOKEN). Setting it lets the API be
    #: reached beyond this machine: the container builds a TokenAuthenticator and
    #: remote peers must present the token. Loopback stays trusted.
    auth_token: str | None = None
    cors_origins: list[str] = field(default_factory=lambda: DEFAULT_CORS_ORIGINS.split(","))
    #: Level for the console and file handlers; VIBE_LOG_LEVEL overrides it.
    log_level: str = "INFO"
    #: The rotating log file. None means the default under the workspace
    #: (<workspace_dir>/logs/vibe.log), so "send me the log" names one path
    #: whether or not the user ever set an environment variable.
    log_file: Path | None = None
    #: VIBE_LOG_FILE=off (or none/false/0) turns the file handler off. The
    #: console handler always stays, so a start failure is still visible.
    log_to_file: bool = True
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
        # P5: a non-loopback bind used to be a silent footgun -- the API became
        # reachable from the network with only LoopbackAuthenticator (which
        # refuses remote peers) in the way. A shared secret is now required
        # before the API is exposed off-machine, and setting one selects token
        # auth. Fail-closed: a network bind with no token is a startup error.
        self.auth_token = (self.auth_token or "").strip() or None
        if self.auth_token is not None:
            self.auth_mode = "token"
        if self.auth_mode == "token" and self.auth_token is None:
            raise ValueError("VIBE_AUTH_MODE=token requires VIBE_AUTH_TOKEN to be set")
        if self.auth_token is None and self.host not in _LOOPBACK_BINDS:
            raise ValueError(
                f"VIBE_HOST={self.host!r} accepts connections beyond this machine, "
                "so it needs VIBE_AUTH_TOKEN set; refusing to expose the API unprotected"
            )
        # A typo in VIBE_MODE used to be indistinguishable from "dev": the app
        # started in the mode nobody asked for and served the wrong thing.
        if self.mode not in ("dev", "prod"):
            raise ValueError(f"VIBE_MODE must be 'dev' or 'prod', not {self.mode!r}")
        self.static_dir = (
            default_static_dir() if self.static_dir is None else Path(self.static_dir).expanduser().resolve()
        )
        # Logging to a file is on by default, under the workspace: a user who
        # is asked "send me the log" must not have to hunt in a console that
        # was already closed. log_to_file=False (VIBE_LOG_FILE=off) is the way
        # out, and it is the only way log_file becomes None after this point.
        if self.log_to_file:
            self.log_file = (
                self.workspace_dir / "logs" / "vibe.log"
                if self.log_file is None
                else Path(self.log_file).expanduser().resolve()
            )
        else:
            self.log_file = None

    @classmethod
    def from_env(cls) -> "Settings":
        raw_log_file = (os.environ.get("VIBE_LOG_FILE") or "").strip()
        return cls(
            # `or` rather than a get() default: an empty VIBE_WORKSPACE_DIR would
            # otherwise resolve to Path("") — the current directory.
            workspace_dir=Path(os.environ.get("VIBE_WORKSPACE_DIR") or (Path.home() / "vibe-workspaces")),
            host=os.environ.get("VIBE_HOST", "127.0.0.1"),
            max_fix_iterations=int(os.environ.get("VIBE_MAX_FIX_ITERATIONS", "3")),
            session_token_budget=int(os.environ["VIBE_SESSION_TOKEN_BUDGET"])
            if os.environ.get("VIBE_SESSION_TOKEN_BUDGET")
            else None,
            history_messages=int(os.environ.get("VIBE_HISTORY_MESSAGES", "24")),
            system_prompt=os.environ.get("VIBE_SYSTEM_PROMPT", ""),
            trash_retention_days=int(os.environ.get("VIBE_TRASH_RETENTION_DAYS", "14")),
            dev_server_idle_timeout_min=int(os.environ.get("VIBE_DEV_SERVER_IDLE_TIMEOUT_MIN", "30")),
            browser_headless=os.environ.get("VIBE_BROWSER_HEADLESS", "1").lower() not in ("0", "false", "no"),
            browser_timeout_ms=int(os.environ.get("VIBE_BROWSER_TIMEOUT_MS", "10000")),
            port=int(os.environ.get("VIBE_PORT", "7321")),
            mode=os.environ.get("VIBE_MODE", "dev").strip().lower(),
            static_dir=Path(os.environ["VIBE_STATIC_DIR"]) if os.environ.get("VIBE_STATIC_DIR") else None,
            auth_mode=os.environ.get("VIBE_AUTH_MODE", "loopback"),
            auth_token=os.environ.get("VIBE_AUTH_TOKEN"),
            cors_origins=[
                o.strip() for o in os.environ.get("VIBE_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()
            ],
            log_level=os.environ.get("VIBE_LOG_LEVEL", "INFO"),
            log_to_file=raw_log_file.lower() not in _LOG_OFF_VALUES,
            log_file=(Path(raw_log_file) if raw_log_file and raw_log_file.lower() not in _LOG_OFF_VALUES else None),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            opencode_api_key=os.environ.get("OPENCODE_API_KEY"),
        )

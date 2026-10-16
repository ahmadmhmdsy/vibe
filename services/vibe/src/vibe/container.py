# services/vibe/src/vibe/container.py
"""Composition root: everything the app is composed of, built once.

`create_app` used to assign each collaborator onto `app.state` one line at a
time, and tests then reassigned those attributes to swap in stubs. That worked,
but it had two costs:

* A handler could not see what it depended on — it reached into `app.state`
  by string name, so a missing collaborator was a runtime AttributeError rather
  than a signature you could read.
* Swapping a collaborator after the fact left anything that had already
  captured it stale. `SessionLifecycle` holds its store, event log and
  registries by reference, so the test suite had to rebuild it by hand after
  patching `app.state` — the fixture comment says exactly that.

The container is built *before* anything derives from it, so replacing a seam
replaces the whole graph at once. `build(**overrides)` is the single place a
test substitutes a stub.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from vibe.approvals import ApprovalStore
from vibe.auth import LOOPBACK_OWNER_ID, Authenticator, LoopbackAuthenticator
from vibe.autorun.policy import AutoRunPolicy
from vibe.config import Settings
from vibe.events import EventBus, EventLog, EventStore
from vibe.executor.base import Executor
from vibe.executor.browser import BrowserDriver
from vibe.executor.local import LocalSubprocessExecutor
from vibe.lifecycle import SessionLifecycle
from vibe.providers.custom import CustomProviderStore
from vibe.providers.registry import build_llm_factory
from vibe.runs import RunRegistry, SessionKey
from vibe.runtime.base import AgentRuntime
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.services.messages import MessageService
from vibe.services.sessions import SessionService
from vibe.settings_store import SettingsStore, effective_override
from vibe.store import SessionStore
from vibe.tools.executor_tools import register_executor_tools
from vibe.tools.files import register_file_tools
from vibe.tools.registry import ToolRegistry
from vibe.usage.tracker import UsageTracker


def _build_authenticator(settings: Settings) -> Authenticator:
    """Pick the authenticator named by settings.auth_mode.

    An unknown mode raises rather than falling back to loopback: a typo that
    silently downgraded to the permissive option would be a security bug with
    a green test suite.
    """
    if settings.auth_mode == "loopback":
        return LoopbackAuthenticator()
    raise ValueError(f"unknown VIBE_AUTH_MODE: {settings.auth_mode!r} (expected 'loopback')")


class ExecutorFactory(Protocol):
    """Builds (or reuses) the executor that runs one session's commands.

    A session-level resource is addressed by owner *and* session, so the factory
    takes both. The owner keyword defaults to the loopback owner for the local
    single-user app and for tests, and every route passes the principal's id.
    """

    def __call__(self, session_id: str, workspace: Path, *,
                 owner_id: str = LOOPBACK_OWNER_ID) -> Executor: ...


class AutoRunFactory(Protocol):
    """Builds (or reuses) the auto-run fix-loop policy for one session."""

    def __call__(self, session_id: str, workspace: Path, *,
                 owner_id: str = LOOPBACK_OWNER_ID) -> AutoRunPolicy: ...


def _default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_file_tools(registry)
    register_executor_tools(registry)
    return registry


@dataclass(frozen=True)
class Container:
    """The app's collaborators. Frozen: swap the container, never a field."""

    settings: Settings
    authenticator: Authenticator
    store: SessionStore
    event_log: EventStore
    event_bus: EventBus
    tool_registry: ToolRegistry
    runtime: AgentRuntime
    usage: UsageTracker
    custom_provider_store: CustomProviderStore
    settings_store: SettingsStore
    approval_store: ApprovalStore
    runs: RunRegistry
    lifecycle: SessionLifecycle
    session_service: SessionService
    message_service: MessageService
    executors: dict[SessionKey, Executor]
    autorun_policies: dict[SessionKey, AutoRunPolicy]
    get_executor: ExecutorFactory
    get_autorun: AutoRunFactory

    @classmethod
    def build(cls, settings: Settings, **overrides) -> Container:
        """Compose the app.

        Each override replaces a seam *before* anything is derived from it, so a
        test that passes `store=...` gets a `SessionLifecycle` that already
        points at that store. Unknown names are rejected rather than silently
        ignored — a typo in an override would otherwise look like a passing test
        that never exercised the stub.
        """
        # SessionStore opens sqlite inside the workspace dir, so the builder needs
        # it to exist. create_app also makes it, for the pre-built-container path.
        settings.workspace_dir.mkdir(parents=True, exist_ok=True)
        authenticator = overrides.pop("authenticator", None) or _build_authenticator(settings)
        store = overrides.pop("store", None) or SessionStore(settings.workspace_dir / "sessions.db")
        event_log = overrides.pop("event_log", None) or EventLog(settings.workspace_dir / "events.db")
        event_bus = overrides.pop("event_bus", None) or EventBus()
        custom_provider_store = (overrides.pop("custom_provider_store", None)
                                 or CustomProviderStore(settings.workspace_dir / "providers.json"))
        # The GUI-writable half of BE-19. Workspace-scoped, and read per turn, so
        # a prompt saved in Settings applies without a restart.
        settings_store = (overrides.pop("settings_store", None)
                          or SettingsStore(settings.workspace_dir / "settings.json"))
        tool_registry = overrides.pop("tool_registry", None) or _default_tool_registry()
        usage = overrides.pop("usage", None) or UsageTracker(log=event_log, bus=event_bus)
        runtime = overrides.pop("runtime", None) or LangGraphRuntime(
            llm_factory=build_llm_factory(settings, custom_provider_store),
            tool_registry=tool_registry,
            usage=usage,
        )
        approval_store = overrides.pop("approval_store", None) or ApprovalStore()
        runs = overrides.pop("runs", None) or RunRegistry()

        # Executors and auto-run policies are per-session (each session owns its
        # own workspace), so they live in registries keyed by owner *and* session:
        # a session id is a generated uuid, so the same id under two owners is a
        # different session and must not share a dev server or a fix loop.
        executors: dict[SessionKey, Executor] = {}
        autorun_policies: dict[SessionKey, AutoRunPolicy] = {}

        def get_executor(
            sid: str, workspace: Path, *, owner_id: str = LOOPBACK_OWNER_ID
        ) -> Executor:
            key = SessionKey(owner_id=owner_id, session_id=sid)
            ex = executors.get(key)
            if ex is None:
                ex = LocalSubprocessExecutor(workspace=workspace, browser=BrowserDriver(
                    headless=settings.browser_headless,
                    timeout_ms=settings.browser_timeout_ms))
                executors[key] = ex
            return ex

        def get_autorun(
            sid: str, workspace: Path, *, owner_id: str = LOOPBACK_OWNER_ID
        ) -> AutoRunPolicy:
            key = SessionKey(owner_id=owner_id, session_id=sid)
            policy = autorun_policies.get(key)
            if policy is None:
                policy = AutoRunPolicy(
                    executor=get_executor(sid, workspace, owner_id=owner_id),
                    runtime=runtime,
                    max_fix_iterations=settings.max_fix_iterations,
                    usage=usage,
                    session_token_budget=settings.session_token_budget,
                    # A callable, not a snapshot: the fix loop must see a prompt
                    # saved after the app started (BE-19).
                    system_prompt=lambda: effective_override(settings, settings_store))
                autorun_policies[key] = policy
            return policy

        # A test may replace either factory outright. get_autorun reads
        # get_executor by name, so an overridden executor is picked up too.
        get_executor = overrides.pop("get_executor", None) or get_executor
        get_autorun = overrides.pop("get_autorun", None) or get_autorun
        if overrides:
            raise TypeError(f"unknown container override(s): {', '.join(sorted(overrides))}")

        # Deleting a session has to take everything it owned with it — dev server,
        # executor, autorun policy, event log, approvals — not just its sqlite row
        # (audit H3). Built last, from the (possibly overridden) pieces above.
        lifecycle = SessionLifecycle(
            store=store,
            event_log=event_log,
            executors=executors,
            autorun_policies=autorun_policies,
            approvals=approval_store,
            runs=runs,
            workspace_dir=settings.workspace_dir,
            trash_retention_days=settings.trash_retention_days,
        )
        # Thin facades over the seams above, built from the same (possibly
        # overridden) instances so a test's stub is the one they talk to.
        session_service = SessionService(store=store, lifecycle=lifecycle,
                                         workspace_dir=settings.workspace_dir)
        message_service = MessageService(event_log)
        return cls(
            settings=settings,
            authenticator=authenticator,
            store=store,
            event_log=event_log,
            event_bus=event_bus,
            tool_registry=tool_registry,
            runtime=runtime,
            usage=usage,
            custom_provider_store=custom_provider_store,
            settings_store=settings_store,
            approval_store=approval_store,
            runs=runs,
            lifecycle=lifecycle,
            session_service=session_service,
            message_service=message_service,
            executors=executors,
            autorun_policies=autorun_policies,
            get_executor=get_executor,
            get_autorun=get_autorun,
        )

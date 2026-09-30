# services/vibe/src/vibe/api/app.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vibe.config import Settings
from vibe.store import SessionStore
from vibe.events import EventLog, EventBus
from vibe.tools.registry import ToolRegistry
from vibe.tools.files import register_file_tools
from vibe.tools.executor_tools import register_executor_tools
from vibe.executor.local import LocalSubprocessExecutor
from vibe.runtime.langgraph import LangGraphRuntime
from vibe.autorun.policy import AutoRunPolicy
from vibe.usage.tracker import UsageTracker
from vibe.providers.custom import CustomProviderStore
from vibe.approvals import ApprovalStore


def _llm_factory(settings: Settings, custom_store):
    """Return a factory that builds a real langchain chat model from Settings.

    LangGraphRuntime calls the factory with a ModelRef and expects a chat
    model exposing bind_tools()/astream(). The provider classes wrap
    langchain models but only expose the LlmProvider.chat() protocol, so the
    underlying chat models are constructed directly here from Settings.

    session_id is the vibe session the model call belongs to; OpenCode Go
    requires a stable x-opencode-session header for routing/shard affinity.

    Custom (user-defined) providers are looked up from custom_store; the
    model's protocol decides which LangChain chat model to build.
    """
    def factory(model_ref, session_id: str | None = None):
        if model_ref.provider_id == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(api_key=settings.openai_api_key, model=model_ref.model_id, streaming=True)
        if model_ref.provider_id == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(api_key=settings.anthropic_api_key, model=model_ref.model_id, streaming=True)
        if model_ref.provider_id == "opencode-go":
            from langchain_openai import ChatOpenAI
            headers = {"x-opencode-session": session_id} if session_id else {}
            return ChatOpenAI(api_key=settings.opencode_api_key,
                              base_url="https://opencode.ai/zen/go/v1",
                              model=model_ref.model_id, streaming=True,
                              default_headers=headers)
        # Custom provider: look up the row and build from its protocol.
        custom = custom_store.get(model_ref.provider_id) if custom_store else None
        if custom is not None:
            protocol = next((m.get("protocol", "openai-chat") for m in custom.models if m["id"] == model_ref.model_id), "openai-chat")
            if protocol == "anthropic-messages":
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(api_key=custom.api_key, base_url=custom.base_url,
                                     model=model_ref.model_id, streaming=True)
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(api_key=custom.api_key, base_url=custom.base_url,
                              model=model_ref.model_id, streaming=True)
        raise ValueError(f"unsupported provider: {model_ref.provider_id}")
    return factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="vibe")
    # CORS: the Vite dev server calls this API cross-origin. The port
    # varies (5173, or the next free one when busy), so the allowlist is
    # configurable via VIBE_CORS_ORIGINS (comma-separated).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings

    # --- seam composition --------------------------------------------------
    # Keep the session index inside the workspace root so a single vibe
    # install owns both its workspaces and its session metadata.
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)

    store = SessionStore(db_path=settings.workspace_dir / "sessions.db")
    event_log = EventLog()
    event_bus = EventBus()
    custom_provider_store = CustomProviderStore(settings.workspace_dir / "providers.json")

    tool_registry = ToolRegistry()
    register_file_tools(tool_registry)
    register_executor_tools(tool_registry)

    usage = UsageTracker(log=event_log, bus=event_bus)

    runtime = LangGraphRuntime(llm_factory=_llm_factory(settings, custom_provider_store), tool_registry=tool_registry, usage=usage)

    # Executors and auto-run policies are per-session (each session owns its
    # own workspace), so they live in registries keyed by session id.
    executors: dict[str, LocalSubprocessExecutor] = {}
    autorun_policies: dict[str, AutoRunPolicy] = {}

    app.state.store = store
    app.state.event_log = event_log
    app.state.event_bus = event_bus
    app.state.tool_registry = tool_registry
    app.state.runtime = runtime
    app.state.executors = executors
    app.state.autorun_policies = autorun_policies
    app.state.usage = usage
    app.state.custom_provider_store = custom_provider_store
    app.state.approval_store = ApprovalStore()

    def _get_executor(sid: str, workspace) -> LocalSubprocessExecutor:
        ex = executors.get(sid)
        if ex is None:
            ex = LocalSubprocessExecutor(workspace=workspace)
            executors[sid] = ex
        return ex

    def _get_autorun(sid: str, workspace) -> AutoRunPolicy:
        policy = autorun_policies.get(sid)
        if policy is None:
            policy = AutoRunPolicy(executor=_get_executor(sid, workspace),
                                   runtime=app.state.runtime,
                                   max_fix_iterations=settings.max_fix_iterations,
                                   usage=app.state.usage,
                                   session_token_budget=settings.session_token_budget)
            autorun_policies[sid] = policy
        return policy

    # Attached to app.state so routes can reach them without a circular
    # import (routes are imported by this module below).
    app.state.get_executor = _get_executor
    app.state.get_autorun = _get_autorun

    @app.get("/health")
    def health():
        return {"status": "ok"}

    from vibe.api.routes import sessions, chat, catalog, providers, approvals, messages, preview
    app.include_router(sessions.router)
    app.include_router(chat.router)
    app.include_router(catalog.router)
    app.include_router(providers.router)
    app.include_router(approvals.router)
    app.include_router(messages.router)
    app.include_router(preview.router)

    return app

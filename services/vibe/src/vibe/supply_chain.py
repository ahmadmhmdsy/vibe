# services/vibe/src/vibe/supply_chain.py
from __future__ import annotations

from vibe.events import Event
from vibe.runtime.base import AgentContext

# Starter allowlist: packages the agent may install without approval.
# Anything outside this set requires explicit user approval (a chat event).
ALLOWLIST: frozenset[str] = frozenset({
    # React core
    "react", "react-dom", "react-scripts", "@types/react", "@types/react-dom",
    # Vite / build tooling
    "vite", "@vitejs/plugin-react", "typescript", "tsx", "@types/node",
    # Tailwind
    "tailwindcss", "postcss", "autoprefixer",
    # Common UI / utility libs
    "lucide-react", "clsx", "class-variance-authority", "tailwind-merge",
    "framer-motion", "zustand",
})


def is_allowlisted(package: str) -> bool:
    """True if the package (name only, no version spec) is in the allowlist."""
    # Strip any version range: "react@^19" -> "react", "@scope/pkg@^1" -> "@scope/pkg".
    # A scoped name keeps its leading "@" and its scope segment, so it cannot be
    # recovered by splitting on "@" alone.
    if package.startswith("@"):
        parts = package.split("@")
        name = "@" + parts[1] if len(parts) > 1 else package
    else:
        name = package.split("@")[0]
    return name in ALLOWLIST


async def request_approval(ctx: AgentContext, packages: list[str]) -> str:
    """Create a supply-chain approval, emit a chat event, and wait.

    Returns the final status: "approved" or "denied".
    """
    store = ctx.approval_store
    a = store.create(ctx.session_id, packages)
    payload = {"approval_id": a.id, "packages": packages, "status": "pending"}
    seq = await ctx.event_log.append(ctx.session_id, "approval", payload)
    await ctx.event_bus.publish(ctx.session_id, Event(session_id=ctx.session_id, seq=seq, type="approval", payload=payload))
    status = await store.wait(a.id)
    # Record the resolution as a follow-up event.
    payload["status"] = status
    seq = await ctx.event_log.append(ctx.session_id, "approval", payload)
    await ctx.event_bus.publish(ctx.session_id, Event(session_id=ctx.session_id, seq=seq, type="approval", payload=payload))
    return status

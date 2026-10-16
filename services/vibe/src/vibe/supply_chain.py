# services/vibe/src/vibe/supply_chain.py
from __future__ import annotations

from vibe.events import Event
from vibe.runtime.base import AgentContext

# Starter allowlist: packages the agent may install without approval.
# Anything outside this set requires explicit user approval (a chat event).
ALLOWLIST: frozenset[str] = frozenset(
    {
        # React core
        "react",
        "react-dom",
        "react-scripts",
        "@types/react",
        "@types/react-dom",
        # Vite / build tooling
        "vite",
        "@vitejs/plugin-react",
        "typescript",
        "tsx",
        "@types/node",
        # Tailwind
        "tailwindcss",
        "postcss",
        "autoprefixer",
        # Common UI / utility libs
        "lucide-react",
        "clsx",
        "class-variance-authority",
        "tailwind-merge",
        "framer-motion",
        "zustand",
    }
)


# A specifier can point somewhere else entirely: "react@npm:evil" installs
# evil, "react@file:../evil" a local path, "react@github:evil/repo" a git repo.
# Only a plain version range or dist-tag may follow the name.
_PROTOCOLS = ("npm:", "github:", "git:", "git+", "file:", "link:", "portal:", "workspace:", "http:", "https:")
# Characters that never appear in a version range we accept. "react@^19 nope"
# would otherwise ride the allowlist, because the junk range is never inspected.
_JUNK = frozenset("<>|$ \t\n\r")


def _split_spec(package: str) -> tuple[str, str]:
    """Split "react@^19" into ("react", "^19") and "@scope/pkg@^1" into
    ("@scope/pkg", "^1").

    A scoped name keeps its leading "@", so its scope separator must not be
    mistaken for the spec separator.
    """
    if package.startswith("@"):
        scope, _, rest = package.partition("/")
        if rest and "@" in rest:
            name, _, spec = rest.partition("@")
            return f"{scope}/{name}", spec
        return package, ""
    name, _, spec = package.partition("@")
    return name, spec


def is_allowlisted(package: str) -> bool:
    """True if the specifier names an allowlisted package and cannot redirect.

    Name only, no version spec, is what the allowlist is about -- so every part
    of the specifier that npm would resolve elsewhere is refused first.
    """
    if not isinstance(package, str) or any(c in _JUNK for c in package):
        return False
    name, spec = _split_spec(package)
    if not name or name in (".", ".."):
        return False
    if name.startswith("@"):
        # Exactly one scope separator and no path separator anywhere.
        scope, _, bare = name.partition("/")
        if bare.count("/") or bare.endswith("/") or "\\" in name or len(scope) < 2 or not bare:
            return False
    elif "/" in name or "\\" in name:
        return False
    if spec.lower().startswith(_PROTOCOLS):
        return False
    return name in ALLOWLIST


async def request_approval(ctx: AgentContext, packages: list[str]) -> str:
    """Create a supply-chain approval, emit a chat event, and wait.

    Returns the final status: "approved" or "denied".
    """
    store = ctx.approval_store
    a = store.create(ctx.session_id, packages)
    payload = {"approval_id": a.id, "packages": packages, "status": "pending"}
    seq = await ctx.event_log.append(ctx.session_id, "approval", payload)
    await ctx.event_bus.publish(
        ctx.session_id, Event(session_id=ctx.session_id, seq=seq, type="approval", payload=payload)
    )
    status = await store.wait(a.id)
    # Record the resolution as a follow-up event.
    payload["status"] = status
    seq = await ctx.event_log.append(ctx.session_id, "approval", payload)
    await ctx.event_bus.publish(
        ctx.session_id, Event(session_id=ctx.session_id, seq=seq, type="approval", payload=payload)
    )
    return status

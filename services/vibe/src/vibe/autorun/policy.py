# services/vibe/src/vibe/autorun/policy.py
from __future__ import annotations

import logging

from vibe.events import Event
from vibe.executor.base import CAPTURE_FAILED, NO_DEV_SERVER, NO_DRIVER, UNREACHABLE, capture_console
from vibe.models import AgentInput, Message
from vibe.prompts import system_prompt_for
from vibe.runtime.base import AgentContext
from vibe.services.turns import TurnRecorder

logger = logging.getLogger(__name__)

# Why the runtime-error check read nothing, in the operator's words. Every one of
# these means "the console was never inspected", and each has a different fix, so
# the log must not blame the browser driver for all of them (audit M6, BE-09).
_UNREAD_WHY = {
    NO_DEV_SERVER: "no dev server came up",
    NO_DRIVER: "no browser driver",
    UNREACHABLE: "the dev server is not accepting connections",
    CAPTURE_FAILED: "the page could not be inspected",
}


class AutoRunPolicy:
    def __init__(self, executor, runtime, max_fix_iterations: int = 3,
                 usage=None, session_token_budget: int | None = None,
                 system_prompt: str | None = None):
        self._executor = executor
        self._runtime = runtime
        self._max_fix = max_fix_iterations
        self._usage = usage
        self._budget = session_token_budget
        self._system_prompt = system_prompt

    def _prompt_override(self) -> str | None:
        """Resolve the prompt now rather than at construction.

        A plain string is a fixed prompt; a callable is asked every time, so a
        prompt saved in the Settings panel reaches the next fix turn without a
        restart (BE-19). The container passes a callable.
        """
        value = self._system_prompt
        return value() if callable(value) else value

    async def _over_budget(self, ctx: AgentContext) -> bool:
        """True if the session has exceeded its token budget."""
        if not self._budget or self._usage is None:
            return False
        total = await self._usage.session_total(ctx.session_id)
        return total.total_tokens > self._budget

    @staticmethod
    def _stopped(ctx: AgentContext) -> bool:
        """True when the user pressed Stop.

        An auto-fix turn runs after the answer the user was waiting for, so
        without this check Stop stopped the chat turn and the loop kept editing
        files behind it.
        """
        return bool(ctx.is_aborted is not None and ctx.is_aborted())

    async def maybe_run(self, ctx: AgentContext, changed_files: list[str]) -> None:
        if not changed_files:
            return
        for iteration in range(self._max_fix + 1):
            if self._stopped(ctx):
                logger.info("autorun: stopping, the user pressed stop")
                return
            if await self._over_budget(ctx):
                return
            build = await self._executor.build()
            if build.is_error:
                if iteration < self._max_fix:
                    await self._fix_turn(ctx, f"Build failed: {build.content}")
                continue
            # build ok — start dev server and check runtime errors
            await self._executor.start_dev_server()
            # Say which way nothing got read (BE-09): no server came up, no
            # browser driver, a server that has since died, or a page that could
            # not be inspected. They need different fixes, and a dead server must
            # not be reported as a missing driver -- that is the false diagnosis
            # this check used to make. capture_console answers for every cause and
            # falls back to the old None-returning API.
            capture = await capture_console(self._executor, self._executor.dev_server_url, tail=50)
            if not capture.ok:
                # Nothing was read, so there is nothing to fix. That is not the
                # same as "the console was clean": an empty string here would let
                # this loop claim a check it never performed (audit M6).
                logger.warning(
                    "autorun: %s for session %s; runtime errors cannot be checked"
                    " (this is not a clean console)",
                    _UNREAD_WHY.get(capture.status, _UNREAD_WHY[NO_DRIVER]), ctx.session_id)
                return
            logs = capture.value if isinstance(capture.value, str) else ""
            if logs.strip():
                if iteration < self._max_fix:
                    await self._fix_turn(ctx, f"Runtime errors: {logs}")
                continue
            return  # clean

    async def _fix_turn(self, ctx: AgentContext, error: str) -> None:
        """Run one fix turn and record it in the session's own history.

        The loop used to consume the runtime's events and discard them, so a fix
        turn was invisible: its tool calls never reached the log or the stream,
        its prose never appeared in the transcript, and only its token usage left
        a trace. The turn is now recorded exactly like a chat turn -- including
        the prompt, because the model sees it and "model-visible means logged"
        admits no exception for the loop the user cannot see.
        """
        session = await ctx.store.get_session(ctx.session_id)
        model = session.model_ref if session else None
        content = f"The app failed: {error}. Fix it."
        inp = AgentInput(session_id=ctx.session_id,
                         messages=[Message(role="user", content=content)],
                         model=model,
                         system=system_prompt_for(self._prompt_override()))
        log = ctx.event_log
        if log is None:
            # Nothing to record into. The build is still broken, so run the fix
            # anyway, but do not pretend it was logged.
            logger.warning("autorun: fix turn for session %s is unrecorded (no event log)",
                           ctx.session_id)
            async for _ in self._runtime.run(inp, ctx):
                pass
            return

        seq = await log.append(ctx.session_id, "user/message", {"content": content})
        await self._publish(ctx, "user/message", {"content": content}, seq)

        recorder = TurnRecorder(ctx.session_id, log, ctx.event_bus)
        text = await recorder.consume(self._runtime.run(inp, ctx))
        if text:
            seq = await log.append(ctx.session_id, "assistant/message", {"content": text})
            await self._publish(ctx, "assistant/message", {"content": text}, seq)

    @staticmethod
    async def _publish(ctx: AgentContext, type_: str, payload: dict, seq: int) -> None:
        await ctx.event_bus.publish(ctx.session_id, Event(session_id=ctx.session_id, seq=seq,
                                                          type=type_, payload=payload))

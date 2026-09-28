# services/vibe/src/vibe/autorun/policy.py
from __future__ import annotations
from vibe.models import AgentInput, Message
from vibe.runtime.base import AgentContext

class AutoRunPolicy:
    def __init__(self, executor, runtime, max_fix_iterations: int = 3):
        self._executor = executor
        self._runtime = runtime
        self._max_fix = max_fix_iterations

    async def maybe_run(self, ctx: AgentContext, changed_files: list[str]) -> None:
        if not changed_files:
            return
        for iteration in range(self._max_fix + 1):
            build = await self._executor.build()
            if build.is_error:
                if iteration < self._max_fix:
                    await self._fix_turn(ctx, f"Build failed: {build.content}")
                continue
            # build ok — start dev server and check runtime errors
            handle = await self._executor.start_dev_server()
            logs = await self._executor.read_console_logs(tail=50)
            if logs.strip():
                if iteration < self._max_fix:
                    await self._fix_turn(ctx, f"Runtime errors: {logs}")
                continue
            return  # clean

    async def _fix_turn(self, ctx: AgentContext, error: str) -> None:
        session = await ctx.store.get_session(ctx.session_id)
        model = session.model_ref if session else None
        inp = AgentInput(session_id=ctx.session_id,
                         messages=[Message(role="user", content=f"The app failed: {error}. Fix it.")],
                         model=model)
        async for _ in self._runtime.run(inp, ctx):
            pass

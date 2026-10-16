from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter

from vibe.api.deps import App, Owner, require_session
from vibe.api.errors import ApiError, ErrorCode
from vibe.api.schemas import SendMessageIn
from vibe.auth import LOOPBACK_OWNER_ID
from vibe.events import Event
from vibe.models import AgentInput, Attachment, Message
from vibe.prompts import system_prompt_for
from vibe.providers.registry import ProviderNotConfigured
from vibe.runtime.base import AgentContext
from vibe.settings_store import effective_override
from vibe.workspace import relative_files

logger = logging.getLogger(__name__)

router = APIRouter()


def _snapshot_files(workspace: Path) -> set[str]:
    """Relative paths of the workspace's own files, vendored dirs excluded."""
    return set(relative_files(workspace))


@router.post("/sessions/{sid}/messages")
async def send_message(sid: str, body: SendMessageIn, deps: App,
                       owner: Owner = LOOPBACK_OWNER_ID):
    store = deps.store
    session = await require_session(deps, sid, owner)
    event_log = deps.event_log
    event_bus = deps.event_bus
    runs = deps.runs
    # Claim the session's run slot before the first await below. The old code
    # checked is_running here and claimed the slot fifty lines later, with six
    # awaits in between: two concurrent sends both passed the check and both
    # ran the agent (review probe 4). try_start decides and claims in one
    # synchronous step, so exactly one caller can win.
    handle = runs.try_start(sid, owner_id=owner)
    if handle is None:
        # Two turns interleaved into one transcript produce nonsense ordering.
        raise ApiError(ErrorCode.RUN_IN_PROGRESS, "a run is already in progress for this session")
    try:

        workspace = deps.session_service.ensure_workspace(sid)
        executor = deps.get_executor(sid, workspace, owner_id=owner)
        ctx = AgentContext(session_id=sid, workspace_path=workspace, executor=executor,
                           event_bus=event_bus, store=store, event_log=event_log,
                           approval_store=deps.approval_store,
                           # The auto-fix loop reads this to stop when the user
                           # pressed Stop after the answer arrived.
                           is_aborted=lambda: handle.abort_requested)
        attachments = [Attachment(name=a.name, content_type=a.content_type,
                                  data_base64=a.data_base64) for a in body.attachments]
        # History first, then this turn. The log is already the source of truth
        # for the transcript (see MessageService), so replaying it is what makes
        # "make it blue" have a referent -- the model used to receive exactly one
        # message, always, and could not follow up on anything (BE-03). Building
        # the input before the user/message append below is also what keeps the
        # current message from appearing twice.
        history = await deps.message_service.history(sid, limit=deps.settings.history_messages)
        inp = AgentInput(session_id=sid,
                         messages=[*history, Message(role="user", content=body.content,
                                                     attachments=attachments)],
                         model=session.model_ref,
                         # Resolved per turn, so a prompt saved in the GUI applies to
                         # the next message rather than the next restart (BE-19).
                         system=system_prompt_for(effective_override(deps.settings, deps.settings_store)))

        # Logged before the run so the transcript keeps its order. A failed run
        # appends an assistant/error turn, so history never ends on a user message
        # that nothing answers or explains.
        user_seq = await event_log.append(sid, "user/message", {"content": body.content})
        # Title the session from the first message, so the sidebar stops showing
        # "Untitled 1a2b" for every new conversation. Only fires while the title is
        # still the placeholder, so a manual rename is never clobbered.
        await deps.session_service.retitle_from_message(sid, body.content, owner)
        # Every logged event is also published, so a second tab (or a reconnect)
        # sees the transcript, not just the streamed answer. The SSE route dedupes
        # a live event against the replayed log by seq, so this cannot double-send.
        await event_bus.publish(sid, Event(session_id=sid, seq=user_seq,
                                           type="user/message", payload={"content": body.content}))

        # Snapshot before the run so changed files can be detected afterwards.
        before = _snapshot_files(workspace)
        text_parts: list[str] = []

        async def _consume() -> None:
            async for event in deps.runtime.run(inp, ctx):
                if event.kind == "text_chunk":
                    text_parts.append(event.data.get("text", ""))
                    # Ephemeral: streamed live, never stored (see EventLog.next_seq).
                    await event_bus.publish(sid, Event(session_id=sid, seq=event_log.next_seq(sid),
                                                       type="text_chunk", payload=event.data))
                elif event.kind in ("tool_call", "tool_result"):
                    seq = await event_log.append(sid, event.kind, event.data)
                    await event_bus.publish(sid, Event(session_id=sid, seq=seq,
                                                       type=event.kind, payload=event.data))
                elif event.kind == "turn_complete":
                    await event_bus.publish(sid, Event(session_id=sid, seq=event_log.next_seq(sid),
                                                       type="turn_complete", payload=event.data))

        # The run is a task so /abort has something concrete to cancel: cancelling
        # it propagates into the runtime's async generator and stops the model call.
        logger.info("run started for session %s", sid)
        task = asyncio.create_task(_consume())
        handle.task = task
        error: str | None = None
        error_code = ErrorCode.INTERNAL
        aborted = False
        try:
            await task
        except asyncio.CancelledError:
            if task.cancelled() and handle.abort_requested:
                aborted = True          # /abort stopped the run: report it, do not re-raise
            else:
                handle.request_abort()  # the client vanished: stop the run with us
                raise
        except ProviderNotConfigured as e:
            # A missing key or an unknown provider id is the operator's to fix; it
            # is not a crash and needs no traceback. It gets its own code because
            # it is the one failure the UI can tell the user how to resolve.
            error = str(e)
            error_code = ErrorCode.PROVIDER_NOT_CONFIGURED
            logger.warning("run rejected for session %s: %s", sid, error)
        except Exception as e:
            if isinstance(e, ValueError):
                # A ValueError is a rejected request, not a crash: its text is
                # written for the caller and is safe to show.
                error = str(e)
                error_code = ErrorCode.VALIDATION_FAILED
                logger.warning("run rejected for session %s: %s", sid, error)
            else:
                # An unexpected failure's text can carry a filesystem path, a
                # provider's raw response body or a key fragment. Keep the
                # honest code, but send a generic message with a short
                # correlation id and log the detail under that same id, so the
                # user can quote it and an operator can find it (BE-10).
                error_id = uuid.uuid4().hex[:8]
                error = f"internal server error (error id {error_id})"
                error_code = ErrorCode.INTERNAL
                logger.exception("run failed for session %s (error id %s): %s", sid, error_id, e)
        finally:
            if not task.done():
                task.cancel()

        content = "".join(text_parts)

        if error is not None:
            error_seq = await event_log.append(sid, "assistant/error", {"content": error})
            await event_bus.publish(sid, Event(session_id=sid, seq=error_seq,
                                               type="assistant/error", payload={"content": error}))
            await event_bus.publish(sid, Event(session_id=sid, seq=event_log.next_seq(sid),
                                               type="error", payload={"message": error}))
            raise ApiError(error_code, error)

        if aborted:
            logger.info("run aborted for session %s", sid)
            # Keep the text the user already saw and close the turn, so a client
            # spinner cannot hang on a run that will never finish.
            if content:
                partial_seq = await event_log.append(sid, "assistant/message", {"content": content})
                await event_bus.publish(sid, Event(session_id=sid, seq=partial_seq,
                                                   type="assistant/message", payload={"content": content}))
            aborted_seq = await event_log.append(sid, "turn/aborted", {})
            await event_bus.publish(sid, Event(session_id=sid, seq=aborted_seq,
                                               type="turn/aborted", payload={}))
            await event_bus.publish(sid, Event(session_id=sid, seq=event_log.next_seq(sid),
                                               type="turn_complete", payload={"aborted": True}))
            return {"content": content, "aborted": True}

        answer_seq = await event_log.append(sid, "assistant/message", {"content": content})
        await event_bus.publish(sid, Event(session_id=sid, seq=answer_seq,
                                           type="assistant/message", payload={"content": content}))

        # auto-run verify-fix: if source files changed, build + run + fix. A stop
        # request also stops this follow-on work.
        after = _snapshot_files(workspace)
        changed = sorted(after - before)
        if changed and not handle.abort_requested:
            logger.info("autorun: %d changed file(s) in session %s", len(changed), sid)
            autorun = deps.get_autorun(sid, workspace, owner_id=owner)
            await autorun.maybe_run(ctx, changed)
        return {"content": content, "aborted": False}

    finally:
        # Release the slot on every path, including a failure before the run
        # started. The old bookkeeping released it in the inner finally, so a
        # request that failed earlier left a handle nobody ever finished and
        # wedged the session against every later send.
        if handle.task is not None and not handle.task.done():
            handle.task.cancel()
        runs.finish(sid, handle, owner_id=owner)


@router.post("/sessions/{sid}/abort")
async def abort_run(sid: str, deps: App, owner: Owner = LOOPBACK_OWNER_ID):
    """Stop the in-flight agent run for this session.

    Idempotent: reports whether a run was actually stopped, so a Stop click
    that races the end of a turn is a no-op instead of an error.
    """
    await require_session(deps, sid, owner)
    return {"aborted": deps.runs.abort(sid, owner_id=owner)}

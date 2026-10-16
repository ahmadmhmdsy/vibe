# services/vibe/src/vibe/runtime/langgraph.py
from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from vibe.models import AgentEvent, AgentInput, Message, UsageRecord
from vibe.runtime.base import AgentContext
from vibe.usage.pricing import cost_usd


def _to_lc_message(m: Message):
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    if m.role == "user":
        if m.attachments:
            content: list = [{"type": "text", "text": m.content}]
            for a in m.attachments:
                content.append(
                    {"type": "image_url", "image_url": {"url": f"data:{a.content_type};base64,{a.data_base64}"}}
                )
            return HumanMessage(content=content)
        return HumanMessage(content=m.content)
    if m.role == "assistant":
        return AIMessage(content=m.content, tool_calls=m.tool_calls)
    if m.role == "system":
        return SystemMessage(content=m.content)
    return ToolMessage(content=m.content, tool_call_id=m.tool_call_id, name=m.name)


def build_messages(input: AgentInput) -> list:
    """The message list the model sees: standing instructions, then the transcript.

    Split out of run() so the shape can be asserted without a graph or an LLM.
    """
    messages = [_to_lc_message(m) for m in input.messages]
    if input.system:
        messages.insert(0, _to_lc_message(Message(role="system", content=input.system)))
    return messages


def _text_of(content) -> str:
    """The text of a tool message, ignoring any image blocks.

    A tool may return content blocks (a screenshot returns an image). The SSE
    event is a transcript, not a transport for binary, so the image is dropped
    here -- it still reaches the model through the message itself.
    """
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return content if isinstance(content, str) else str(content)


def _is_error(message) -> bool:
    """Whether the tool reported a failure, read from the message artifact.

    This used to be a hardcoded False, so a failing tool looked like a
    successful one to the UI and to every consumer of the event stream.
    """
    artifact = getattr(message, "artifact", None)
    return bool(artifact.get("is_error")) if isinstance(artifact, dict) else False


class LangGraphRuntime:
    def __init__(self, llm_factory: Callable, tool_registry, usage=None):
        self._llm_factory = llm_factory
        self._tool_registry = tool_registry
        self._usage = usage

    async def _record_usage(self, model_ref, ctx: AgentContext, response) -> None:
        """Normalize the LLM response's usage_metadata into a UsageRecord."""
        md = getattr(response, "usage_metadata", None) or {}
        if not md:
            return
        input_tokens = md.get("input_tokens", 0) or 0
        output_tokens = md.get("output_tokens", 0) or 0
        details = md.get("input_token_details", {}) or {}
        cached = details.get("cache_read", 0) or 0
        cache_write = details.get("cache_creation", 0) or 0
        usage = UsageRecord(
            provider=model_ref.provider_id,
            model=model_ref.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached,
            cache_write_tokens=cache_write,
            cache_hit=cached > 0,
            cache_hit_rate=cached / (input_tokens + cached) if (input_tokens + cached) else 0.0,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd(model_ref.provider_id, model_ref.model_id, input_tokens, output_tokens, cached),
        )
        await self._usage.record(ctx.session_id, usage)

    def _build_graph(self, model_ref, ctx: AgentContext):
        llm = self._llm_factory(model_ref, ctx.session_id)
        lc_tools = self._tool_registry.to_langchain_tools(ctx)
        llm_with_tools = llm.bind_tools(lc_tools)

        async def call_model(state: MessagesState):
            response = await llm_with_tools.ainvoke(state["messages"])
            if self._usage is not None:
                await self._record_usage(model_ref, ctx, response)
            return {"messages": [response]}

        tool_node = ToolNode(lc_tools)
        graph = StateGraph(MessagesState)
        graph.add_node("call_model", call_model)
        graph.add_node("execute_tools", tool_node)
        graph.add_edge(START, "call_model")
        graph.add_conditional_edges("call_model", tools_condition, {"tools": "execute_tools", END: END})
        graph.add_edge("execute_tools", "call_model")
        return graph.compile()

    async def run(self, input: AgentInput, ctx: AgentContext) -> AsyncIterator[AgentEvent]:
        app = self._build_graph(input.model, ctx)
        messages = build_messages(input)
        async for chunk in app.astream({"messages": messages}, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_name == "call_model":
                    msg = node_output["messages"][-1]
                    if msg.content:
                        yield AgentEvent(kind="text_chunk", data={"text": msg.content})
                    for tc in getattr(msg, "tool_calls", []):
                        yield AgentEvent(kind="tool_call", data={"tool_call": tc})
                elif node_name == "execute_tools":
                    for tm in node_output["messages"]:
                        yield AgentEvent(
                            kind="tool_result",
                            data={
                                "tool_call_id": tm.tool_call_id,
                                "name": tm.name,
                                "content": _text_of(tm.content),
                                "is_error": _is_error(tm),
                            },
                        )
        yield AgentEvent(kind="turn_complete", data={})

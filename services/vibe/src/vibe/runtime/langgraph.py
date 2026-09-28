# services/vibe/src/vibe/runtime/langgraph.py
from __future__ import annotations
from typing import AsyncIterator, Callable
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import AIMessage
from vibe.models import AgentInput, AgentEvent, Message
from vibe.runtime.base import AgentContext

def _to_lc_message(m: Message):
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
    if m.role == "user":
        return HumanMessage(content=m.content)
    if m.role == "assistant":
        return AIMessage(content=m.content, tool_calls=m.tool_calls)
    if m.role == "system":
        return SystemMessage(content=m.content)
    return ToolMessage(content=m.content, tool_call_id=m.tool_call_id, name=m.name)

class LangGraphRuntime:
    def __init__(self, llm_factory: Callable, tool_registry):
        self._llm_factory = llm_factory
        self._tool_registry = tool_registry

    def _build_graph(self, model_ref, ctx: AgentContext):
        llm = self._llm_factory(model_ref)
        lc_tools = self._tool_registry.to_langchain_tools(ctx)
        llm_with_tools = llm.bind_tools(lc_tools)

        def call_model(state: MessagesState):
            response = llm_with_tools.invoke(state["messages"])
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
        messages = [_to_lc_message(m) for m in input.messages]
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
                        yield AgentEvent(kind="tool_result", data={
                            "tool_call_id": tm.tool_call_id, "name": tm.name,
                            "content": tm.content, "is_error": False})
        yield AgentEvent(kind="turn_complete", data={})

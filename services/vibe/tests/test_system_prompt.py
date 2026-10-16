# tests/test_system_prompt.py
"""R3-T4 (BE-19): the agent gets standing instructions, not just tool schemas.

Nothing ever emitted a system message: AgentInput had no system field, and the
runtime's converter had a "system" branch no caller used. So the model's whole
instruction set was the tool schemas — nothing said the target is React + Vite +
TypeScript, that the session owns one workspace, or that the app has to build.
"""

import pytest
from conftest import swap
from langchain_core.messages import HumanMessage, SystemMessage

from vibe.models import AgentEvent, AgentInput, Message, ModelRef
from vibe.prompts import DEFAULT_SYSTEM_PROMPT, system_prompt_for
from vibe.runtime.langgraph import build_messages


class SystemRecordingRuntime:
    """Records the whole AgentInput, so a test can see the prompt that was sent."""

    def __init__(self):
        self.systems: list = []
        self.prompts: list = []

    async def run(self, input, ctx):
        self.systems.append(input.system)
        self.prompts.append([m.content for m in input.messages])
        yield AgentEvent(kind="text_chunk", data={"text": "ok"})
        yield AgentEvent(kind="turn_complete", data={})


def test_the_default_prompt_names_the_target_stack():
    for expected in ("React", "TypeScript", "Vite"):
        assert expected in DEFAULT_SYSTEM_PROMPT, expected
    assert "workspace" in DEFAULT_SYSTEM_PROMPT


@pytest.mark.parametrize("override", [None, "", "   "])
def test_an_empty_override_means_the_built_in_prompt(override):
    """An empty VIBE_SYSTEM_PROMPT must not strip the agent of all framing."""
    assert system_prompt_for(override) == DEFAULT_SYSTEM_PROMPT


def test_an_override_replaces_the_default():
    assert system_prompt_for("  be terse  ") == "be terse"


def test_the_system_message_comes_first():
    inp = AgentInput(
        session_id="s",
        messages=[Message(role="user", content="build a counter")],
        model=ModelRef("openai", "gpt-4o"),
        system="STANDING INSTRUCTIONS",
    )
    messages = build_messages(inp)
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == "STANDING INSTRUCTIONS"
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "build a counter"


def test_no_system_message_without_a_prompt():
    """A caller that deliberately sends a bare transcript gets no invented prompt."""
    inp = AgentInput(session_id="s", messages=[Message(role="user", content="hi")], model=ModelRef("openai", "gpt-4o"))
    messages = build_messages(inp)
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)


def test_history_and_prompt_arrive_together(app, client, session_id, container):
    """The two R3 halves meet in the route: framed, and with its history."""
    runtime = SystemRecordingRuntime()
    swap(app, runtime=runtime)

    first = client.post(f"/sessions/{session_id}/messages", json={"content": "my name is Ahmad"})
    assert first.status_code == 200, first.text
    second = client.post(f"/sessions/{session_id}/messages", json={"content": "what is my name?"})
    assert second.status_code == 200, second.text

    assert runtime.systems == [DEFAULT_SYSTEM_PROMPT, DEFAULT_SYSTEM_PROMPT]
    assert runtime.prompts[1] == ["my name is Ahmad", "ok", "what is my name?"]

    container.settings.system_prompt = "answer in Arabic"
    third = client.post(f"/sessions/{session_id}/messages", json={"content": "hi again"})
    assert third.status_code == 200, third.text
    assert runtime.systems[2] == "answer in Arabic"

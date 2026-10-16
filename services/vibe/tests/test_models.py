# tests/test_models.py
from vibe.models import AgentInput, Message, ModelRef, ToolCall, ToolResult, UsageRecord


def test_message_with_tool_calls():
    msg = Message(
        role="assistant", content="", tool_calls=[ToolCall(id="1", name="write_file", arguments={"path": "a.py"})]
    )
    assert msg.tool_calls[0].name == "write_file"


def test_tool_result():
    r = ToolResult(tool_call_id="1", name="write_file", content="ok")
    assert r.is_error is False


def test_usage_record_cache_hit_rate():
    u = UsageRecord(
        provider="openai",
        model="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        cached_tokens=80,
        cache_write_tokens=0,
        cache_hit=True,
        cache_hit_rate=80 / 180,
        total_tokens=230,
        cost_usd=0.01,
    )
    assert 0.44 < u.cache_hit_rate < 0.45


def test_agent_input():
    inp = AgentInput(
        session_id="s1",
        messages=[Message(role="user", content="hi")],
        model=ModelRef(provider_id="openai", model_id="gpt-4o"),
    )
    assert inp.session_id == "s1"

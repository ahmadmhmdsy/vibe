# tests/test_history.py
"""R1-T4 probe 3 promoted, fixed in R3-T1: the agent must see the conversation.

send_message used to build AgentInput from a single Message: the turn the user
just sent. The model therefore re-read the log's own transcript -- nothing -- and
could not answer "what did I just say?". The recording runtime captures exactly
what it was handed, so the evidence is the second turn's message list.
"""

from conftest import swap


def test_second_turn_sees_the_first(app, client, recording_runtime, session_id):
    swap(app, runtime=recording_runtime)

    first = client.post(f"/sessions/{session_id}/messages", json={"content": "my name is Ahmad"})
    assert first.status_code == 200, first.text
    second = client.post(f"/sessions/{session_id}/messages", json={"content": "what is my name?"})
    assert second.status_code == 200, second.text

    assert len(recording_runtime.inputs) == 2
    assert [m.content for m in recording_runtime.inputs[1]] == [
        "my name is Ahmad",
        "ok",
        "what is my name?",
    ]


def test_history_is_capped(app, client, recording_runtime, session_id, container):
    """A long session must not resend its whole transcript on every turn.

    history_messages caps what is replayed from the log; the current message is
    appended to that window, so limit=2 yields two prior messages plus this one.
    """
    swap(app, runtime=recording_runtime)
    container.settings.history_messages = 2

    for i in range(6):
        resp = client.post(f"/sessions/{session_id}/messages", json={"content": f"m{i}"})
        assert resp.status_code == 200, resp.text

    assert [m.content for m in recording_runtime.inputs[-1]] == ["m4", "ok", "m5"]

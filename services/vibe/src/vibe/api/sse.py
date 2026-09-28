from __future__ import annotations
import json
from fastapi.responses import StreamingResponse
from vibe.events import Event

def format_sse(event: Event) -> str:
    return f"data: {json.dumps({'seq': event.seq, 'type': event.type, 'payload': event.payload})}\n\n"

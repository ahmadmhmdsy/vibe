# tests/live/sse_probe.py
# Reads the first N events off a live SSE endpoint and prints them as JSON.
# The endpoint is an infinite stream, so this breaks after N rather than
# waiting for a body that never ends (TestClient cannot do this).
#   python tests/live/sse_probe.py http://127.0.0.1:7321 <session-id>
import json
import sys

import httpx

base, sid = sys.argv[1], sys.argv[2]
seen = []
with httpx.stream("GET", f"{base}/sessions/{sid}/events", timeout=10.0) as r:
    for line in r.iter_lines():
        if line.startswith("data: "):
            seen.append(json.loads(line[6:]))
        if len(seen) >= 2:
            break
print(json.dumps(seen))

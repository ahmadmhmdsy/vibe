---
id: agent
status: active
scope: services/vibe agent runtime
applies_when: agent runtime, LLM providers, or tool loop work
owner: repository-owner
last_reviewed: 2026-09-28
supersedes: none
evidence: design spec §4–5
---

# Agent runtime rules

- The agent loop is a **seam**: the backend depends on the `AgentRuntime`
  interface, never on LangGraph directly. Swapping the framework means
  writing one new implementation — no other module changes.
- Tools are **registrations**: adding/removing a tool is a registry
  edit, never a loop edit. The loop discovers tools at runtime.
- Auto-run is a **policy** that composes runtime calls — never a branch
  inside the loop. Fix turns are ordinary `AgentRuntime.run()` calls.
- Model-visible means logged: anything the agent sees is reconstructable
  from the EventLog.
- Provider calls go through the `LlmProvider` seam; per-model protocol
  routing (openai-chat / openai-responses / anthropic-messages) is resolved
  from the provider config row, never hardcoded.
- Usage is captured per step from the streaming response and normalized
  across providers into one UsageRecord shape.

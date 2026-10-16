// features/chat/toolSummary.ts — one line that says what a tool is doing.
//
// A tool row is only useful if the user can tell which file, command, or
// package it touched without expanding it. The backend's tool names are stable
// (see the agent's tool registry), so a small explicit map beats guessing at
// argument shapes.

/** Longest summary we render; the row is one line and truncates with CSS too. */
const MAX_SUMMARY_CHARS = 120;

const PATH_KEYS = ["path", "file", "filename", "file_path", "target"];
const COMMAND_KEYS = ["command", "cmd", "script"];

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const asString = (value: unknown): string => (typeof value === "string" ? value.trim() : "");

function firstString(record: Record<string, unknown>, keys: readonly string[]): string {
  for (const key of keys) {
    const value = asString(record[key]);
    if (value) return value;
  }
  return "";
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(asString).filter(Boolean);
}

function firstStringValue(record: Record<string, unknown>): string {
  for (const value of Object.values(record)) {
    const text = asString(value);
    if (text) return text;
  }
  return "";
}

function compactJson(record: Record<string, unknown>): string {
  try {
    return JSON.stringify(record);
  } catch {
    return "";
  }
}

const cap = (text: string): string =>
  text.length > MAX_SUMMARY_CHARS ? `${text.slice(0, MAX_SUMMARY_CHARS - 1)}…` : text;

/** A one-line human summary of a tool call's arguments. "" when the tool takes
 * nothing worth naming, in which case the row shows just the tool name. */
export function summarizeToolCall(name: string, args: unknown): string {
  const record = isRecord(args) ? args : {};

  switch (name) {
    case "write_file":
    case "read_file":
    case "edit_file":
      return cap(firstString(record, PATH_KEYS));
    case "list_files":
      return cap(firstString(record, PATH_KEYS) || "the workspace");
    case "install_deps": {
      const packages = stringList(record.packages);
      if (packages.length > 0) return cap(packages.join(", "));
      return cap(firstString(record, ["manager", "ecosystem", "command"]));
    }
    case "run_command":
    case "run_terminal_command":
      return cap(firstString(record, COMMAND_KEYS));
    case "read_console_logs":
      return cap(`${firstString(record, ["level"]) || "error"} logs`);
    case "screenshot":
      return cap(firstString(record, ["label", "url"]));
    default: {
      // Unknown or new tool: show the first argument that reads as a value, and
      // fall back to compact JSON so the arguments are never invisible.
      const direct = firstStringValue(record);
      if (direct) return cap(direct);
      const json = compactJson(record);
      return json === "{}" ? "" : cap(json);
    }
  }
}

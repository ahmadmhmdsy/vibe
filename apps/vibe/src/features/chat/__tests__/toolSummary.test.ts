// features/chat/__tests__/toolSummary.test.ts
import { describe, it, expect } from "vitest";
import { summarizeToolCall } from "../toolSummary";

describe("summarizeToolCall", () => {
  it("names the file a file tool touches", () => {
    expect(summarizeToolCall("write_file", { path: "src/App.tsx" })).toBe("src/App.tsx");
    expect(summarizeToolCall("read_file", { file_path: "src/main.tsx" })).toBe("src/main.tsx");
    expect(summarizeToolCall("edit_file", { file: "package.json" })).toBe("package.json");
  });

  it("shows the command a run tool executes", () => {
    expect(summarizeToolCall("run_command", { command: "pnpm test" })).toBe("pnpm test");
  });

  it("lists the packages an install touches", () => {
    expect(summarizeToolCall("install_deps", { packages: ["react", "zod"] })).toBe("react, zod");
  });

  it("falls back to a generic label for a bare list", () => {
    expect(summarizeToolCall("list_files", {})).toBe("the workspace");
  });

  it("labels console log reads by level", () => {
    expect(summarizeToolCall("read_console_logs", {})).toBe("error logs");
    expect(summarizeToolCall("read_console_logs", { level: "warn" })).toBe("warn logs");
  });

  it("returns nothing when a tool takes no arguments", () => {
    expect(summarizeToolCall("screenshot", {})).toBe("");
  });

  it("uses the first string argument for an unknown tool", () => {
    expect(summarizeToolCall("mystery_tool", { query: "find the bug" })).toBe("find the bug");
  });

  it("falls back to compact JSON when no argument is a string", () => {
    expect(summarizeToolCall("mystery_tool", { depth: 3 })).toBe('{"depth":3}');
  });

  it("caps a long summary", () => {
    const summary = summarizeToolCall("run_command", { command: "x".repeat(300) });
    expect(summary).toHaveLength(120);
    expect(summary.endsWith("…")).toBe(true);
  });
});

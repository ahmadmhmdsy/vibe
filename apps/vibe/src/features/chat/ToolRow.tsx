// features/chat/ToolRow.tsx — one tool call, its status, and its output.
//
// The row is a button: its accessible name is the tool, the summary of its
// arguments, and the status word, and activating it reveals the raw arguments
// and result. Status is carried by a word and an icon, never by colour alone.

import { useEffect, useState } from "react";
import { Icon } from "../../components/icons/Icon";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { summarizeToolCall } from "./toolSummary";
import type { ToolItem, ToolStatus } from "./timeline";

/** A result longer than this collapses behind a "Show full output" toggle. */
const RESULT_LINE_LIMIT = 20;
const RESULT_CHAR_LIMIT = 4000;

const STATUS_LABEL: Record<ToolStatus, string> = {
  running: "Running",
  ok: "Done",
  error: "Failed",
};

/** Live seconds since the call started; ticks only while it is running. */
function useElapsedSeconds(startedAt: number, running: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  return Math.max(0, Math.floor((now - startedAt) / 1000));
}

function formatArgs(args: unknown): string | undefined {
  if (args === undefined || args === null) return undefined;
  try {
    const json = JSON.stringify(args, null, 2);
    if (!json || json === "{}" || json === "[]") return undefined;
    return json;
  } catch {
    return undefined;
  }
}

export function ToolRow({ item }: { item: ToolItem }) {
  const [open, setOpen] = useState(false);
  const [showFullResult, setShowFullResult] = useState(false);
  const running = item.status === "running";
  const elapsed = useElapsedSeconds(item.startedAt, running);
  const summary = summarizeToolCall(item.name, item.args);
  const argsJson = formatArgs(item.args);
  const result = item.result ?? "";
  const isLongResult =
    result.split("\n").length > RESULT_LINE_LIMIT || result.length > RESULT_CHAR_LIMIT;

  // The row and its detail are one unit: without the wrapper the transcript's
  // inter-item gap would visually detach the expanded output from its row.
  return (
    <div className="tool-item">
      <button
        type="button"
        className="tool-row"
        data-status={item.status}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="chevronRight" size={14} className="tool-row-chevron" />
        {/* Decorative: the status word next to it carries the meaning, and the
            spinner inside a live region must not be a second live region. */}
        <span className="tool-row-icon" aria-hidden="true">
          {running ? (
            <Spinner size="sm" live={false} label="Running" />
          ) : (
            <Icon name={item.status === "ok" ? "check" : "warning"} size={14} />
          )}
        </span>
        <code className="tool-row-name">{item.name}</code>
        {summary && <span className="tool-row-summary">{summary}</span>}
        <span className="tool-row-meta">
          {running && <span className="tool-row-elapsed tnum">{elapsed}s</span>}
          <span className="tool-row-status-label">{STATUS_LABEL[item.status]}</span>
        </span>
      </button>

      {open && (
        <div className="tool-row-detail">
          <div className="tool-row-section">
            <span className="tool-row-label">Arguments</span>
            {argsJson ? (
              <pre className="tool-row-pre">
                <code>{argsJson}</code>
              </pre>
            ) : (
              <p className="message-pending">No arguments</p>
            )}
          </div>
          {item.result !== undefined && (
            <div className="tool-row-section">
              <span className="tool-row-label">{item.status === "error" ? "Error" : "Result"}</span>
              <pre
                className={`tool-row-pre${isLongResult && !showFullResult ? " is-clamped" : ""}`}
                data-error={item.status === "error" || undefined}
              >
                <code>{result || "(empty)"}</code>
              </pre>
              {isLongResult && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowFullResult((value) => !value)}
                >
                  {showFullResult ? "Show less output" : "Show full output"}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

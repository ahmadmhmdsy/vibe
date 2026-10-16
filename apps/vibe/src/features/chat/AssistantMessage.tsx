// features/chat/AssistantMessage.tsx — one assistant turn.
//
// Prose and fenced code are rendered from the item's text: the fence splitter
// (./codeFences) decides the split, so there is no markdown pipeline in the
// transcript and streaming text is safe to render as it arrives.

import { useCallback, useState } from "react";
import { Icon } from "../../components/icons/Icon";
import { Button } from "../../components/ui/Button";
import { splitFences } from "./codeFences";
import type { AssistantItem } from "./timeline";

export function AssistantMessage({ item }: { item: AssistantItem }) {
  const segments = splitFences(item.content);
  return (
    <div className="message message-assistant">
      <span className="message-role">Agent</span>
      <div className="message-content">
        {segments.map((segment, index) =>
          segment.kind === "code" ? (
            <CodeBlock key={index} code={segment.content} lang={segment.lang} />
          ) : (
            <p key={index} className="message-prose">
              {segment.content}
            </p>
          )
        )}
        {item.streaming && <span className="message-caret" aria-hidden="true" />}
      </div>
    </div>
  );
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    try {
      // Clipboard access is unavailable outside a secure context; the code
      // stays selectable, which is the fallback.
      await navigator.clipboard?.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* keep the code selectable */
    }
  }, [code]);

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{lang || "text"}</span>
        <Button
          variant="ghost"
          size="sm"
          className="code-block-copy"
          aria-label="Copy code"
          onClick={copy}
        >
          <Icon name={copied ? "check" : "copy"} size={14} />
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <pre className="code-block-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// apps/vibe/src/lib/markdown.tsx
import { useState } from "react";
import ReactMarkdown from "react-markdown";

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable (non-secure context) — ignore.
    }
  };

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-block-lang">{language}</span>
        <button onClick={copy} className="code-block-copy" aria-label="Copy code">
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="code-block-pre">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export function Markdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        code({ className, children }) {
          const match = /language-(\w+)/.exec(className || "");
          const code = String(children).replace(/\n$/, "");
          if (match) {
            return <CodeBlock language={match[1]} code={code} />;
          }
          return <code className={className}>{children}</code>;
        },
        pre({ children }) {
          // CodeBlock renders its own <pre>; avoid double-wrapping.
          return <>{children}</>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

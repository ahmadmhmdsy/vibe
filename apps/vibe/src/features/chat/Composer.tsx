// apps/vibe/src/features/chat/Composer.tsx
import { useRef, useState } from "react";
import { api, ApiError, type Attachment } from "../../lib/api";
import { useChatStore } from "./store";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { IconButton } from "../../components/ui/IconButton";
import { Button } from "../../components/ui/Button";

export function Composer({ sessionId }: { sessionId: string }) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const addMessage = useChatStore((s) => s.addMessage);
  const setStreaming = useChatStore((s) => s.setStreaming);
  const requestStop = useChatStore((s) => s.requestStop);
  const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    for (const f of files) {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        const data_base64 = dataUrl.split(",")[1] ?? "";
        setAttachments((prev) => [...prev, { name: f.name, content_type: f.type || "image/png", data_base64 }]);
      };
      reader.readAsDataURL(f);
    }
    e.target.value = "";
  };

  const send = async () => {
    if (!text.trim() && attachments.length === 0) return;
    const snapshot = { text, attachments };
    addMessage(sessionId, { role: "user", content: text });
    setText("");
    setAttachments([]);
    setStreaming(sessionId, true);
    setError(null);
    try {
      await api.sendMessage(sessionId, snapshot.text, snapshot.attachments);
    } catch (e) {
      // Restore the user's work — never swallow a failed send silently.
      setText(snapshot.text);
      setAttachments(snapshot.attachments);
      setError(e instanceof ApiError ? `${e.message}. Your message was kept.` : "Failed to send. Your message was kept.");
    } finally {
      setStreaming(sessionId, false);
    }
  };

  const stop = () => {
    requestStop(sessionId);
    setStreaming(sessionId, false);
  };

  return (
    <div className="composer">
      {error && (
        <div className="composer-error">
          <ErrorBanner message={error} />
        </div>
      )}
      {attachments.length > 0 && (
        <div className="composer-attachments">
          {attachments.map((a, i) => (
            <div key={i} className="composer-attachment">
              <img src={`data:${a.content_type};base64,${a.data_base64}`} alt={a.name} />
              <button
                onClick={() => setAttachments((prev) => prev.filter((_, j) => j !== i))}
                aria-label={`Remove ${a.name}`}
                className="composer-attachment-remove"
              >
                <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="composer-row">
        <input ref={fileRef} type="file" accept="image/*" multiple onChange={onPick} className="sr-only" aria-label="Attach image" />
        <IconButton label="Attach image" onClick={() => fileRef.current?.click()}>
          <svg width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
            <path d="M6.5 9.5L13 3a2.1 2.1 0 00-3-3L3.5 6.5M8 2l6 6M2 11.5V14h2.5L13 5.5 10.5 3 2 11.5z" strokeLinejoin="round" />
          </svg>
        </IconButton>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="Describe the app you want to build..."
          aria-label="Describe the app you want to build"
          className="composer-input"
          rows={1}
        />
        {isStreaming ? (
          <Button variant="danger" size="md" onClick={stop}>
            Stop
          </Button>
        ) : (
          <Button variant="primary" size="md" onClick={send} disabled={!text.trim() && attachments.length === 0}>
            Send
          </Button>
        )}
      </div>
    </div>
  );
}

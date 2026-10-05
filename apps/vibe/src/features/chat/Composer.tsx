// features/chat/Composer.tsx — Message input with image attachment.
// Supports text input, image attachments, drag-and-drop, and send/stop functionality.

import { useEffect, useRef, useState, useCallback } from "react";
import { api, ApiError, type Attachment } from "../../lib/api";
import { useChatStore } from "./store";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { IconButton } from "../../components/ui/IconButton";
import { Button } from "../../components/ui/Button";

const MAX_CHARS = 4000;

export function Composer({ sessionId }: { sessionId: string }) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const addMessage = useChatStore((s) => s.addMessage);
  const beginStream = useChatStore((s) => s.beginStream);
  const endStream = useChatStore((s) => s.endStream);
  const requestStop = useChatStore((s) => s.requestStop);
  const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);

  const charCount = text.length;
  const isOverLimit = charCount > MAX_CHARS;
  // The limit is only worth showing when it is about to matter.
  const isNearLimit = charCount > MAX_CHARS * 0.8;

  // Grow with the draft instead of scrolling a one-line box.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text]);

  const processFiles = useCallback((files: FileList | File[]) => {
    for (const f of Array.from(files)) {
      if (!f.type.startsWith("image/")) continue;
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        const data_base64 = dataUrl.split(",")[1] ?? "";
        setAttachments((prev) => [...prev, { name: f.name, content_type: f.type || "image/png", data_base64 }]);
      };
      reader.readAsDataURL(f);
    }
  }, []);

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(e.target.files ?? []);
    e.target.value = "";
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const send = async () => {
    if (!text.trim() && attachments.length === 0) return;
    if (isOverLimit) return;
    const snapshot = { text, attachments };
    addMessage(sessionId, { role: "user", content: text });
    setText("");
    setAttachments([]);
    beginStream(sessionId);
    setError(null);
    try {
      await api.sendMessage(sessionId, snapshot.text, snapshot.attachments);
    } catch (e) {
      // Restore the user's work — never swallow a failed send silently.
      setText(snapshot.text);
      setAttachments(snapshot.attachments);
      setError(e instanceof ApiError ? `${e.message}. Your message was kept.` : "Failed to send. Your message was kept.");
    } finally {
      endStream(sessionId);
    }
  };

  const stop = async () => {
    requestStop(sessionId);
    try {
      const { aborted } = await api.abortSession(sessionId);
      // A real abort makes the backend publish turn_complete, which ends the
      // stream; only a no-op stop has to end it here.
      if (!aborted) endStream(sessionId);
    } catch {
      endStream(sessionId);
    }
  };

  return (
    <div
      className="composer"
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
    >
      {isDragging && (
        <div className="composer-drop-zone">
          Drop images to attach
        </div>
      )}
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
        <div className="composer-input-wrap">
          <label className="sr-only" htmlFor="composer-input">Describe the app you want to build</label>
          <textarea
            id="composer-input"
            ref={textareaRef}
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
            maxLength={MAX_CHARS}
          />
          {(isNearLimit || isOverLimit) && (
            <div className="composer-char-count" aria-live="polite">
              <span className={isOverLimit ? "composer-char-count-over" : ""}>
                {charCount.toLocaleString()} / {MAX_CHARS.toLocaleString()}
              </span>
            </div>
          )}
        </div>
        {isStreaming ? (
          <Button variant="danger" size="md" className="composer-send" onClick={stop}>
            Stop
          </Button>
        ) : (
          <Button
            variant="primary"
            size="md"
            className="composer-send"
            onClick={send}
            disabled={(!text.trim() && attachments.length === 0) || isOverLimit}
          >
            Send
          </Button>
        )}
      </div>
    </div>
  );
}

// features/chat/Composer.tsx — the message input.
// Grows with the draft, sends on Enter (Shift+Enter for a newline, Ctrl/Cmd+Enter
// as an explicit alternative), carries image attachments, and swaps the single
// Send control for Stop while a turn is running. A failed send withdraws the
// optimistic row it added.
//
// The toolbar above the input holds context references, the prompt template
// library, the plan/act choice, and the model picker. The "/" menu is an inline
// autocomplete over the same template data (see ./templates.ts), so the two
// surfaces can never drift apart.

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { api, ApiError, type Attachment } from "../../lib/api";
import { useChatStore } from "./store";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { IconButton } from "../../components/ui/IconButton";
import { Button } from "../../components/ui/Button";
import { Menu } from "../../components/ui/Menu";
import { ModelPicker } from "./ModelPicker";
import { Icon } from "../../components/icons/Icon";
import { Kbd } from "../../components/ui/Kbd";
import { TEMPLATES, type PromptTemplate } from "./templates";
import {
  buildSlashCommands,
  filterSlashCommands,
  findSlashToken,
  CLEAR_COMMAND_ID,
} from "./slashCommands";

const MAX_CHARS = 4000;

/** Prepended when the user picks "Plan".
 *
 * This is a client-side prompt prefix, not a backend feature: the send request
 * carries only content and attachments (lib/api.ts), and the POST
 * /sessions/{sid}/messages handler reads no plan flag. Prefixing before the
 * optimistic row keeps the bubble identical to what the server logs and replays.
 */
const PLAN_PREFIX = "Before changing any files, outline a short plan and wait for my confirmation.";

export function Composer({ sessionId }: { sessionId: string }) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [planFirst, setPlanFirst] = useState(false);
  // null means the slash menu is closed; a string is the filter after "/".
  const [slashQuery, setSlashQuery] = useState<string | null>(null);
  const [activeSlashId, setActiveSlashId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // A caret to restore after the next text update. A ref rather than state: it
  // is written from callbacks and read once in the effect, and it must not
  // cause a second render.
  const pendingCaretRef = useRef<number | null>(null);
  const addOptimisticUserMessage = useChatStore((s) => s.addOptimisticUserMessage);
  const removeTimelineItem = useChatStore((s) => s.removeTimelineItem);
  const beginStream = useChatStore((s) => s.beginStream);
  const endStream = useChatStore((s) => s.endStream);
  const requestStop = useChatStore((s) => s.requestStop);
  const isStreaming = useChatStore((s) => s.isStreamingBySession[sessionId] ?? false);
  const pendingDraft = useChatStore((s) => s.pendingDraftBySession[sessionId]);
  const takePendingDraft = useChatStore((s) => s.takePendingDraft);

  const charCount = text.length;
  // The limit is only worth showing when it is about to matter. There is no
  // "over limit" state to track: the textarea's maxLength makes it unreachable.
  const isNearLimit = charCount > MAX_CHARS * 0.8;

  const slashCommands = useMemo(() => buildSlashCommands(), []);
  const slashMatches = useMemo(
    () => (slashQuery === null ? [] : filterSlashCommands(slashCommands, slashQuery)),
    [slashCommands, slashQuery]
  );
  // The highlighted command. Derived rather than stored so a filter change can
  // never leave the highlight pointing at a command that is no longer listed.
  const activeSlash =
    slashMatches.find((command) => command.id === activeSlashId) ?? slashMatches[0] ?? null;
  const slashOpen = slashQuery !== null && slashMatches.length > 0;

  // Grow with the draft instead of scrolling a one-line box. CSS caps the
  // height; past that the textarea scrolls.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text]);

  // Restore the caret after an edit that was not typed character by character
  // (a template insert, a path reference, accepting a slash command). Writing
  // the selection only after React has committed the new value avoids clamping
  // it against the old, shorter value.
  useEffect(() => {
    const caret = pendingCaretRef.current;
    if (caret === null) return;
    pendingCaretRef.current = null;
    textareaRef.current?.setSelectionRange(caret, caret);
  }, [text]);

  // A draft handed in from outside (the first-run example prompts) is adopted
  // during render - React's documented "adjust state when a value changes" path,
  // which avoids the cascading render an effect would cause. Each handoff has a
  // unique id, so adopting one is exact rather than a comparison of texts.
  const [adoptedDraftId, setAdoptedDraftId] = useState<number | null>(null);
  if (pendingDraft !== undefined && pendingDraft.id !== adoptedDraftId) {
    setAdoptedDraftId(pendingDraft.id);
    setText(pendingDraft.text);
  }

  // Clear the handoff once adopted, so remounting the composer cannot refill a
  // box the user already cleared or sent. This is an external-store update, not
  // component state: no render cascade, and nothing to adopt a second time.
  useEffect(() => {
    if (pendingDraft !== undefined) takePendingDraft(sessionId);
  }, [pendingDraft, sessionId, takePendingDraft]);

  const applyEdit = useCallback((nextText: string, caret: number) => {
    pendingCaretRef.current = caret;
    setText(nextText);
    setSlashQuery(null);
    setActiveSlashId(null);
  }, []);

  /** Put a template in the composer.
   *
   * Appends rather than replaces: a template must never discard a draft the
   * user already typed. An empty box starts with the template body. */
  const applyTemplate = useCallback(
    (template: PromptTemplate) => {
      if (text.trim().length === 0) {
        applyEdit(template.prompt, template.prompt.length);
      } else {
        const base = text.replace(/\s+$/, "");
        const next = `${base}\n\n${template.prompt}`;
        applyEdit(next, next.length);
      }
      textareaRef.current?.focus();
    },
    [applyEdit, text]
  );

  /** Insert a workspace path placeholder at the caret.
   *
   * There is no upload endpoint and no file/folder picker for prompt context,
   * so this inserts an editable reference the user fills in; see the report. */
  const insertReference = useCallback(
    (kind: "file" | "folder") => {
      const el = textareaRef.current;
      const start = el?.selectionStart ?? text.length;
      const end = el?.selectionEnd ?? start;
      const token = kind === "folder" ? "`path/to/folder/`" : "`path/to/file.tsx`";
      const next = `${text.slice(0, start)}${token}${text.slice(end)}`;
      applyEdit(next, start + token.length);
      el?.focus();
    },
    [applyEdit, text]
  );

  const acceptSlashCommand = useCallback(
    (commandId: string) => {
      const command = slashCommands.find((c) => c.id === commandId);
      const el = textareaRef.current;
      if (!command || !el) return;
      if (command.id === CLEAR_COMMAND_ID) {
        applyEdit("", 0);
        el.focus();
        return;
      }
      const template = TEMPLATES.find((t) => t.id === command.templateId);
      if (!template) return;
      // Remove the typed "/..." token, then insert into whatever is left.
      const token = findSlashToken(text, el.selectionStart ?? text.length);
      const rest = token ? text.slice(0, token.start) + text.slice(token.end) : text;
      if (rest.trim().length === 0) {
        applyEdit(template.prompt, template.prompt.length);
      } else {
        const base = rest.replace(/\s+$/, "");
        const next = `${base}\n\n${template.prompt}`;
        applyEdit(next, next.length);
      }
      el.focus();
    },
    [applyEdit, slashCommands, text]
  );

  const moveSlashActive = useCallback(
    (direction: 1 | -1) => {
      if (slashMatches.length === 0) return;
      const current = slashMatches.findIndex((c) => c.id === activeSlash?.id);
      const next = (current + direction + slashMatches.length) % slashMatches.length;
      setActiveSlashId(slashMatches[next].id);
    },
    [activeSlash, slashMatches]
  );

  const closeSlash = useCallback(() => {
    setSlashQuery(null);
    setActiveSlashId(null);
  }, []);

  const processFiles = useCallback((files: FileList | File[]) => {
    for (const f of Array.from(files)) {
      if (!f.type.startsWith("image/")) continue;
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result as string;
        const data_base64 = dataUrl.split(",")[1] ?? "";
        setAttachments((prev) => [
          ...prev,
          { name: f.name, content_type: f.type || "image/png", data_base64 },
        ]);
      };
      reader.readAsDataURL(f);
    }
  }, []);

  const onPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(e.target.files ?? []);
    e.target.value = "";
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      processFiles(e.dataTransfer.files);
    },
    [processFiles]
  );

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
    const draft = text;
    // Plan is applied to the outgoing text only; a failed send restores the
    // draft the user actually typed, not the prefixed copy.
    const outgoing = planFirst && text.trim() ? `${PLAN_PREFIX}\n\n${text}` : text;
    const snapshot = { text: outgoing, attachments };
    // Remember which row the optimistic add created: a failed send must
    // withdraw it, or the restored draft is sent as a second, duplicate message.
    const optimisticId = addOptimisticUserMessage(sessionId, outgoing);
    setText("");
    setAttachments([]);
    closeSlash();
    beginStream(sessionId);
    setError(null);
    try {
      await api.sendMessage(sessionId, snapshot.text, snapshot.attachments);
    } catch (e) {
      // Withdraw the row and restore the user's work — never swallow a failed
      // send, and never leave a message the server never received.
      removeTimelineItem(sessionId, optimisticId);
      setText(draft);
      setAttachments(snapshot.attachments);
      setError(
        e instanceof ApiError
          ? `${e.message}. Your message was kept.`
          : "Failed to send. Your message was kept."
      );
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

  const onChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setText(value);
    // The caret comes from the event, not from the end of the value: the user
    // may be editing in the middle of a longer draft.
    const caret = e.target.selectionStart ?? value.length;
    const token = findSlashToken(value, caret);
    setSlashQuery(token ? token.query : null);
    setActiveSlashId(null);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Never hijack a key mid-composition: every CJK input method sends Enter
    // and arrows while its candidate list is open.
    if (e.nativeEvent.isComposing) return;
    if (slashOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        moveSlashActive(1);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        moveSlashActive(-1);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (activeSlash) acceptSlashCommand(activeSlash.id);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        closeSlash();
        return;
      }
    }
    // Enter sends, Shift+Enter keeps the newline, and Ctrl/Cmd+Enter is the
    // explicit send chord. Shift is checked first so a newline is never sent.
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="composer" onDrop={onDrop} onDragOver={onDragOver} onDragLeave={onDragLeave}>
      {isDragging && <div className="composer-drop-zone">Drop images to attach</div>}
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
                type="button"
                onClick={() => setAttachments((prev) => prev.filter((_, j) => j !== i))}
                aria-label={`Remove ${a.name}`}
                className="composer-attachment-remove"
              >
                <Icon name="close" size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="composer-toolbar" role="toolbar" aria-label="Composer tools">
        <Menu
          label="Reference a file"
          align="start"
          tooltipSide="top"
          icon={<Icon name="attach" size={18} />}
          entries={[
            {
              id: "file",
              label: "Reference a file path",
              icon: <Icon name="file" size={16} />,
              onSelect: () => insertReference("file"),
            },
            {
              id: "folder",
              label: "Reference a folder path",
              icon: <Icon name="folder" size={16} />,
              onSelect: () => insertReference("folder"),
            },
          ]}
        />
        <Menu
          label="Prompt templates"
          align="start"
          tooltipSide="top"
          icon={<Icon name="sparkle" size={18} />}
          entries={TEMPLATES.map((template) => ({
            id: template.id,
            label: template.label,
            hint: `/${template.id}`,
            icon: <Icon name="wand" size={16} />,
            onSelect: () => applyTemplate(template),
          }))}
        />
        <div className="composer-mode" role="radiogroup" aria-label="Agent mode">
          <button
            type="button"
            role="radio"
            aria-checked={planFirst}
            className="composer-mode-option"
            onClick={() => setPlanFirst(true)}
            title="Ask the agent to outline a plan before it changes files"
          >
            Plan
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={!planFirst}
            className="composer-mode-option"
            onClick={() => setPlanFirst(false)}
            title="Let the agent make changes directly"
          >
            Act
          </button>
        </div>
        <span className="composer-toolbar-spacer" />
        <ModelPicker sessionId={sessionId} />
      </div>

      <div className="composer-row">
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          onChange={onPick}
          className="sr-only"
          aria-label="Attach image"
          // The visible IconButton below is the real control; without this the
          // clipped input is a second, invisible tab stop with the same name.
          tabIndex={-1}
        />
        <IconButton label="Attach image" onClick={() => fileRef.current?.click()}>
          <Icon name="attach" size={18} />
        </IconButton>
        <div className="composer-input-wrap">
          <label className="sr-only" htmlFor="composer-input">
            Describe the app you want to build
          </label>
          <textarea
            id="composer-input"
            ref={textareaRef}
            value={text}
            onChange={onChange}
            onKeyDown={onKeyDown}
            placeholder="Describe the app you want to build..."
            aria-label="Describe the app you want to build"
            aria-autocomplete="list"
            // aria-expanded belongs to combobox, and HTML-ARIA does not permit
            // role=combobox on a textarea, so the open state is carried by
            // aria-controls plus the active option below instead.
            aria-controls={slashOpen ? "composer-slash-list" : undefined}
            aria-activedescendant={
              slashOpen && activeSlash ? `composer-slash-${activeSlash.id}` : undefined
            }
            className="composer-input"
            rows={1}
            maxLength={MAX_CHARS}
          />
          {slashOpen && (
            <ul
              id="composer-slash-list"
              className="composer-slash"
              role="listbox"
              aria-label="Slash commands"
            >
              {slashMatches.map((command) => (
                <li
                  key={command.id}
                  id={`composer-slash-${command.id}`}
                  role="option"
                  aria-selected={command.id === activeSlash?.id}
                  className="composer-slash-option"
                  // Keep the caret in the textarea so accepting continues there.
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => acceptSlashCommand(command.id)}
                >
                  <span className="composer-slash-command">{command.command}</span>
                  <span className="composer-slash-text">
                    <span className="composer-slash-label">{command.label}</span>
                    {command.description ? (
                      <span className="composer-slash-desc">{command.description}</span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="composer-footer">
            {/* Enter sends on every platform, so the chord is identical on
                macOS and there is no platform-specific hint to render. Hidden
                on coarse pointers, where there is no Enter key. */}
            <span className="composer-hint">
              <Kbd keys={["Enter"]} /> send
              <Kbd keys={["Shift", "Enter"]} /> new line
            </span>
            {isNearLimit && (
              <span className="composer-char-count" aria-live="polite">
                {charCount.toLocaleString()} / {MAX_CHARS.toLocaleString()}
              </span>
            )}
          </div>
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
            disabled={!text.trim() && attachments.length === 0}
          >
            Send
          </Button>
        )}
      </div>
    </div>
  );
}

// features/chat/codeFences.ts — split assistant text into prose and code.
//
// The transcript used to hand the whole reply to a markdown renderer. The
// product only ever needs fenced blocks and plain prose, and a line scanner
// keeps the split testable and predictable while text is still streaming in.
// A fence that has not closed yet is still shown as code: the opening fence
// arrives before the body, and hiding the body would blank the response.

export interface TextSegment {
  kind: "text";
  content: string;
}

export interface CodeSegment {
  kind: "code";
  content: string;
  /** The info string on the opening fence; "" when there is none. */
  lang: string;
}

export type Segment = TextSegment | CodeSegment;

/** A line that opens or closes a fence. Group 1 is the info string. */
const FENCE = /^`{3,}\s*(.*)$/;

export function splitFences(source: string): Segment[] {
  if (source.length === 0) return [];

  const segments: Segment[] = [];
  const lines = source.split("\n");
  let text: string[] = [];
  let code: string[] = [];
  let lang = "";
  let inFence = false;

  const flushText = () => {
    if (text.length === 0) return;
    segments.push({ kind: "text", content: text.join("\n") });
    text = [];
  };
  const flushCode = () => {
    segments.push({ kind: "code", content: code.join("\n"), lang });
    code = [];
    lang = "";
  };

  for (const line of lines) {
    const match = line.trim().match(FENCE);
    if (!inFence) {
      if (match) {
        flushText();
        inFence = true;
        lang = match[1].trim().split(/\s+/)[0] ?? "";
      } else {
        text.push(line);
      }
    } else if (match && match[1].trim() === "") {
      // A bare fence closes; a fence with an info string is content, so an
      // opening fence indented inside a block is not mistaken for the close.
      flushCode();
      inFence = false;
    } else {
      code.push(line);
    }
  }

  if (inFence) flushCode();
  flushText();
  return segments;
}

// features/chat/__tests__/codeFences.test.ts
import { describe, it, expect } from "vitest";
import { splitFences } from "../codeFences";

describe("splitFences", () => {
  it("returns no segments for empty text", () => {
    expect(splitFences("")).toEqual([]);
  });

  it("returns one text segment when there is no fence", () => {
    expect(splitFences("just prose")).toEqual([{ kind: "text", content: "just prose" }]);
  });

  it("splits prose, a fenced block, and trailing prose", () => {
    const source = "Before\n```ts\nconst a = 1;\n```\nAfter";
    expect(splitFences(source)).toEqual([
      { kind: "text", content: "Before" },
      { kind: "code", content: "const a = 1;", lang: "ts" },
      { kind: "text", content: "After" },
    ]);
  });

  it("treats an unclosed fence as code", () => {
    const source = "Here:\n```py\nprint(1)";
    expect(splitFences(source)).toEqual([
      { kind: "text", content: "Here:" },
      { kind: "code", content: "print(1)", lang: "py" },
    ]);
  });

  it("keeps a fence with an info string inside a block as content", () => {
    const source = "```\n```js\nx\n```";
    expect(splitFences(source)).toEqual([{ kind: "code", content: "```js\nx", lang: "" }]);
  });

  it("does not treat a single backtick run as a fence", () => {
    expect(splitFences("a `code` b")).toEqual([{ kind: "text", content: "a `code` b" }]);
  });

  it("takes only the first token of the info string", () => {
    const source = "```ts title=x\nlet a;\n```";
    expect(splitFences(source)).toEqual([{ kind: "code", content: "let a;", lang: "ts" }]);
  });

  it("preserves blank lines inside a code block", () => {
    const source = "```\na\n\nb\n```";
    expect(splitFences(source)).toEqual([{ kind: "code", content: "a\n\nb", lang: "" }]);
  });
});

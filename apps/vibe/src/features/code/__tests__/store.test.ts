// apps/vibe/src/features/code/__tests__/store.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../../../lib/api", () => ({
  api: {
    listFiles: vi.fn(),
    readFile: vi.fn(),
    writeFile: vi.fn(),
  },
}));

import { api } from "../../../lib/api";
import { useCodeStore } from "../store";

beforeEach(() => {
  useCodeStore.setState({ files: [], selectedFile: null, contents: {} });
  vi.clearAllMocks();
});

describe("code store", () => {
  it("propagates a failed file-list read instead of reporting an empty session", async () => {
    // The swallow made a backend outage look like "no files yet"; the panel's
    // own error handling could never run.
    vi.mocked(api.listFiles).mockRejectedValue(new Error("API error: 500"));
    await expect(useCodeStore.getState().loadFiles("s1")).rejects.toThrow("API error: 500");
    expect(useCodeStore.getState().files).toEqual([]);
  });

  it("keeps the previous file list when a refresh fails", async () => {
    useCodeStore.setState({ files: ["src/App.tsx"] });
    vi.mocked(api.listFiles).mockRejectedValue(new Error("offline"));
    await expect(useCodeStore.getState().loadFiles("s1")).rejects.toThrow("offline");
    expect(useCodeStore.getState().files).toEqual(["src/App.tsx"]);
  });

  it("propagates a failed file read instead of caching an empty file", async () => {
    vi.mocked(api.readFile).mockRejectedValue(new Error("API error: 404"));
    await expect(useCodeStore.getState().loadFile("s1", "src/App.tsx")).rejects.toThrow(
      "API error: 404"
    );
    expect(useCodeStore.getState().contents["src/App.tsx"]).toBeUndefined();
  });

  it("stores file contents on a successful read", async () => {
    vi.mocked(api.readFile).mockResolvedValue({ path: "src/App.tsx", content: "hello" });
    await useCodeStore.getState().loadFile("s1", "src/App.tsx");
    expect(useCodeStore.getState().contents["src/App.tsx"]).toBe("hello");
  });
});

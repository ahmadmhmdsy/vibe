// apps/vibe/src/features/sessions/__tests__/SessionsPanel.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";

vi.mock("../../../lib/api", () => ({
  api: {
    listSessions: vi.fn().mockResolvedValue([]),
    getCatalog: vi.fn().mockResolvedValue([]),
    deleteSession: vi.fn().mockResolvedValue(undefined),
    renameSession: vi.fn().mockResolvedValue({ ok: true }),
  },
}));

import { api, type Session } from "../../../lib/api";
import { SessionsPanel } from "../SessionsPanel";
import { useSessionsStore } from "../store";

const daysAgo = (days: number) => new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

function session(overrides: Partial<Session> & { id: string; title: string }): Session {
  const stamp = daysAgo(0);
  return {
    model: { provider_id: "openai", model_id: "gpt-4o" },
    created_at: stamp,
    updated_at: stamp,
    ...overrides,
  };
}

/**
 * Matches a row by title from the start of its accessible name. Anchored on
 * purpose: every row's own menu trigger is labelled "Session actions for
 * <title>", which an unanchored /<title>/ would also match.
 */
const rowName = (title: string) => new RegExp("^" + title);

/** Seed both the store and the list endpoint the mount effect re-reads. */
function show(sessions: Session[], activeId: string | null) {
  vi.mocked(api.listSessions).mockResolvedValue(sessions);
  useSessionsStore.setState({ sessions, activeId });
}

afterEach(() => {
  cleanup();
  useSessionsStore.setState({ sessions: [], activeId: null });
  vi.mocked(api.listSessions).mockReset().mockResolvedValue([]);
  vi.mocked(api.getCatalog).mockReset().mockResolvedValue([]);
  vi.mocked(api.deleteSession).mockReset().mockResolvedValue(undefined);
  vi.mocked(api.renameSession).mockReset().mockResolvedValue({ ok: true });
});

describe("SessionsPanel", () => {
  it("names the panel and keeps new session as the primary action", async () => {
    show([session({ id: "s1", title: "My app" })], "s1");
    render(<SessionsPanel />);

    expect(screen.getByRole("heading", { name: "Sessions", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New session" })).toBeInTheDocument();
    // The list has its own accessible name rather than being an unnamed pile.
    expect(await screen.findByRole("navigation", { name: "Sessions" })).toBeInTheDocument();
    // The count travels with the title.
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows an empty state with a CTA when there are no sessions", async () => {
    show([], null);
    render(<SessionsPanel />);

    const title = await screen.findByText(/no sessions yet/i);
    const block = title.closest(".empty-state") as HTMLElement;
    expect(within(block).getByRole("button", { name: "New session" })).toBeInTheDocument();
  });

  it("groups sessions under a recency heading and skips empty buckets", async () => {
    const today = session({ id: "s1", title: "Today app" });
    const old = session({
      id: "s2",
      title: "Old app",
      created_at: daysAgo(45),
      updated_at: daysAgo(45),
    });
    show([today, old], "s1");
    render(<SessionsPanel />);

    const todaySection = await screen.findByRole("region", { name: "Today" });
    expect(
      within(todaySection).getByRole("button", { name: rowName("Today app") })
    ).toBeInTheDocument();
    expect(within(todaySection).queryByRole("button", { name: rowName("Old app") })).toBeNull();

    const olderSection = screen.getByRole("region", { name: "Older" });
    expect(
      within(olderSection).getByRole("button", { name: rowName("Old app") })
    ).toBeInTheDocument();

    // A bucket with nothing in it is not rendered at all.
    expect(screen.queryByRole("region", { name: "Yesterday" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Previous 7 days" })).toBeNull();
  });

  it("filters by title and model, drops the buckets, and reports the count", async () => {
    show(
      [
        session({ id: "s1", title: "Alpha app" }),
        session({
          id: "s2",
          title: "Beta app",
          model: { provider_id: "anthropic", model_id: "claude-sonnet" },
        }),
      ],
      "s1"
    );
    render(<SessionsPanel />);

    const search = await screen.findByLabelText("Search sessions");

    fireEvent.change(search, { target: { value: "beta" } });
    expect(screen.getByText("1 result")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: rowName("Beta app") })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: rowName("Alpha app") })).toBeNull();
    // Grouping a filtered list would hide matches behind headings.
    expect(screen.queryByRole("region", { name: "Today" })).toBeNull();

    // A model id matches too.
    fireEvent.change(search, { target: { value: "claude" } });
    expect(screen.getByText("1 result")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: rowName("Beta app") })).toBeInTheDocument();

    // Clearing the field restores the grouped view.
    fireEvent.click(screen.getByRole("button", { name: "Clear search sessions" }));
    expect(screen.getByRole("region", { name: "Today" })).toBeInTheDocument();
    expect(screen.queryByText(/result/)).toBeNull();
  });

  it("matches a model's display name from the catalog", async () => {
    vi.mocked(api.getCatalog).mockResolvedValue([
      {
        id: "anthropic",
        name: "Anthropic",
        capabilities: { tool_support: true, vision: true },
        models: [{ id: "claude-sonnet", name: "Claude Sonnet" }],
        key_configured: true,
      },
    ]);
    show(
      [
        session({
          id: "s1",
          title: "Alpha app",
          model: { provider_id: "anthropic", model_id: "claude-sonnet" },
        }),
      ],
      "s1"
    );
    render(<SessionsPanel />);

    expect(await screen.findByText("Claude Sonnet")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search sessions"), {
      target: { value: "claude sonnet" },
    });
    expect(screen.getByText("1 result")).toBeInTheDocument();
  });

  it("shows a distinct no-results state and a zero count", async () => {
    show([session({ id: "s1", title: "Alpha app" })], "s1");
    render(<SessionsPanel />);

    const search = await screen.findByLabelText("Search sessions");
    fireEvent.change(search, { target: { value: "zzz" } });

    expect(await screen.findByText(/no sessions match/i)).toBeInTheDocument();
    expect(screen.getByText("0 results")).toBeInTheDocument();
    // Not the first-run state.
    expect(screen.queryByText(/no sessions yet/i)).toBeNull();
  });

  it("keeps exactly one row in the tab order and moves focus with the arrow keys", async () => {
    show(
      [
        session({ id: "s1", title: "First" }),
        session({ id: "s2", title: "Second" }),
        session({ id: "s3", title: "Third" }),
      ],
      "s2"
    );
    const { container } = render(<SessionsPanel />);

    await screen.findByRole("button", { name: rowName("First") });
    const rows = Array.from(container.querySelectorAll<HTMLButtonElement>(".session-select"));
    expect(rows).toHaveLength(3);
    expect(rows.filter((row) => row.tabIndex === 0)).toHaveLength(1);
    // The active session owns the one tab stop.
    expect(rows[1]).toHaveAttribute("tabindex", "0");
    expect(rows[1]).toHaveAttribute("aria-current", "true");
    expect(rows[0]).not.toHaveAttribute("aria-current");

    fireEvent.keyDown(rows[1], { key: "ArrowDown" });
    expect(document.activeElement).toBe(rows[2]);
    expect(rows.filter((row) => row.tabIndex === 0)).toHaveLength(1);
    expect(rows[2]).toHaveAttribute("tabindex", "0");

    fireEvent.keyDown(rows[2], { key: "ArrowUp" });
    expect(document.activeElement).toBe(rows[1]);

    fireEvent.keyDown(rows[1], { key: "End" });
    expect(document.activeElement).toBe(rows[2]);
    fireEvent.keyDown(rows[2], { key: "Home" });
    expect(document.activeElement).toBe(rows[0]);

    // Clicking a row selects it; Enter and Space are native button activation.
    fireEvent.click(rows[0]);
    expect(rows[0]).toHaveAttribute("aria-current", "true");
  });

  it("asks for confirmation before deleting, naming the session", async () => {
    show([session({ id: "s1", title: "My app" })], "s1");
    render(<SessionsPanel />);

    const trigger = await screen.findByRole("button", { name: "Session actions for My app" });
    fireEvent.click(trigger);

    const menu = screen.getByRole("menu", { name: "Session actions for My app" });
    expect(within(menu).getByRole("menuitem", { name: "Rename" })).toBeInTheDocument();
    expect(within(menu).getByRole("menuitem", { name: "Export" })).toBeInTheDocument();
    fireEvent.click(within(menu).getByRole("menuitem", { name: "Delete" }));

    expect(screen.getByRole("alertdialog", { name: 'Delete "My app"?' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(vi.mocked(api.deleteSession)).toHaveBeenCalledWith("s1");
  });

  it("renames inline from the row menu and returns focus to the row", async () => {
    show([session({ id: "s1", title: "My app" })], "s1");
    render(<SessionsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Session actions for My app" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));

    const input = screen.getByLabelText("Session title");
    fireEvent.change(input, { target: { value: "Renamed app" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() =>
      expect(vi.mocked(api.renameSession)).toHaveBeenCalledWith("s1", "Renamed app")
    );
    await waitFor(() => expect(document.activeElement).toHaveClass("session-select"));
  });

  it("cancels an inline rename on Escape without saving", async () => {
    show([session({ id: "s1", title: "My app" })], "s1");
    render(<SessionsPanel />);

    fireEvent.click(await screen.findByRole("button", { name: "Session actions for My app" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));

    fireEvent.change(screen.getByLabelText("Session title"), { target: { value: "Nope" } });
    fireEvent.keyDown(screen.getByLabelText("Session title"), { key: "Escape" });

    expect(screen.queryByLabelText("Session title")).toBeNull();
    expect(vi.mocked(api.renameSession)).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toHaveClass("session-select"));
  });

  it("shows an error banner when loading sessions fails", async () => {
    vi.mocked(api.listSessions).mockRejectedValueOnce(new Error("API error: 400"));
    render(<SessionsPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/API error: 400/);
  });
});

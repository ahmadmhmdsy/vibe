// apps/vibe/src/features/vcs/__tests__/SourceControlPanel.test.tsx
//
// The panel's job is to keep three states apart: not a repository, changed
// files, and a clean tree. Getting "nothing to commit" wrong would tell the
// user their work was lost when it was in fact already saved.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { api } from "../../../lib/api";
import { ToastProvider } from "../../../components/ui";
import { SourceControlPanel } from "../SourceControlPanel";
import { useVcsStore } from "../store";

vi.mock("../../../lib/api", () => ({
  api: {
    vcsStatus: vi.fn(),
    vcsLog: vi.fn(),
    vcsDiff: vi.fn(),
    vcsCommit: vi.fn(),
    vcsInit: vi.fn(),
    vcsBranch: vi.fn(),
  },
}));

const mocked = vi.mocked(api, true);

beforeEach(() => {
  vi.clearAllMocks();
  useVcsStore.setState({ bySession: {} });
  mocked.vcsLog.mockResolvedValue([]);
});

afterEach(cleanup);

describe("SourceControlPanel", () => {
  it("offers to create a repository when the workspace is not one", async () => {
    mocked.vcsStatus.mockResolvedValue({ is_repo: false, branch: null, files: [] });
    mocked.vcsInit.mockResolvedValue({ branch: "main" });

    render(<SourceControlPanel sessionId="s1" active />);

    const create = await screen.findByRole("button", { name: "Create repository" });
    // Nothing that only makes sense inside a repository is on screen.
    expect(screen.queryByLabelText(/commit message/i)).not.toBeInTheDocument();

    mocked.vcsStatus.mockResolvedValue({
      is_repo: true,
      branch: "main",
      files: [{ path: "src/App.tsx", status: "M", staged: false }],
    });
    fireEvent.click(create);

    await waitFor(() => expect(mocked.vcsInit).toHaveBeenCalledWith("s1"));
    // Re-read after init: the panel must switch to the repository view.
    expect(await screen.findByText("App.tsx")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
  });

  it("reads one file's diff when a change is selected", async () => {
    mocked.vcsStatus.mockResolvedValue({
      is_repo: true,
      branch: "main",
      files: [{ path: "src/App.tsx", status: "M", staged: false }],
    });
    mocked.vcsDiff.mockResolvedValue({ diff: "-old\n+new", truncated: false });

    render(<SourceControlPanel sessionId="s1" active />);

    fireEvent.click(await screen.findByText("App.tsx"));

    await waitFor(() => expect(mocked.vcsDiff).toHaveBeenCalledWith("s1", { path: "src/App.tsx" }));
    expect(await screen.findByText(/\+new/)).toBeInTheDocument();
  });

  it("says nothing to commit rather than failing when the tree is clean", async () => {
    mocked.vcsStatus.mockResolvedValue({
      is_repo: true,
      branch: "main",
      files: [{ path: "src/App.tsx", status: "M", staged: false }],
    });
    mocked.vcsCommit.mockResolvedValue({ sha: null, committed: false });

    // Inside a provider, because the "nothing to commit" answer is only ever
    // reported through a toast.
    render(
      <ToastProvider>
        <SourceControlPanel sessionId="s1" active />
      </ToastProvider>
    );

    fireEvent.change(await screen.findByLabelText(/commit message/i), {
      target: { value: "tweak the header" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Commit/ }));

    await waitFor(() => expect(mocked.vcsCommit).toHaveBeenCalledWith("s1", "tweak the header"));
    expect(await screen.findByText(/Nothing to commit/i)).toBeInTheDocument();
  });

  it("keeps the commit button disabled until a message is typed", async () => {
    mocked.vcsStatus.mockResolvedValue({
      is_repo: true,
      branch: "main",
      files: [{ path: "src/App.tsx", status: "M", staged: false }],
    });

    render(<SourceControlPanel sessionId="s1" active />);

    const button = await screen.findByRole("button", { name: /^Commit/ });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/commit message/i), { target: { value: "x" } });
    expect(button).not.toBeDisabled();
  });
});

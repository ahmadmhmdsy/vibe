// apps/vibe/src/features/sessions/__tests__/NewSessionDialog.test.tsx
//
// The wire shape is the thing worth pinning: the backend only needs `kind`,
// and a folder path or a git url sent under the wrong kind would create the
// wrong workspace (or none).
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import { NewSessionDialog } from "../NewSessionDialog";

afterEach(cleanup);

describe("NewSessionDialog", () => {
  it("creates an empty workspace by default", async () => {
    const onCreate = vi.fn().mockResolvedValue("s1");
    render(<NewSessionDialog open onClose={() => {}} onCreate={onCreate} />);

    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith({ kind: "empty" }));
  });

  it("sends a folder path only with the folder kind", async () => {
    const onCreate = vi.fn().mockResolvedValue("s1");
    render(<NewSessionDialog open onClose={() => {}} onCreate={onCreate} />);

    fireEvent.click(screen.getByRole("radio", { name: /import a folder/i }));
    // Nothing to send yet: the button stays disabled until a path is typed.
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/folder path/i), {
      target: { value: "C:\\projects\\my-app" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith({ kind: "folder", path: "C:\\projects\\my-app" })
    );
  });

  it("keeps the dialog open and shows the backend's message on failure", async () => {
    const onClose = vi.fn();
    const onCreate = vi.fn().mockRejectedValue(new Error("not a folder: C:\\nope"));
    render(<NewSessionDialog open onClose={onClose} onCreate={onCreate} />);

    fireEvent.click(screen.getByRole("radio", { name: /clone a repository/i }));
    fireEvent.change(screen.getByLabelText(/repository url/i), {
      target: { value: "https://example.test/repo.git" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    expect(await screen.findByText("not a folder: C:\\nope")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});

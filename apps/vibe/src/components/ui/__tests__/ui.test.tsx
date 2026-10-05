// apps/vibe/src/components/ui/__tests__/ui.test.tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Button } from "../Button";
import { IconButton } from "../IconButton";
import { Modal } from "../Modal";
import { ConfirmDialog } from "../ConfirmDialog";
import { Spinner } from "../Spinner";
import { EmptyState } from "../EmptyState";
import { ErrorBanner } from "../ErrorBanner";

afterEach(cleanup);

const svgIcon = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 16"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    aria-hidden="true"
  >
    <circle cx="8" cy="8" r="6" />
  </svg>
);

describe("Button", () => {
  it("renders children and handles click", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Send</Button>);
    const btn = screen.getByRole("button", { name: "Send" });
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("applies variant class", () => {
    render(<Button variant="primary">Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveClass("btn-primary");
  });

  it("shows spinner and disables while loading", () => {
    render(<Button loading>Working</Button>);
    const btn = screen.getByRole("button", { name: /working/i });
    expect(btn).toBeDisabled();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("IconButton", () => {
  it("requires an accessible label", () => {
    render(
      <IconButton label="Attach image" onClick={() => {}}>
        {svgIcon}
      </IconButton>
    );
    expect(screen.getByRole("button", { name: "Attach image" })).toBeInTheDocument();
  });

  it("meets the 44px touch target (icon-btn class carries the size)", () => {
    render(
      <IconButton label="Settings" onClick={() => {}}>
        {svgIcon}
      </IconButton>
    );
    expect(screen.getByRole("button", { name: "Settings" })).toHaveClass("icon-btn");
  });
});

describe("Modal", () => {
  it("renders dialog with title and closes on Esc", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Settings">
        <p>modal content</p>
      </Modal>
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("modal content")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on backdrop click but not on content click", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Settings">
        <p>dialog body</p>
      </Modal>
    );
    fireEvent.click(screen.getByText("dialog body"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("modal-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not render when closed", () => {
    render(
      <Modal open={false} onClose={() => {}} title="Settings">
        <p>hidden</p>
      </Modal>
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("ConfirmDialog", () => {
  it("calls onConfirm and onCancel", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={onCancel}
        onConfirm={onConfirm}
        title="Delete session?"
        body="This permanently removes the session and its history."
        confirmLabel="Delete"
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("cancels on Enter and Escape", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={onCancel}
        onConfirm={onConfirm}
        title="Delete session?"
        body="body"
        confirmLabel="Delete"
      />
    );
    fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Enter" });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onCancel).toHaveBeenCalledOnce();
  });
});

describe("Spinner", () => {
  it("has role=status for screen readers", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders title, body and optional CTA", () => {
    render(
      <EmptyState
        title="No files yet"
        body="The agent has not written any."
        action={<button>New</button>}
      />
    );
    expect(screen.getByText("No files yet")).toBeInTheDocument();
    expect(screen.getByText(/has not written any/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });
});

describe("ErrorBanner", () => {
  it("renders message and retry", () => {
    const onRetry = vi.fn();
    render(<ErrorBanner message="API error: 400" onRetry={onRetry} />);
    expect(screen.getByText(/API error: 400/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});

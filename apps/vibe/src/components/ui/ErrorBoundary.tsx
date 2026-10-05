// components/ui/ErrorBoundary.tsx — Error boundary for panel-level isolation.
// Prevents a crash in one panel from taking down the entire app.

import { Component, type ReactNode } from "react";
import { ErrorBanner } from "./ErrorBanner";
import { Button } from "./Button";

interface Props {
  children: ReactNode;
  /** Fallback UI to show on error */
  fallback?: ReactNode;
  /** Reset key — changing this resets the error state */
  resetKey?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.hasError) {
      this.setState({ hasError: false, error: null });
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="error-boundary">
          <ErrorBanner
            message={this.state.error?.message ?? "Something went wrong"}
            onRetry={() => this.setState({ hasError: false, error: null })}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Dismiss
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}

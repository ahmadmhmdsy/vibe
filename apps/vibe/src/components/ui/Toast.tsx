// components/ui/Toast.tsx — Toast notification system.
// Provides transient feedback for user actions.

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import { IconButton } from "./IconButton";

type ToastVariant = "success" | "error" | "info" | "warning";

interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** No-op outside a provider so panels stay renderable on their own. */
const NO_PROVIDER: ToastContextValue = { toast: () => {} };

export function useToast(): ToastContextValue {
  return useContext(ToastContext) ?? NO_PROVIDER;
}

let toastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = String(++toastId);
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => dismiss(id), 4000);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="toast-container" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.variant}`} role="status">
            <span className="toast-message">{t.message}</span>
            <IconButton label="Dismiss" onClick={() => dismiss(t.id)}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
              </svg>
            </IconButton>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

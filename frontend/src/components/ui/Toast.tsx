"use client";

import { useEffect, useState, useCallback, createContext, useContext, type ReactNode } from "react";
import { CheckCircle, XCircle, X, Info } from "@phosphor-icons/react";
import { clsx } from "clsx";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  toast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let toastId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const iconMap = {
    success: CheckCircle,
    error: XCircle,
    info: Info,
  };

  const colorMap = {
    success: "border-emerald-500/30 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300",
    error: "border-red-500/30 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300",
    info: "border-blue-500/30 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300",
  };

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => {
          const Icon = iconMap[t.type];
          return (
            <div
              key={t.id}
              className={clsx(
                "pointer-events-auto flex items-center gap-2.5 px-4 py-2.5 rounded-lg border shadow-sm text-sm",
                "slide-in-right",
                colorMap[t.type],
              )}
            >
              <Icon size={16} weight="fill" className="shrink-0" />
              <span className="flex-1">{t.message}</span>
              <button onClick={() => removeToast(t.id)} className="p-0.5 rounded hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

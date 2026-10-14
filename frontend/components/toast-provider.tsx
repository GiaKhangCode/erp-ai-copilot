"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
}

export interface PromptOptions {
  title: string;
  message: string;
  placeholder?: string;
  defaultValue?: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  multiline?: boolean;
}

interface ToastContextValue {
  showToast: (toast: Omit<ToastItem, "id">) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  prompt: (options: PromptOptions) => Promise<string | null>;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  // Confirm dialog state
  const [confirmState, setConfirmState] = useState<{
    isOpen: boolean;
    options: ConfirmOptions;
    resolve: (value: boolean) => void;
  } | null>(null);

  // Prompt dialog state
  const [promptState, setPromptState] = useState<{
    isOpen: boolean;
    options: PromptOptions;
    inputValue: string;
    resolve: (value: string | null) => void;
  } | null>(null);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    ({ type, title, message, duration = 4000 }: Omit<ToastItem, "id">) => {
      const id = "toast_" + Date.now() + "_" + Math.random().toString(36).slice(2, 7);
      const newToast: ToastItem = { id, type, title, message, duration };

      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const success = useCallback(
    (title: string, message?: string) => showToast({ type: "success", title, message }),
    [showToast]
  );

  const error = useCallback(
    (title: string, message?: string) => showToast({ type: "error", title, message }),
    [showToast]
  );

  const info = useCallback(
    (title: string, message?: string) => showToast({ type: "info", title, message }),
    [showToast]
  );

  const warning = useCallback(
    (title: string, message?: string) => showToast({ type: "warning", title, message }),
    [showToast]
  );

  const confirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmState({
        isOpen: true,
        options,
        resolve,
      });
    });
  }, []);

  const handleConfirmChoice = (choice: boolean) => {
    if (confirmState) {
      confirmState.resolve(choice);
      setConfirmState(null);
    }
  };

  const prompt = useCallback((options: PromptOptions): Promise<string | null> => {
    return new Promise((resolve) => {
      setPromptState({
        isOpen: true,
        options,
        inputValue: options.defaultValue || "",
        resolve,
      });
    });
  }, []);

  const handlePromptChoice = (confirmed: boolean) => {
    if (promptState) {
      if (confirmed) {
        promptState.resolve(promptState.inputValue.trim());
      } else {
        promptState.resolve(null);
      }
      setPromptState(null);
    }
  };

  return (
    <ToastContext.Provider value={{ showToast, success, error, info, warning, confirm, prompt }}>
      {children}

      {/* Container Toast Notifications */}
      <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
        {toasts.map((t) => {
          const typeConfig = {
            success: {
              border: "border-emerald-200 bg-white/95 text-emerald-950",
              iconBg: "bg-emerald-100 text-emerald-600",
              icon: <CheckCircle2 className="w-4 h-4" />,
            },
            error: {
              border: "border-rose-200 bg-white/95 text-rose-950",
              iconBg: "bg-rose-100 text-rose-600",
              icon: <AlertCircle className="w-4 h-4" />,
            },
            warning: {
              border: "border-amber-200 bg-white/95 text-amber-950",
              iconBg: "bg-amber-100 text-amber-600",
              icon: <AlertTriangle className="w-4 h-4" />,
            },
            info: {
              border: "border-blue-200 bg-white/95 text-blue-950",
              iconBg: "bg-blue-100 text-blue-600",
              icon: <Info className="w-4 h-4" />,
            },
          }[t.type];

          return (
            <div
              key={t.id}
              className={`pointer-events-auto p-3.5 rounded-2xl shadow-xl backdrop-blur-md border ${typeConfig.border} flex items-start gap-3 transition-all duration-300 animate-in fade-in slide-in-from-bottom-3`}
            >
              <div className={`p-1.5 rounded-xl shrink-0 ${typeConfig.iconBg}`}>
                {typeConfig.icon}
              </div>
              <div className="flex-1 min-w-0 pr-1">
                <h4 className="text-xs font-bold leading-tight">{t.title}</h4>
                {t.message && (
                  <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed line-clamp-3">
                    {t.message}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => removeToast(t.id)}
                className="text-slate-400 hover:text-slate-600 p-0.5 rounded-md transition-colors"
                title="Đóng"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Confirmation Dialog Modal */}
      {confirmState?.isOpen && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-md w-full shadow-2xl border border-slate-200/90 overflow-hidden transform scale-100 animate-in zoom-in-95 duration-200">
            <div className="p-5">
              <div className="flex items-center gap-3 mb-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    confirmState.options.isDanger
                      ? "bg-rose-100 text-rose-600"
                      : "bg-blue-100 text-blue-600"
                  }`}
                >
                  {confirmState.options.isDanger ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : (
                    <Info className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {confirmState.options.title}
                  </h3>
                  <span className="text-[11px] text-slate-400">Xác nhận thao tác hệ thống</span>
                </div>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-line pl-1 mb-4">
                {confirmState.options.message}
              </p>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handleConfirmChoice(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  {confirmState.options.cancelText || "Hủy bỏ"}
                </button>
                <button
                  type="button"
                  onClick={() => handleConfirmChoice(true)}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold text-white shadow-xs transition-colors cursor-pointer ${
                    confirmState.options.isDanger
                      ? "bg-rose-600 hover:bg-rose-700"
                      : "bg-blue-600 hover:bg-blue-700"
                  }`}
                >
                  {confirmState.options.confirmText || "Xác nhận"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Prompt Dialog Modal */}
      {promptState?.isOpen && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-slate-200/90 overflow-hidden transform scale-100 animate-in zoom-in-95 duration-200">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handlePromptChoice(true);
              }}
              className="p-5"
            >
              <div className="flex items-center gap-3 mb-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    promptState.options.isDanger
                      ? "bg-rose-100 text-rose-600"
                      : "bg-blue-100 text-blue-600"
                  }`}
                >
                  {promptState.options.isDanger ? (
                    <AlertTriangle className="w-5 h-5" />
                  ) : (
                    <Info className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {promptState.options.title}
                  </h3>
                  <span className="text-[11px] text-slate-400">Yêu cầu nhập thông tin</span>
                </div>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-line pl-1 mb-3">
                {promptState.options.message}
              </p>

              <div className="mb-4">
                <textarea
                  autoFocus
                  rows={3}
                  value={promptState.inputValue}
                  onChange={(e) =>
                    setPromptState((prev) =>
                      prev ? { ...prev, inputValue: e.target.value } : null
                    )
                  }
                  placeholder={promptState.options.placeholder || "Nhập nội dung..."}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-hidden text-xs text-slate-800 placeholder:text-slate-400 resize-none transition-all"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handlePromptChoice(true);
                    }
                  }}
                />
                <span className="text-[10px] text-slate-400 block mt-1">
                  Nhấn <kbd className="font-mono bg-slate-100 px-1 py-0.5 rounded text-[9.5px]">Enter</kbd> để xác nhận, <kbd className="font-mono bg-slate-100 px-1 py-0.5 rounded text-[9.5px]">Shift + Enter</kbd> để xuống dòng
                </span>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => handlePromptChoice(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  {promptState.options.cancelText || "Hủy bỏ"}
                </button>
                <button
                  type="submit"
                  className={`px-4 py-2 rounded-xl text-xs font-semibold text-white shadow-xs transition-colors cursor-pointer ${
                    promptState.options.isDanger
                      ? "bg-rose-600 hover:bg-rose-700"
                      : "bg-blue-600 hover:bg-blue-700"
                  }`}
                >
                  {promptState.options.confirmText || "Xác nhận"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}

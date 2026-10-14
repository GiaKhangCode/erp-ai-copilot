"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertOctagon, RefreshCw, Home, ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
    showDetails: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error caught by ErrorBoundary:", error, errorInfo);
    this.setState({ errorInfo });
  }

  private handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    });
    window.location.reload();
  };

  private toggleDetails = () => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-[400px] h-full w-full flex items-center justify-center p-6 bg-slate-50/50">
          <div className="max-w-lg w-full bg-white rounded-3xl border border-slate-200/90 shadow-xl p-8 text-center animate-in fade-in zoom-in-95 duration-200">
            <div className="w-16 h-16 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-5 shadow-xs border border-rose-100">
              <AlertOctagon className="w-8 h-8" />
            </div>

            <h2 className="text-xl font-bold text-slate-900 mb-2">
              Đã xảy ra sự cố không mong muốn
            </h2>
            <p className="text-xs text-slate-500 mb-6 leading-relaxed">
              Thành phần giao diện gặp lỗi trong quá trình kết xuất dữ liệu. Bạn có thể thử tải lại trang hoặc quay về trang chủ.
            </p>

            <div className="flex items-center justify-center gap-3 mb-6">
              <button
                type="button"
                onClick={this.handleReset}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 shadow-sm transition-all cursor-pointer"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Tải lại trang</span>
              </button>
              <a
                href="/dashboard"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-100 text-slate-700 text-xs font-semibold hover:bg-slate-200 transition-colors cursor-pointer"
              >
                <Home className="w-4 h-4" />
                <span>Về Bảng điều khiển</span>
              </a>
            </div>

            {/* Chi tiết lỗi kỹ thuật */}
            {this.state.error && (
              <div className="text-left border-t border-slate-100 pt-4">
                <button
                  type="button"
                  onClick={this.toggleDetails}
                  className="w-full flex items-center justify-between text-[11px] font-semibold text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  <span>Chi tiết kỹ thuật (Developer Info)</span>
                  {this.state.showDetails ? (
                    <ChevronUp className="w-3.5 h-3.5" />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" />
                  )}
                </button>

                {this.state.showDetails && (
                  <div className="mt-3 p-3 bg-slate-900 rounded-xl text-slate-100 font-mono text-[10.5px] overflow-x-auto max-h-48">
                    <p className="text-rose-400 font-bold mb-1">
                      {this.state.error.name}: {this.state.error.message}
                    </p>
                    {this.state.error.stack && (
                      <pre className="text-slate-400 whitespace-pre-wrap leading-tight text-[10px]">
                        {this.state.error.stack}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

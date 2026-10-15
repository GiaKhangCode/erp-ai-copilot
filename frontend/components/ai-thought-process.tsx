"use client";

import React, { useState } from "react";
import {
  Brain,
  Database,
  FileSearch,
  Sparkles,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronUp,
  PackageCheck,
  Workflow,
} from "lucide-react";
import { ThoughtStep } from "@/lib/api";

interface AiThoughtProcessProps {
  thoughtSteps?: ThoughtStep[];
  isStreaming?: boolean;
}

export function AiThoughtProcess({
  thoughtSteps,
  isStreaming = false,
}: AiThoughtProcessProps) {
  const [isOpen, setIsOpen] = useState<boolean>(true);

  if (!thoughtSteps || thoughtSteps.length === 0) {
    return null;
  }

  const isRunning =
    isStreaming || thoughtSteps.some((s) => s.status === "running");

  const getStepIcon = (step: string) => {
    if (step === "intent" || step === "super_agent") {
      return <Brain className="w-3.5 h-3.5 text-blue-600 shrink-0" />;
    }
    if (step.includes("knowledge") || step === "rag") {
      return <FileSearch className="w-3.5 h-3.5 text-violet-600 shrink-0" />;
    }
    if (step.includes("draft") || step.includes("propose")) {
      return <PackageCheck className="w-3.5 h-3.5 text-amber-600 shrink-0" />;
    }
    if (
      step.includes("inventory") ||
      step.includes("product") ||
      step.includes("customer") ||
      step.includes("sales") ||
      step.includes("revenue") ||
      step === "db"
    ) {
      return <Database className="w-3.5 h-3.5 text-sky-600 shrink-0" />;
    }
    if (step === "synthesis") {
      return <Sparkles className="w-3.5 h-3.5 text-indigo-600 shrink-0" />;
    }
    return <Workflow className="w-3.5 h-3.5 text-slate-500 shrink-0" />;
  };

  const getStepTag = (step: string) => {
    if (step.includes("knowledge") || step === "rag") {
      return (
        <span className="text-[10px] font-semibold text-violet-700 bg-violet-50 border border-violet-200/80 px-1.5 py-0.2 rounded-md">
          Tài liệu nội bộ (RAG)
        </span>
      );
    }
    if (step.includes("draft") || step.includes("propose")) {
      return (
        <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200/80 px-1.5 py-0.2 rounded-md">
          Đề xuất HITL
        </span>
      );
    }
    if (
      step.includes("inventory") ||
      step.includes("product") ||
      step.includes("customer") ||
      step.includes("sales") ||
      step.includes("revenue") ||
      step === "db"
    ) {
      return (
        <span className="text-[10px] font-semibold text-sky-700 bg-sky-50 border border-sky-200/80 px-1.5 py-0.2 rounded-md">
          Cơ sở dữ liệu ERP
        </span>
      );
    }
    if (step === "super_agent") {
      return (
        <span className="text-[10px] font-semibold text-blue-700 bg-blue-50 border border-blue-200/80 px-1.5 py-0.2 rounded-md">
          Điều phối ReAct
        </span>
      );
    }
    return null;
  };

  return (
    <div className="mb-3 rounded-xl border border-slate-200/90 bg-slate-50/70 overflow-hidden text-left transition-all">
      {/* Header nút đóng mở */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3.5 py-2.5 bg-white/60 hover:bg-white text-xs font-semibold text-slate-700 transition-colors cursor-pointer select-none group"
      >
        <div className="flex items-center gap-2">
          <div
            className={`w-5 h-5 rounded-md flex items-center justify-center ${isRunning ? "bg-blue-100 text-blue-600 animate-pulse" : "bg-slate-100 text-slate-600"}`}
          >
            <Brain className="w-3.5 h-3.5" />
          </div>
          <span>Luồng suy nghĩ của AI</span>
          <span className="text-[11px] font-normal text-slate-400">
            ({thoughtSteps.length} bước)
          </span>

          {isRunning ? (
            <span className="inline-flex items-center gap-1 text-[10.5px] font-medium text-blue-600 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">
              <Loader2 className="w-2.5 h-2.5 animate-spin" />
              <span>Đang suy nghĩ...</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-[10.5px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
              <CheckCircle2 className="w-2.5 h-2.5" />
              <span>Đã hoàn thành</span>
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-slate-400 group-hover:text-slate-600 text-[11px] font-medium">
          <span>{isOpen ? "Thu gọn" : "Xem chi tiết"}</span>
          {isOpen ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </div>
      </button>

      {/* Danh sách các bước suy nghĩ */}
      {isOpen && (
        <div className="px-4 py-3 border-t border-slate-200/60 bg-white/40 space-y-3">
          {thoughtSteps.map((item, idx) => {
            const isLast = idx === thoughtSteps.length - 1;
            const isStepRunning = item.status === "running";

            return (
              <div
                key={idx}
                className="relative flex items-start gap-3 text-xs"
              >
                {/* Đường nối timeline thẳng đứng */}
                {!isLast && (
                  <div className="absolute left-[9px] top-4 bottom-[-14px] w-[1.5px] bg-slate-200" />
                )}

                {/* Biểu tượng trạng thái bên trái */}
                <div className="relative z-10 w-5 h-5 rounded-full flex items-center justify-center shrink-0 bg-white border border-slate-200 shadow-2xs">
                  {isStepRunning ? (
                    <Loader2 className="w-3 h-3 text-blue-600 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  )}
                </div>

                {/* Nội dung chi tiết bước */}
                <div className="flex-1 space-y-0.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                      {getStepIcon(item.step)}
                      <span>{item.title}</span>
                    </span>
                    {getStepTag(item.step)}
                  </div>
                  {item.detail && (
                    <p className="text-[11.5px] text-slate-500 font-normal leading-relaxed">
                      {item.detail}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

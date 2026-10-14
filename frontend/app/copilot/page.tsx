"use client";

import React, { useState, useEffect, useRef, Suspense } from "react";
import Link from "next/link";
import {
  Sparkles,
  Send,
  Paperclip,
  UploadCloud,
  FileSearch,
  PlusCircle,
  Check,
  TrendingUp,
  FileText,
  Database,
  Lightbulb,
  ChevronRight,
  Loader2,
  CheckCheck,
  CheckSquare,
  Trash2,
  MessageSquare,
  AlertCircle,
  Plus,
  RefreshCw,
  ExternalLink,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Download,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import {
  sendChatMessage,
  sendChatMessageStream,
  fetchConversations,
  fetchConversationDetail,
  deleteConversationApi,
  deleteDocumentApi,
  fetchDocumentsApi,
  fetchDocumentBlobApi,
  fetchDocumentDownloadUrlApi,
  uploadOrderDocumentApi,
  uploadRagDocumentApi,
  ChatMessage,
  ConversationItem,
  RagDocumentItem,
  Citation,
  ProposedAction,
  ThoughtStep,
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { MarkdownRenderer } from "@/components/markdown-renderer";
import { AiThoughtProcess } from "@/components/ai-thought-process";
import { OrderIngestModal } from "@/components/order-ingest-modal";
import { RagUploadModal } from "@/components/rag-upload-modal";
import { useToast } from "@/components/toast-provider";

function CopilotDashboardWorkspace() {
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q");
  const { user } = useAuth();
  const toast = useToast();

  const [inputQuery, setInputQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [documents, setDocuments] = useState<RagDocumentItem[]>([]);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [notification, setNotification] = useState<{
    type: "success" | "error";
    msg: string;
  } | null>(null);
  const [initialProcessed, setInitialProcessed] = useState(false);

  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false);
  const [isRagUploadModalOpen, setIsRagUploadModalOpen] = useState(false);

  const handleDownloadDocument = async (docId?: string, filename?: string) => {
    let targetId = docId;
    if (!targetId && filename) {
      const match = documents.find((d) => d.filename === filename);
      if (match) targetId = match.id;
    }
    if (!targetId) {
      toast.warning(
        "Không tìm thấy tệp",
        `Không thể xác định vị trí tệp ${filename || ""}`,
      );
      return;
    }
    const targetFilename = filename || "document";
    try {
      const { url } = await fetchDocumentBlobApi(targetId, false);
      const a = document.createElement("a");
      a.href = url;
      a.download = targetFilename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success(
        "Tải xuống thành công",
        `Đang lưu tệp "${targetFilename}" về máy.`,
      );
    } catch (err: any) {
      try {
        const res = await fetchDocumentDownloadUrlApi(targetId);
        if (res.download_url) {
          window.open(res.download_url, "_blank");
        }
      } catch (fallbackErr: any) {
        toast.error("Không thể tải file", err.message || "Lỗi tải tệp");
      }
    }
  };

  // ==========================================
  // Resize Panes State & Drag Handlers
  // ==========================================
  const [leftWidth, setLeftWidth] = useState<number>(240);
  const [rightWidth, setRightWidth] = useState<number>(320);
  const [isResizingLeft, setIsResizingLeft] = useState<boolean>(false);
  const [isResizingRight, setIsResizingRight] = useState<boolean>(false);

  // Pane Visibility (Ẩn / Hiện cột trái & phải)
  const [isLeftVisible, setIsLeftVisible] = useState<boolean>(true);
  const [isRightVisible, setIsRightVisible] = useState<boolean>(true);

  useEffect(() => {
    try {
      const savedLeft = localStorage.getItem("erp_copilot_left_width");
      const savedRight = localStorage.getItem("erp_copilot_right_width");
      const savedLeftVis = localStorage.getItem("erp_copilot_left_visible");
      const savedRightVis = localStorage.getItem("erp_copilot_right_visible");

      if (savedLeft) {
        const val = parseInt(savedLeft, 10);
        if (!isNaN(val)) setLeftWidth(Math.max(160, Math.min(420, val)));
      }
      if (savedRight) {
        const val = parseInt(savedRight, 10);
        if (!isNaN(val)) setRightWidth(Math.max(220, Math.min(600, val)));
      }
      if (savedLeftVis !== null) setIsLeftVisible(savedLeftVis === "true");
      if (savedRightVis !== null) setIsRightVisible(savedRightVis === "true");
    } catch {}
  }, []);

  const toggleLeftPane = () => {
    setIsLeftVisible((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("erp_copilot_left_visible", String(next));
      } catch {}
      return next;
    });
  };

  const toggleRightPane = () => {
    setIsRightVisible((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("erp_copilot_right_visible", String(next));
      } catch {}
      return next;
    });
  };

  const startResizingLeft = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingLeft(true);
    const startX = e.clientX;
    const startW = leftWidth;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX;
      const clamped = Math.max(160, Math.min(420, startW + delta));
      setLeftWidth(clamped);
    };

    const handleMouseUp = () => {
      setIsResizingLeft(false);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      setLeftWidth((current) => {
        try {
          localStorage.setItem("erp_copilot_left_width", current.toString());
        } catch {}
        return current;
      });
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const startResizingRight = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingRight(true);
    const startX = e.clientX;
    const startW = rightWidth;

    const handleMouseMove = (moveEvent: MouseEvent) => {
      // Kéo sang trái (clientX nhỏ hơn startX) -> cột phải to hơn
      // Kéo sang phải (clientX lớn hơn startX) -> cột chat to hơn, cột phải hẹp lại
      const delta = startX - moveEvent.clientX;
      const clamped = Math.max(220, Math.min(600, startW + delta));
      setRightWidth(clamped);
    };

    const handleMouseUp = () => {
      setIsResizingRight(false);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
      setRightWidth((current) => {
        try {
          localStorage.setItem("erp_copilot_right_width", current.toString());
        } catch {}
        return current;
      });
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
  };

  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Tự động co giãn chiều cao của ô nhập prompt theo nội dung
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      if (inputQuery) {
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
      }
    }
  }, [inputQuery]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter") {
      if (!e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      } else {
        requestAnimationFrame(() => {
          if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
          }
        });
      }
    }
  };

  // Load conversations & documents list
  const loadSidebarData = async () => {
    try {
      const [convRes, docRes] = await Promise.allSettled([
        fetchConversations(),
        fetchDocumentsApi({ limit: 10 }),
      ]);
      if (convRes.status === "fulfilled") {
        setConversations(convRes.value);
      }
      if (docRes.status === "fulfilled") {
        setDocuments(docRes.value.items || []);
      }
    } catch {
      // offline fallback
    }
  };

  useEffect(() => {
    loadSidebarData();
  }, []);

  // Process initial query if passed via URL (?q=...)
  useEffect(() => {
    if (initialQuery && !initialProcessed) {
      setInitialProcessed(true);
      handleSendMessage(initialQuery);
    }
  }, [initialQuery]);

  const handleSelectConversation = async (convId: string) => {
    if (convId === activeConversationId) return;
    setIsLoading(true);
    setActiveConversationId(convId);
    try {
      const detail = await fetchConversationDetail(convId);
      const mapped: ChatMessage[] = detail.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        created_at: new Date(m.created_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      }));
      setMessages(mapped);
    } catch (err: any) {
      setNotification({
        type: "error",
        msg: "Lỗi tải cuộc hội thoại: " + err.message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setInputQuery("");
  };

  const handleDeleteConversation = async (
    e: React.MouseEvent,
    convId: string,
  ) => {
    e.stopPropagation();
    const confirmed = await toast.confirm({
      title: "Xác nhận xóa cuộc hội thoại",
      message:
        "Bạn có chắc chắn muốn xóa cuộc hội thoại này không? Toàn bộ lịch sử tin nhắn sẽ bị xóa vĩnh viễn.",
      confirmText: "Xóa hội thoại",
      isDanger: true,
    });
    if (!confirmed) return;

    try {
      await deleteConversationApi(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        handleNewConversation();
      }
      toast.success(
        "Đã xóa cuộc hội thoại",
        "Lịch sử tin nhắn đã được làm mới.",
      );
    } catch (err: any) {
      toast.error("Lỗi xóa cuộc hội thoại", err.message || "Không thể xóa");
    }
  };

  const handleDeleteDocument = async (
    e: React.MouseEvent,
    docId: string,
    filename: string,
  ) => {
    e.stopPropagation();
    const confirmed = await toast.confirm({
      title: "Xác nhận xóa tài liệu",
      message: `Bạn có chắc chắn muốn xóa tài liệu "${filename}" khỏi hệ thống không?\n\nTệp tin và toàn bộ nội dung đã xử lý sẽ bị xóa hoàn toàn khỏi cơ sở dữ liệu.`,
      confirmText: "Xóa tài liệu",
      isDanger: true,
    });
    if (!confirmed) return;

    try {
      await deleteDocumentApi(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      toast.success(
        "Đã xóa tài liệu",
        `Đã xóa tài liệu "${filename}" thành công.`,
      );
    } catch (err: any) {
      toast.error("Lỗi khi xóa tài liệu", err.message || "Không thể xóa");
    }
  };

  const [streamingStatus, setStreamingStatus] = useState<string | null>(null);

  const handleSendMessage = async (queryText?: string) => {
    const text = (queryText || inputQuery).trim();
    if (!text || isLoading) return;

    setInputQuery("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    const userMsg: ChatMessage = {
      id: "u-" + Date.now(),
      role: "user",
      content: text,
      created_at: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    const tempAssistantId = "a-" + Date.now();
    const tempAssistantMsg: ChatMessage = {
      id: tempAssistantId,
      role: "assistant",
      content: "",
      created_at: "Đang tạo...",
    };

    setMessages((prev) => [...prev, userMsg, tempAssistantMsg]);
    setIsLoading(true);
    setStreamingStatus("AI Copilot đang phân tích câu hỏi...");

    try {
      await sendChatMessageStream(text, activeConversationId, {
        onStart: (convId) => {
          if (!activeConversationId && convId) {
            setActiveConversationId(convId);
            loadSidebarData();
          }
        },
        onIntent: (intent) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === tempAssistantId ? { ...m, intent } : m)),
          );
        },
        onThought: (thoughtStep) => {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== tempAssistantId) return m;
              const currentSteps = m.thought_steps || [];
              const idx = currentSteps.findIndex((s) => s.step === thoughtStep.step);
              const nextSteps = [...currentSteps];
              if (idx >= 0) {
                nextSteps[idx] = thoughtStep;
              } else {
                nextSteps.push(thoughtStep);
              }
              return {
                ...m,
                thought_steps: nextSteps,
              };
            }),
          );
        },
        onStatus: (statusMessage) => {
          setStreamingStatus(statusMessage);
        },
        onToken: (token) => {
          setStreamingStatus(null);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? { ...m, content: m.content + token }
                : m,
            ),
          );
        },
        onDone: (data) => {
          setStreamingStatus(null);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? {
                    ...m,
                    content: data.answer || m.content,
                    citations: data.citations,
                    proposed_action: data.proposed_action,
                    requires_confirmation: Boolean(data.proposed_action),
                    thought_steps:
                      data.thought_steps && data.thought_steps.length > 0
                        ? data.thought_steps
                        : m.thought_steps?.map((s) => ({
                            ...s,
                            status: "completed" as const,
                          })),
                    created_at: new Date().toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                  }
                : m,
            ),
          );
        },
        onError: (errMsg) => {
          setStreamingStatus(null);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? {
                    ...m,
                    content: m.content
                      ? m.content + "\n\n⚠️ " + errMsg
                      : "⚠️ Đã xảy ra lỗi khi kết nối AI Copilot: " + errMsg,
                    created_at: new Date().toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                  }
                : m,
            ),
          );
        },
      });
    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === tempAssistantId && !m.content
            ? {
                ...m,
                content: "⚠️ Đã xảy ra lỗi kết nối: " + err.message,
                created_at: new Date().toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                }),
              }
            : m,
        ),
      );
    } finally {
      setIsLoading(false);
      setStreamingStatus(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const file = files[0];
    setUploadLoading(true);
    setNotification(null);

    try {
      const fileNameLower = file.name.toLowerCase();
      if (
        fileNameLower.endsWith(".eml") ||
        fileNameLower.includes("don_hang") ||
        fileNameLower.includes("po")
      ) {
        // Phân tích đơn hàng qua Document AI
        const res = await uploadOrderDocumentApi(file);
        setNotification({
          type: "success",
          msg: `Đã phân tích đơn hàng từ tệp ${file.name}! Đã tạo bản nháp và chuyển vào Hộp thư phê duyệt.`,
        });
        // Tự động gửi một tin nhắn thông báo vào luồng chat
        handleSendMessage(
          `Tôi vừa tải lên tệp đơn hàng ${file.name}, hệ thống đã xử lý như thế nào?`,
        );
      } else {
        // Upload tài liệu vào kho dữ liệu
        const res = await uploadRagDocumentApi(file);
        setNotification({
          type: "success",
          msg: `Đã thêm tài liệu ${file.name} vào kho dữ liệu thành công (${res.chunk_count || 1} đoạn nội dung sẵn sàng tra cứu).`,
        });
        loadSidebarData();
      }
    } catch (err: any) {
      setNotification({ type: "error", msg: "Lỗi xử lý tệp: " + err.message });
    } finally {
      setUploadLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div
      className={`flex-1 h-full flex overflow-hidden bg-[#F8FAFC] relative ${
        isResizingLeft || isResizingRight ? "select-none" : ""
      }`}
    >
      {/* Hidden file input for uploads */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        className="hidden"
        accept=".pdf,.docx,.doc,.txt,.eml"
      />

      {/* ========================================================
          CỘT TRÁI (ẨN / HIỆN): Lịch sử hội thoại
         ======================================================== */}
      {isLeftVisible && (
        <>
          <aside
            style={{ width: `${leftWidth}px` }}
            className="h-full bg-white flex flex-col justify-between shrink-0 select-none overflow-hidden transition-[width] duration-75"
          >
            <div className="p-4 space-y-3 flex-1 overflow-y-auto">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleNewConversation}
                  className="flex-1 bg-[#0066FF] hover:bg-blue-700 text-white text-xs font-semibold px-3.5 py-2.5 rounded-xl transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer active:scale-95"
                >
                  <Plus className="w-4 h-4" />
                  <span>Cuộc trò chuyện mới</span>
                </button>
                <button
                  type="button"
                  onClick={toggleLeftPane}
                  title="Ẩn khung lịch sử hội thoại (mở rộng khung chat)"
                  className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer shrink-0"
                >
                  <PanelLeftClose className="w-4 h-4" />
                </button>
              </div>

              <div className="pt-2">
                <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-1 mb-2">
                  Lịch sử hội thoại
                </div>

                {conversations.length === 0 ? (
                  <div className="text-center py-6 text-xs text-slate-400">
                    Chưa có cuộc trò chuyện nào
                  </div>
                ) : (
                  <div className="space-y-1">
                    {conversations.map((conv) => {
                      const isActive = conv.id === activeConversationId;
                      return (
                        <div
                          key={conv.id}
                          onClick={() => handleSelectConversation(conv.id)}
                          className={`group flex items-center justify-between p-2.5 rounded-xl text-xs cursor-pointer transition-colors ${
                            isActive
                              ? "bg-blue-50 text-blue-700 font-semibold"
                              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <MessageSquare
                              className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-blue-600" : "text-slate-400"}`}
                            />
                            <span className="truncate">
                              {conv.title || "Cuộc hội thoại"}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={(e) =>
                              handleDeleteConversation(e, conv.id)
                            }
                            className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 rounded transition-opacity"
                            title="Xóa cuộc trò chuyện"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            <div className="p-3 border-t border-slate-100 text-[11px] text-slate-400 text-center">
              LangGraph • Google Gemini
            </div>
          </aside>

          {/* ========================================================
              RESIZE HANDLE: Trái (Lịch sử hội thoại <-> Main Chat)
             ======================================================== */}
          <div
            onMouseDown={startResizingLeft}
            onDoubleClick={() => setLeftWidth(240)}
            title="Kéo sang trái/phải để thay đổi độ rộng danh sách hội thoại (Nhấp đúp để đặt lại 240px)"
            className={`w-2 -mx-1 hover:w-2.5 bg-transparent hover:bg-blue-500/20 active:bg-blue-600/30 cursor-col-resize transition-all shrink-0 relative group select-none z-20 flex items-center justify-center ${
              isResizingLeft ? "bg-blue-600/30 w-2.5" : ""
            }`}
          >
            <div
              className={`w-[1.5px] h-full transition-colors ${
                isResizingLeft
                  ? "bg-blue-600"
                  : "bg-slate-200 group-hover:bg-blue-500"
              }`}
            />
            <div
              className={`absolute w-1 h-7 rounded-full transition-colors shadow-2xs flex items-center justify-center ${
                isResizingLeft
                  ? "bg-blue-600"
                  : "bg-slate-300 group-hover:bg-blue-500"
              }`}
            >
              <div className="w-0.5 h-3 bg-white/80 rounded-full" />
            </div>
          </div>
        </>
      )}

      {/* ========================================================
          CỘT GIỮA: Interactive Copilot Workspace (Main Center)
         ======================================================== */}
      <main className="flex-1 min-w-[340px] h-full flex flex-col overflow-hidden bg-white">
        {/* Workspace Subheader */}
        <div className="px-6 py-3.5 border-b border-slate-100 flex items-center justify-between shrink-0 bg-white">
          <div className="flex items-center gap-3">
            {!isLeftVisible && (
              <button
                type="button"
                onClick={toggleLeftPane}
                title="Hiện khung lịch sử hội thoại"
                className="p-1.5 -ml-1 text-slate-600 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors cursor-pointer shrink-0 flex items-center gap-1.5 text-xs font-semibold border border-slate-200/90 shadow-2xs"
              >
                <PanelLeftOpen className="w-4 h-4 text-blue-600" />
                <span className="hidden sm:inline">Lịch sử</span>
              </button>
            )}

            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-xs shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900 leading-tight">
                ERP AI Copilot Orchestrator
              </h1>
              <p className="text-[11px] text-slate-400">
                Truy vấn tồn kho • Báo cáo doanh thu • Đề xuất tạo đơn hàng
                (HITL) • RAG Documents
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/approvals"
              className="flex items-center gap-1.5 text-xs text-blue-600 bg-blue-50 border border-blue-200 hover:bg-blue-100 px-3 py-1.5 rounded-xl font-medium transition-colors"
            >
              <CheckSquare className="w-3.5 h-3.5" />
              <span>Hộp thư phê duyệt</span>
            </Link>

            {!isRightVisible && (
              <button
                type="button"
                onClick={toggleRightPane}
                title="Hiện khung tài liệu RAG & Ngữ cảnh"
                className="flex items-center gap-1.5 text-xs text-blue-600 bg-blue-50 border border-blue-200 hover:bg-blue-100 px-3 py-1.5 rounded-xl font-medium transition-colors cursor-pointer shadow-2xs"
              >
                <PanelRightOpen className="w-3.5 h-3.5 text-blue-600" />
                <span className="hidden sm:inline">Tài liệu</span>
              </button>
            )}
          </div>
        </div>

        {/* Notification Alert Box */}
        {notification && (
          <div
            className={`mx-6 mt-4 p-3 rounded-xl text-xs flex items-center justify-between border ${
              notification.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}
          >
            <div className="flex items-center gap-2">
              {notification.type === "success" ? (
                <CheckCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              )}
              <span>{notification.msg}</span>
            </div>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="text-slate-400 hover:text-slate-600 ml-2"
            >
              ✕
            </button>
          </div>
        )}

        {/* Scrollable Conversation Stream */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4 max-w-lg mx-auto">
              <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-inner">
                <Sparkles className="w-7 h-7" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-slate-800">
                  Chào bạn, tôi có thể hỗ trợ gì cho doanh nghiệp hôm nay?
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Tôi có thể tra cứu số lượng tồn kho theo thời gian thực, tổng
                  hợp báo cáo doanh thu, trích xuất email đặt hàng và hỗ trợ trả
                  lời các chính sách công ty qua kho tài liệu RAG.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full pt-2">
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage(
                      "Doanh thu năm 2026 của công ty là bao nhiêu?",
                    )
                  }
                  className="p-3 text-left bg-slate-50 hover:bg-blue-50/70 border border-slate-200/80 hover:border-blue-200 rounded-xl text-xs text-slate-700 transition-all font-medium"
                >
                  📊 Doanh thu năm 2026 của công ty
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage("Kiểm tra tồn kho sản phẩm SKU-001")
                  }
                  className="p-3 text-left bg-slate-50 hover:bg-blue-50/70 border border-slate-200/80 hover:border-blue-200 rounded-xl text-xs text-slate-700 transition-all font-medium"
                >
                  📦 Kiểm tra tồn kho SKU-001
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage(
                      "Tạo đơn hàng nháp cho Công ty TNHH ABC gồm 2 SKU-001",
                    )
                  }
                  className="p-3 text-left bg-slate-50 hover:bg-blue-50/70 border border-slate-200/80 hover:border-blue-200 rounded-xl text-xs text-slate-700 transition-all font-medium"
                >
                  📝 Tạo đơn hàng nháp cho CUS-0001
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage(
                      "Chính sách thanh toán và chiết khấu cho khách hàng",
                    )
                  }
                  className="p-3 text-left bg-slate-50 hover:bg-blue-50/70 border border-slate-200/80 hover:border-blue-200 rounded-xl text-xs text-slate-700 transition-all font-medium"
                >
                  📄 Chính sách bán hàng & chiết khấu
                </button>
              </div>
            </div>
          )}

          {/* Dynamic Follow-up Messages */}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start gap-3 max-w-4xl ${
                msg.role === "user"
                  ? "ml-auto justify-end"
                  : "mr-auto justify-start"
              }`}
            >
              {msg.role !== "user" && (
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shrink-0 mt-0.5 shadow-2xs">
                  <Sparkles className="w-4 h-4" />
                </div>
              )}

              <div
                className={`space-y-2.5 ${msg.role === "user" ? "text-right max-w-xl" : "flex-1"}`}
              >
                {msg.role === "user" ? (
                  <div className="p-3.5 rounded-2xl text-[13px] leading-relaxed bg-[#EBF3FF] text-[#1D39C4] rounded-br-none font-medium shadow-2xs inline-block text-left whitespace-pre-wrap">
                    {msg.content}
                  </div>
                ) : (
                  <div className="p-4 rounded-2xl text-[13px] leading-relaxed bg-white text-slate-800 border border-slate-200/90 rounded-tl-none shadow-xs">
                    {msg.thought_steps && msg.thought_steps.length > 0 && (
                      <AiThoughtProcess
                        thoughtSteps={msg.thought_steps}
                        isStreaming={isLoading && messages[messages.length - 1]?.id === msg.id}
                      />
                    )}

                    {msg.content ? (
                      <MarkdownRenderer
                        content={msg.content}
                        onViewDocument={(filename) =>
                          handleDownloadDocument(undefined, filename)
                        }
                      />
                    ) : (
                      <div className="flex items-center gap-2.5 text-slate-500 text-xs py-1">
                        <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                        <span className="font-medium animate-pulse">
                          {streamingStatus || "AI Copilot đang xử lý..."}
                        </span>
                      </div>
                    )}
                  </div>
                )}

                {/* Proposed Action HITL Card */}
                {msg.proposed_action && (
                  <div className="bg-[#F8FAFC] border border-blue-200 rounded-2xl p-4 space-y-3 text-left shadow-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                        <h4 className="text-xs font-bold text-slate-900 uppercase tracking-tight">
                          Đề xuất lập đơn hàng nháp (Human-In-The-Loop)
                        </h4>
                      </div>
                      <span className="text-[11px] font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-100">
                        Chờ xác nhận
                      </span>
                    </div>

                    <div className="text-xs space-y-1 text-slate-700">
                      <div>
                        Khách hàng:{" "}
                        <span className="font-bold text-slate-900">
                          {msg.proposed_action.customer_name ||
                            msg.proposed_action.customer_code}
                        </span>
                      </div>
                      {msg.proposed_action.total_amount && (
                        <div>
                          Tổng tiền tạm tính:{" "}
                          <span className="font-bold text-blue-700">
                            {formatVND(msg.proposed_action.total_amount)}
                          </span>
                        </div>
                      )}
                      {msg.proposed_action.items &&
                        msg.proposed_action.items.length > 0 && (
                          <div className="pt-1">
                            <span className="text-[11px] text-slate-500 font-semibold">
                              Danh sách sản phẩm:
                            </span>
                            <ul className="list-disc pl-5 text-[11.5px] text-slate-600 pt-0.5">
                              {msg.proposed_action.items.map((it, idx) => (
                                <li key={idx}>
                                  {it.product_name || it.product_sku || it.sku}:{" "}
                                  <span className="font-bold">
                                    {it.quantity}
                                  </span>{" "}
                                  {it.unit_price
                                    ? `(${formatVND(it.unit_price)}/sp)`
                                    : ""}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                    </div>

                    <div className="pt-2 flex items-center gap-2">
                      <Link
                        href="/approvals"
                        className="bg-[#0066FF] hover:bg-blue-700 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-xs flex items-center gap-1.5"
                      >
                        <CheckSquare className="w-3.5 h-3.5" />
                        <span>Mở Hộp thư phê duyệt để duyệt đơn</span>
                      </Link>
                    </div>
                  </div>
                )}

                {/* Citations Box */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="bg-[#FFFBEB] border border-amber-200/90 rounded-xl p-3 text-xs space-y-2 text-left shadow-2xs">
                    <span className="font-semibold text-amber-900 flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-amber-700" />
                      Nguồn trích dẫn tài liệu:
                    </span>
                    <div className="space-y-1.5">
                      {msg.citations.map((c, i) => (
                        <div
                          key={i}
                          onClick={() =>
                            handleDownloadDocument(undefined, c.filename)
                          }
                          className="text-slate-700 text-[11.5px] pl-3 border-l-2 border-amber-400 py-1 hover:bg-amber-100/60 rounded-r-lg transition-colors cursor-pointer group flex items-start justify-between gap-2"
                          title={`Bấm để tải tệp tin gốc: ${c.filename}`}
                        >
                          <div>
                            📄{" "}
                            <span className="font-semibold text-slate-900 group-hover:text-blue-700 transition-colors">
                              {c.filename}
                            </span>{" "}
                            {c.page_number ? (
                              <span className="text-amber-800 font-medium">
                                (Trang {c.page_number})
                              </span>
                            ) : (
                              ""
                            )}{" "}
                            {c.quote ? (
                              <span className="italic text-slate-600">
                                - "{c.quote}"
                              </span>
                            ) : (
                              ""
                            )}
                          </div>
                          <span className="text-[10.5px] text-blue-600 font-semibold group-hover:underline shrink-0 flex items-center gap-0.5">
                            Tải tài liệu ↓
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="text-[11px] text-slate-400 pr-1">
                  {msg.created_at || "Vừa xong"}
                </div>
              </div>

              {msg.role === "user" && (
                <img
                  src="/user-avatar.png"
                  alt="User"
                  className="w-7 h-7 rounded-full object-cover shrink-0 mt-1"
                />
              )}
            </div>
          ))}

          {uploadLoading && (
            <div className="flex items-center gap-3 text-xs text-slate-500 py-2">
              <div className="w-8 h-8 rounded-full bg-amber-500 flex items-center justify-center text-white shrink-0">
                <UploadCloud className="w-4 h-4" />
              </div>
              <div className="flex items-center gap-2 bg-white border border-slate-200/90 px-4 py-2.5 rounded-xl shadow-2xs">
                <Loader2 className="w-4 h-4 animate-spin text-amber-600" />
                <span>Đang tải lên và trích xuất nội dung tài liệu...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ========================================================
            Bottom Smart Input Box with Action Shortcuts (CỐ ĐỊNH Ở ĐÁY)
           ======================================================== */}
        <div className="p-4 border-t border-slate-100 bg-white shrink-0">
          <div className="border border-blue-200/90 rounded-2xl p-2.5 shadow-sm focus-within:ring-4 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all bg-white">
            {/* Input Row */}
            <div className="flex items-start gap-2.5 px-2 pt-0.5">
              <button
                type="button"
                onClick={() => setIsIngestModalOpen(true)}
                title="Bóc tách đơn hàng tự động (.eml, .pdf, văn bản)"
                className="text-blue-600 hover:text-blue-700 p-1 mt-0.5 cursor-pointer shrink-0"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputQuery}
                onChange={(e) => setInputQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Nhập câu hỏi hoặc dán nội dung đơn hàng... (Shift + Enter để xuống dòng, Enter để gửi)"
                className="w-full bg-transparent text-[13px] text-slate-800 placeholder-slate-400 focus:outline-none resize-none leading-relaxed min-h-[26px] max-h-44 py-1 overflow-y-auto"
              />
            </div>

            {/* Bottom Row Shortcuts & Submit */}
            <div className="flex items-center justify-between pt-2.5 border-t border-slate-100/90 mt-2 px-1">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsIngestModalOpen(true)}
                  className="flex items-center gap-1.5 text-[11.5px] text-blue-700 bg-blue-50/80 hover:bg-blue-100 px-2.5 py-1 rounded-lg transition-colors font-semibold border border-blue-200 cursor-pointer"
                  title="Document AI: Tự động trích xuất đơn hàng từ email hoặc file PDF/DOCX"
                >
                  <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                  <span>Bóc tách đơn AI</span>
                </button>
                <button
                  type="button"
                  onClick={() => setIsRagUploadModalOpen(true)}
                  className="flex items-center gap-1.5 text-[11.5px] text-slate-600 hover:text-violet-600 hover:bg-violet-50/60 px-2 py-1 rounded-lg transition-colors font-medium border border-transparent hover:border-violet-100 cursor-pointer"
                  title="Tải văn bản hoặc quy chế vào kho RAG"
                >
                  <UploadCloud className="w-3.5 h-3.5 text-slate-500" />
                  <span>Thêm tài liệu nội bộ</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage(
                      "Báo cáo phân tích doanh thu chi tiết các tháng",
                    )
                  }
                  className="flex items-center gap-1.5 text-[11.5px] text-slate-600 hover:text-blue-600 hover:bg-blue-50/60 px-2 py-1 rounded-lg transition-colors font-medium border border-transparent hover:border-blue-100 cursor-pointer"
                >
                  <FileSearch className="w-3.5 h-3.5 text-slate-500" />
                  <span>Phân tích doanh thu</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleSendMessage(
                      "Tạo đơn hàng nháp cho khách hàng CUS-0001",
                    )
                  }
                  className="flex items-center gap-1.5 text-[11.5px] text-slate-600 hover:text-blue-600 hover:bg-blue-50/60 px-2 py-1 rounded-lg transition-colors font-medium border border-transparent hover:border-blue-100 cursor-pointer"
                >
                  <PlusCircle className="w-3.5 h-3.5 text-slate-500" />
                  <span>Tạo đơn nháp</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => handleSendMessage()}
                disabled={isLoading || !inputQuery.trim()}
                className="bg-[#0066FF] hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white text-xs font-semibold px-4 py-2 rounded-xl transition-all shadow-xs flex items-center gap-1.5 active:scale-95 disabled:cursor-not-allowed cursor-pointer"
              >
                {isLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                <span>Gửi (Enter)</span>
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* ========================================================
          CỘT PHẢI (ẨN / HIỆN): Context & Quick Actions Panel
         ======================================================== */}
      {isRightVisible && (
        <>
          {/* RESIZE HANDLE: Phải (Main Chat <-> Tài liệu RAG) */}
          <div
            onMouseDown={startResizingRight}
            onDoubleClick={() => setRightWidth(320)}
            title="Kéo sang trái để mở rộng tài liệu, kéo sang phải để mở rộng khung chat (Nhấp đúp để đặt lại 320px)"
            className={`w-2.5 -mx-1.5 hover:w-3 bg-transparent hover:bg-blue-500/20 active:bg-blue-600/30 cursor-col-resize transition-all shrink-0 relative group select-none z-20 flex items-center justify-center ${
              isResizingRight ? "bg-blue-600/30 w-3" : ""
            }`}
          >
            <div
              className={`w-[1.5px] h-full transition-colors ${
                isResizingRight
                  ? "bg-blue-600"
                  : "bg-slate-200 group-hover:bg-blue-500"
              }`}
            />
            <div
              className={`absolute w-1.5 h-9 rounded-full transition-colors shadow-2xs flex items-center justify-center ${
                isResizingRight
                  ? "bg-blue-600"
                  : "bg-slate-300 group-hover:bg-blue-500"
              }`}
            >
              <div className="w-0.5 h-4 bg-white/90 rounded-full" />
            </div>
          </div>

          {/* CỘT PHẢI: Context & Quick Actions Panel (Real RAG Documents) */}
          <aside
            style={{ width: `${rightWidth}px` }}
            className="bg-[#F8FAFC] border-l border-slate-200/90 flex flex-col overflow-y-auto p-5 space-y-5 shrink-0 select-none transition-[width] duration-75"
          >
            {/* 1. Kho tài liệu tri thức RAG */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h3 className="text-xs font-bold text-slate-900 tracking-tight">
                    Tài liệu tri thức RAG
                  </h3>
                  <span className="w-5 h-5 rounded-full bg-slate-200/80 text-slate-600 text-[11px] font-bold flex items-center justify-center">
                    {documents.length}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setIsRagUploadModalOpen(true)}
                    title="Tải tài liệu mới vào hệ thống"
                    className="p-1 text-slate-400 hover:text-violet-600 hover:bg-violet-50 rounded-lg transition-colors cursor-pointer"
                  >
                    <UploadCloud className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={toggleRightPane}
                    title="Ẩn khung tài liệu (mở rộng khung chat)"
                    className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer"
                  >
                    <PanelRightClose className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                {documents.length === 0 ? (
                  <div className="p-4 bg-white border border-slate-200/90 rounded-xl text-center text-xs text-slate-400">
                    Chưa có tài liệu nào trong hệ thống. Nhấn biểu tượng tải lên
                    để thêm tài liệu PDF/DOCX.
                  </div>
                ) : (
                  documents.map((doc) => (
                    <div
                      key={doc.id}
                      onClick={() =>
                        handleDownloadDocument(doc.id, doc.filename)
                      }
                      className="bg-white border border-slate-200/90 rounded-xl p-3 flex items-center justify-between hover:border-blue-400 hover:shadow-xs transition-all cursor-pointer group"
                      title="Bấm để tải tệp tin gốc về máy"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors flex items-center justify-center shrink-0">
                          <FileText className="w-4 h-4" />
                        </div>
                        <div className="space-y-0.5 truncate">
                          <div className="text-[12px] font-semibold text-slate-800 group-hover:text-blue-600 transition-colors truncate">
                            {doc.filename}
                          </div>
                          <div className="text-[10.5px] text-slate-400">
                            {doc.access_scope === "restricted"
                              ? "Tài liệu giới hạn"
                              : "Tài liệu nội bộ"}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          type="button"
                          onClick={(e) =>
                            handleDeleteDocument(e, doc.id, doc.filename)
                          }
                          className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-all cursor-pointer"
                          title="Xóa tài liệu khỏi hệ thống"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <Download className="w-4 h-4 text-slate-400 group-hover:text-blue-600 shrink-0 transition-colors" />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* 2. Nguồn dữ liệu kết nối ERP */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-900 tracking-tight">
                Nguồn dữ liệu ERP kết nối
              </h3>
              <div className="bg-white border border-slate-200/90 rounded-xl p-3 space-y-2.5">
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                    <Database className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-xs">
                    <p className="font-semibold text-slate-800">
                      PostgreSQL 16
                    </p>
                    <p className="text-[10.5px] text-slate-400">
                      Cơ sở dữ liệu ERP & Tri thức AI
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <div className="text-xs">
                    <p className="font-semibold text-slate-800">
                      Google Gemini 3.5 Flash-Lite
                    </p>
                    <p className="text-[10.5px] text-slate-400">
                      LangGraph State Machine
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* 3. Phím tắt thao tác nhanh */}
            <div className="space-y-2 pt-1">
              <div className="text-xs font-bold text-slate-900 tracking-tight">
                Thao tác nhanh
              </div>
              <Link
                href="/approvals"
                className="w-full bg-white hover:bg-slate-50 border border-slate-200/90 text-slate-700 text-xs font-medium p-3 rounded-xl shadow-2xs flex items-center justify-between group transition-colors"
              >
                <div className="flex items-center gap-2">
                  <CheckSquare className="w-4 h-4 text-blue-600" />
                  <span>Xử lý đơn chờ duyệt</span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
              </Link>
              <Link
                href="/reports"
                className="w-full bg-white hover:bg-slate-50 border border-slate-200/90 text-slate-700 text-xs font-medium p-3 rounded-xl shadow-2xs flex items-center justify-between group transition-colors"
              >
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <span>Xem báo cáo doanh thu</span>
                </div>
                <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 transition-colors" />
              </Link>
            </div>
          </aside>
        </>
      )}

      {/* Modal Bóc tách đơn hàng Document AI */}
      <OrderIngestModal
        isOpen={isIngestModalOpen}
        onClose={() => setIsIngestModalOpen(false)}
        onSuccess={() => {
          loadSidebarData();
        }}
      />

      {/* Modal Nạp tài liệu RAG */}
      <RagUploadModal
        isOpen={isRagUploadModalOpen}
        onClose={() => setIsRagUploadModalOpen(false)}
        onSuccess={() => {
          loadSidebarData();
        }}
      />
    </div>
  );
}

export default function CopilotPage() {
  return (
    <Suspense
      fallback={
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      }
    >
      <CopilotDashboardWorkspace />
    </Suspense>
  );
}

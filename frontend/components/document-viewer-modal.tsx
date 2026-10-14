"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  X,
  FileText,
  Download,
  Calendar,
  Search,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  MessageSquare,
  BookOpen,
  Clock,
  Type,
  FileCode,
  ExternalLink,
  Eye,
} from "lucide-react";
import {
  DocumentDetailItem,
  RagDocumentItem,
  fetchDocumentDetailApi,
  fetchDocumentBlobApi,
} from "@/lib/api";
import { useToast } from "@/components/toast-provider";

interface DocumentViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string | null;
  documentFilename?: string | null;
  availableDocuments?: RagDocumentItem[];
  onAskAboutDoc?: (filename: string) => void;
}

export function DocumentViewerModal({
  isOpen,
  onClose,
  documentId,
  documentFilename,
  availableDocuments = [],
  onAskAboutDoc,
}: DocumentViewerModalProps) {
  const toast = useToast();
  const [loading, setLoading] = useState<boolean>(false);
  const [docDetail, setDocDetail] = useState<DocumentDetailItem | null>(null);
  const [fileBlobUrl, setFileBlobUrl] = useState<string | null>(null);
  const [fileMimeType, setFileMimeType] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [copiedAll, setCopiedAll] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [fontSize, setFontSize] = useState<"sm" | "base" | "lg">("base");
  const [viewMode, setViewMode] = useState<"original" | "text">("original");

  const currentFilename = docDetail?.filename || documentFilename || "Tài liệu";
  const isPdf =
    currentFilename.toLowerCase().endsWith(".pdf") ||
    fileMimeType.includes("pdf") ||
    docDetail?.mime_type === "application/pdf";
  const isDocx =
    currentFilename.toLowerCase().endsWith(".docx") ||
    currentFilename.toLowerCase().endsWith(".doc");

  useEffect(() => {
    if (!isOpen) {
      if (fileBlobUrl) {
        URL.revokeObjectURL(fileBlobUrl);
      }
      setDocDetail(null);
      setFileBlobUrl(null);
      setFileMimeType("");
      setError(null);
      setSearchQuery("");
      return;
    }

    let targetId = documentId;

    // Tìm documentId tương ứng nếu chỉ truyền documentFilename
    if (!targetId && documentFilename) {
      const cleanTarget = documentFilename.trim().toLowerCase();
      const matched = availableDocuments.find(
        (d) =>
          d.filename.toLowerCase() === cleanTarget ||
          d.filename.toLowerCase().includes(cleanTarget) ||
          cleanTarget.includes(d.filename.toLowerCase())
      );
      if (matched) {
        targetId = matched.id;
      }
    }

    if (targetId) {
      loadDocumentData(targetId);
    } else if (documentFilename) {
      setError(`Không tìm thấy thông tin tài liệu: "${documentFilename}".`);
    }
  }, [isOpen, documentId, documentFilename, availableDocuments]);

  const loadDocumentData = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      // 1. Tải metadata và các đoạn văn bản
      const data = await fetchDocumentDetailApi(id);
      setDocDetail(data);

      // 2. Tải luồng tệp tin gốc trực tiếp từ backend lưu trữ
      try {
        const fileRes = await fetchDocumentBlobApi(id, true);
        setFileBlobUrl(fileRes.url);
        setFileMimeType(fileRes.mimeType);

        // Mặc định: Nếu là PDF thì mở tab xem tệp gốc, nếu là DOCX thì mở tab văn bản
        const fileNameLower = (data.filename || "").toLowerCase();
        if (fileNameLower.endsWith(".docx") || fileNameLower.endsWith(".doc")) {
          setViewMode("text");
        } else {
          setViewMode("original");
        }
      } catch (fileErr: any) {
        console.warn("Không thể tải xem trước file gốc:", fileErr);
        setViewMode("text");
      }
    } catch (err: any) {
      setError(err.message || "Không thể tải nội dung tài liệu.");
    } finally {
      setLoading(false);
    }
  };

  // Tải tệp tin gốc về máy tính
  const handleDownload = async () => {
    const targetId = docDetail?.id || documentId;
    if (!targetId) return;

    setDownloading(true);
    try {
      if (fileBlobUrl) {
        const a = document.createElement("a");
        a.href = fileBlobUrl;
        a.download = currentFilename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        toast.success("Tải xuống thành công", `Đang lưu tệp "${currentFilename}" về máy.`);
      } else {
        const { url } = await fetchDocumentBlobApi(targetId, false);
        const a = document.createElement("a");
        a.href = url;
        a.download = currentFilename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        toast.success("Tải xuống thành công", `Đang lưu tệp "${currentFilename}" về máy.`);
      }
    } catch (err: any) {
      toast.error("Lỗi tải tệp", err.message || "Không thể tải tệp tin");
    } finally {
      setDownloading(false);
    }
  };

  // Ghép toàn bộ nội dung tài liệu liền mạch thành văn bản hoàn chỉnh
  const fullDocumentText = useMemo(() => {
    if (!docDetail?.chunks || docDetail.chunks.length === 0) return "";
    const sorted = [...docDetail.chunks].sort((a, b) => a.chunk_index - b.chunk_index);
    return sorted.map((c) => c.content.trim()).join("\n\n");
  }, [docDetail]);

  // Thống kê độ dài văn bản
  const textStats = useMemo(() => {
    if (!fullDocumentText) return { words: 0, readMinutes: 1 };
    const words = fullDocumentText.split(/\s+/).filter(Boolean).length;
    const readMinutes = Math.max(1, Math.ceil(words / 220));
    return { words, readMinutes };
  }, [fullDocumentText]);

  // Sao chép toàn bộ văn bản tài liệu
  const handleCopyAll = () => {
    if (!fullDocumentText) return;
    navigator.clipboard.writeText(fullDocumentText);
    setCopiedAll(true);
    toast.success("Đã sao chép toàn bộ", "Toàn bộ nội dung tài liệu đã được lưu vào khay nhớ tạm.");
    setTimeout(() => setCopiedAll(false), 2500);
  };

  // Tìm kiếm và đánh dấu từ khóa trong văn bản
  const { renderedContent, matchCount } = useMemo(() => {
    if (!fullDocumentText) return { renderedContent: null, matchCount: 0 };
    if (!searchQuery.trim()) {
      return {
        renderedContent: (
          <div className="whitespace-pre-wrap leading-relaxed select-text font-sans">
            {fullDocumentText}
          </div>
        ),
        matchCount: 0,
      };
    }

    const cleanQuery = searchQuery.trim();
    const escaped = cleanQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escaped})`, "gi");
    const parts = fullDocumentText.split(regex);
    let count = 0;

    const elements = parts.map((part, index) => {
      if (part.toLowerCase() === cleanQuery.toLowerCase()) {
        count++;
        return (
          <mark
            key={index}
            className="bg-amber-200/90 text-amber-950 px-1 py-0.5 rounded-sm font-semibold shadow-2xs"
          >
            {part}
          </mark>
        );
      }
      return <span key={index}>{part}</span>;
    });

    return {
      renderedContent: (
        <div className="whitespace-pre-wrap leading-relaxed select-text font-sans">
          {elements}
        </div>
      ),
      matchCount: count,
    };
  }, [fullDocumentText, searchQuery]);

  if (!isOpen) return null;

  const fontSizeClass = {
    sm: "text-[12.5px] leading-relaxed",
    base: "text-[14px] leading-relaxed",
    lg: "text-[15.5px] leading-loose",
  }[fontSize];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 md:p-6 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="bg-white w-full max-w-5xl h-[92vh] max-h-[880px] rounded-3xl shadow-2xl border border-slate-200/90 flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ================= HEADER ================= */}
        <div className="px-6 py-3.5 border-b border-slate-200 bg-slate-50/90 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 border border-blue-200 shadow-2xs">
              <BookOpen className="w-5 h-5" />
            </div>

            <div className="truncate">
              <h2 className="text-sm sm:text-base font-bold text-slate-900 truncate">
                {currentFilename}
              </h2>
              <div className="text-xs text-slate-500 flex flex-wrap items-center gap-2 mt-0.5">
                {docDetail?.created_at && (
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-400" />
                    {new Date(docDetail.created_at).toLocaleDateString("vi-VN")}
                  </span>
                )}
                {textStats.words > 0 && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span>Khoảng {textStats.words.toLocaleString("vi-VN")} từ</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Các nút hành động chính */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Nút tải tệp gốc về máy */}
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="bg-[#0066FF] hover:bg-blue-700 text-white text-xs font-semibold px-3.5 py-1.5 rounded-xl transition-all shadow-xs flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              title="Tải tệp tin gốc về máy tính"
            >
              {downloading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5" />
              )}
              <span>Tải tài liệu</span>
            </button>

            {fullDocumentText && viewMode === "text" && (
              <button
                type="button"
                onClick={handleCopyAll}
                className="bg-white hover:bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold px-3 py-1.5 rounded-xl transition-all shadow-2xs flex items-center gap-1.5 cursor-pointer"
                title="Sao chép toàn bộ nội dung văn bản"
              >
                {copiedAll ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700">Đã chép</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-slate-500" />
                    <span>Sao chép</span>
                  </>
                )}
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="text-slate-400 hover:text-slate-700 p-1.5 rounded-xl hover:bg-slate-200/60 transition-colors cursor-pointer ml-1"
              title="Đóng cửa sổ"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ================= TOOLBAR & MODE SWITCHER ================= */}
        <div className="px-6 py-2 border-b border-slate-200/80 bg-white flex flex-wrap items-center justify-between gap-3 shrink-0">
          {/* Segmented Control: Xem file gốc vs Đọc văn bản */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-semibold text-slate-600">
            <button
              type="button"
              onClick={() => setViewMode("original")}
              className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                viewMode === "original"
                  ? "bg-white text-blue-600 shadow-2xs font-bold"
                  : "hover:text-slate-900"
              }`}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>Xem tệp gốc {isPdf ? "(PDF)" : isDocx ? "(Word)" : ""}</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode("text")}
              className={`px-3 py-1 rounded-lg transition-all flex items-center gap-1.5 cursor-pointer ${
                viewMode === "text"
                  ? "bg-white text-blue-600 shadow-2xs font-bold"
                  : "hover:text-slate-900"
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Văn bản trích xuất</span>
            </button>
          </div>

          {/* Thanh công cụ khi ở chế độ Đọc văn bản */}
          {viewMode === "text" && (
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Tìm từ khóa trong văn bản..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-7 py-1 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer text-xs"
                  >
                    ✕
                  </button>
                )}
              </div>

              {searchQuery.trim() && (
                <span className="text-[11px] font-medium text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-lg">
                  Tìm thấy <strong>{matchCount}</strong> kết quả
                </span>
              )}

              {/* Nút cỡ chữ */}
              <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg text-xs font-semibold text-slate-600">
                <span className="text-[10.5px] text-slate-400 px-1.5 flex items-center gap-1">
                  <Type className="w-3 h-3" /> Cỡ chữ:
                </span>
                {(["sm", "base", "lg"] as const).map((sz) => (
                  <button
                    key={sz}
                    type="button"
                    onClick={() => setFontSize(sz)}
                    className={`px-2 py-0.5 rounded-md transition-all cursor-pointer ${
                      fontSize === sz ? "bg-white text-blue-600 shadow-2xs font-bold" : "hover:text-slate-900"
                    }`}
                  >
                    {sz === "sm" ? "Nhỏ" : sz === "base" ? "Vừa" : "Lớn"}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Công cụ khi ở chế độ xem tệp gốc */}
          {viewMode === "original" && fileBlobUrl && (
            <div className="flex items-center gap-2">
              <a
                href={fileBlobUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1 font-semibold hover:underline"
              >
                <span>Mở cửa sổ mới</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          )}
        </div>

        {/* ================= DOCUMENT VIEWER BODY ================= */}
        <div className="flex-1 overflow-hidden bg-slate-100/70 relative">
          {loading && (
            <div className="h-full flex flex-col items-center justify-center py-20 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              <p className="text-xs text-slate-600 font-medium">Đang tải và chuẩn bị tài liệu...</p>
            </div>
          )}

          {error && (
            <div className="max-w-xl mx-auto my-12 p-5 bg-rose-50 border border-rose-200 rounded-2xl text-rose-800 text-xs flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-sm mb-1">Không thể mở tài liệu</p>
                <p>{error}</p>
              </div>
            </div>
          )}

          {/* CHẾ ĐỘ 1: XEM TỆP GỐC TRỰC TIẾP */}
          {!loading && !error && viewMode === "original" && (
            <div className="w-full h-full">
              {isPdf && fileBlobUrl ? (
                /* Trình đọc PDF tích hợp trực tiếp bằng iframe trình duyệt */
                <iframe
                  src={fileBlobUrl}
                  className="w-full h-full border-0 bg-slate-200"
                  title={`Tệp PDF: ${currentFilename}`}
                />
              ) : isDocx ? (
                /* Thông báo tệp Word và hỗ trợ tải về hoặc chuyển văn bản */
                <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-4">
                  <div className="w-16 h-16 rounded-3xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-xs border border-blue-100">
                    <FileText className="w-8 h-8" />
                  </div>
                  <div className="max-w-md space-y-1">
                    <h3 className="text-base font-bold text-slate-900">
                      Tệp tin Microsoft Word (.docx)
                    </h3>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Trình duyệt không hỗ trợ mở trực tiếp tệp Word định dạng nhị phân. Bạn có thể tải tệp tin về máy tính để mở trên Word, hoặc chuyển sang tab <strong>Văn bản trích xuất</strong> để đọc toàn bộ nội dung ngay tại đây.
                    </p>
                  </div>
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      type="button"
                      onClick={handleDownload}
                      className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Download className="w-4 h-4" />
                      <span>Tải tệp Word về máy</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewMode("text")}
                      className="px-5 py-2.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-semibold shadow-2xs transition-colors flex items-center gap-2 cursor-pointer"
                    >
                      <Eye className="w-4 h-4 text-blue-600" />
                      <span>Đọc văn bản trích xuất</span>
                    </button>
                  </div>
                </div>
              ) : fileBlobUrl ? (
                /* Các tệp văn bản thô hoặc hình ảnh khác */
                <iframe
                  src={fileBlobUrl}
                  className="w-full h-full border-0 bg-white"
                  title={currentFilename}
                />
              ) : (
                <div className="h-full flex flex-col items-center justify-center p-8 text-center space-y-3">
                  <p className="text-xs text-slate-500">Đang chuẩn bị luồng hiển thị tệp tin...</p>
                  <button
                    type="button"
                    onClick={() => setViewMode("text")}
                    className="text-xs text-blue-600 font-semibold underline cursor-pointer"
                  >
                    Chuyển sang xem dạng văn bản
                  </button>
                </div>
              )}
            </div>
          )}

          {/* CHẾ ĐỘ 2: ĐỌC VĂN BẢN NGUYÊN BẢN (TRANG GIẤY) */}
          {!loading && !error && viewMode === "text" && (
            <div className="h-full overflow-y-auto p-4 sm:p-6">
              {!fullDocumentText ? (
                <div className="max-w-md mx-auto my-16 text-center space-y-3 p-8 bg-white rounded-2xl border border-slate-200 shadow-2xs">
                  <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
                    <FileText className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-800">Chưa có nội dung văn bản trích xuất</h3>
                  <p className="text-xs text-slate-500">
                    Tài liệu có thể đang trong quá trình xử lý. Bạn có thể bấm nút "Tải tài liệu" ở góc trên để tải tệp gốc về máy.
                  </p>
                </div>
              ) : (
                <div className="max-w-3xl mx-auto bg-white rounded-2xl border border-slate-200/90 shadow-sm p-6 sm:p-10 my-2 transition-all">
                  <div className="border-b border-slate-100 pb-4 mb-6">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-blue-600">
                      Nội dung văn bản
                    </span>
                    <h1 className="text-lg sm:text-xl font-bold text-slate-900 mt-1">
                      {currentFilename}
                    </h1>
                  </div>

                  <div className={`text-slate-800 ${fontSizeClass}`}>
                    {renderedContent}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* ================= FOOTER ================= */}
        <div className="px-6 py-3 border-t border-slate-200 bg-white flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <BookOpen className="w-4 h-4 text-slate-400" />
            <span>
              {viewMode === "original" ? "Đang xem tệp tin gốc" : "Đang đọc văn bản trích xuất"}
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            {onAskAboutDoc && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onAskAboutDoc(currentFilename);
                }}
                className="bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-semibold px-3.5 py-1.5 rounded-xl transition-all shadow-2xs flex items-center gap-1.5 cursor-pointer"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                <span>Hỏi Trợ lý AI về tài liệu</span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold px-4 py-1.5 rounded-xl transition-all cursor-pointer shadow-2xs"
            >
              Đóng
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

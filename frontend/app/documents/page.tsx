"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import { 
  FileText, 
  Search, 
  RefreshCw, 
  Upload, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Lock, 
  Globe, 
  Sparkles,
  Download,
  Trash2,
  X,
  Loader2,
  FileUp,
  FileCheck2
} from "lucide-react";
import { 
  fetchDocumentsApi, 
  uploadRagDocumentApi, 
  fetchDocumentDownloadUrlApi,
  fetchDocumentBlobApi,
  deleteDocumentApi,
  RagDocumentItem 
} from "@/lib/api";
import { useToast } from "@/components/toast-provider";

export default function DocumentsPage() {
  const toast = useToast();
  const [documents, setDocuments] = useState<RagDocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [scopeFilter, setScopeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modal Upload tài liệu mới
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadScope, setUploadScope] = useState<string>("internal");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchDocumentsApi({
        access_scope: scopeFilter === "all" ? undefined : scopeFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: 100,
      });
      setDocuments(data.items || []);
    } catch (err: any) {
      const msg = "Lỗi khi tải danh sách tài liệu RAG: " + err.message;
      setErrorMsg(msg);
      toast.error("Không thể tải tài liệu", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [scopeFilter, statusFilter]);

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      if (!searchTerm.trim()) return true;
      const term = searchTerm.toLowerCase();
      return (doc.filename || "").toLowerCase().includes(term);
    });
  }, [documents, searchTerm]);

  const stats = useMemo(() => {
    const total = documents.length;
    const indexed = documents.filter((d) => d.status === "indexed").length;
    const internal = documents.filter((d) => d.access_scope === "internal").length;
    const restricted = documents.filter((d) => d.access_scope === "restricted").length;
    return { total, indexed, internal, restricted };
  }, [documents]);

  const handleDeleteDocument = async (docId: string, filename: string) => {
    const confirmed = await toast.confirm({
      title: "Xác nhận xóa tài liệu",
      message: `Bạn có chắc chắn muốn xóa tài liệu "${filename}"?\n\nTệp tin và toàn bộ nội dung đã xử lý sẽ bị xóa hoàn toàn khỏi hệ thống.`,
      confirmText: "Xóa tài liệu",
      isDanger: true,
    });

    if (!confirmed) return;

    try {
      await deleteDocumentApi(docId);
      toast.success("Đã xóa tài liệu", `Đã xóa tài liệu "${filename}" thành công.`);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err: any) {
      toast.error("Lỗi khi xóa tài liệu", err.message || "Không thể xóa");
    }
  };

  const handleDownload = async (docId: string, filename: string) => {
    try {
      const { url } = await fetchDocumentBlobApi(docId, false);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success("Tải xuống thành công", `Đang lưu tệp "${filename}" về máy.`);
    } catch (err: any) {
      try {
        const res = await fetchDocumentDownloadUrlApi(docId);
        if (res.download_url) {
          window.open(res.download_url, "_blank");
        }
      } catch (fallbackErr: any) {
        toast.error("Không thể tải file", err.message);
      }
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      toast.warning("Chưa chọn tệp tin", "Vui lòng chọn tệp tin cần tải lên!");
      return;
    }

    setUploading(true);
    try {
      await uploadRagDocumentApi(uploadFile, uploadScope);
      toast.success("Tải lên thành công", `Tài liệu "${uploadFile.name}" đã được tải lên và đang được hệ thống xử lý nội dung.`);
      setIsUploadModalOpen(false);
      setUploadFile(null);
      loadDocuments();
    } catch (err: any) {
      toast.error("Lỗi khi tải lên tài liệu", err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Header phân hệ */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-violet-50 text-violet-600 flex items-center justify-center shadow-xs border border-violet-100">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Kho Tài liệu & Quy trình Doanh nghiệp
            </h1>
            <p className="text-xs text-slate-500">
              Quản lý văn bản, tài liệu PDF/DOCX giúp Trợ lý AI tra cứu và giải đáp chính xác theo quy định nội bộ
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadDocuments}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-violet-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <button
            type="button"
            onClick={() => setIsUploadModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Tải tài liệu mới</span>
          </button>
        </div>
      </div>

      {/* 2. Thẻ thống kê */}
      <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-4 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center shrink-0">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tổng số tài liệu</div>
            <div className="text-base font-bold text-slate-900">{stats.total} văn bản</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Sẵn sàng tra cứu</div>
            <div className="text-base font-bold text-emerald-600">{stats.indexed} văn bản</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Globe className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Quyền nội bộ (Internal)</div>
            <div className="text-base font-bold text-blue-600">{stats.internal} văn bản</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
            <Lock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Giới hạn (Restricted)</div>
            <div className="text-base font-bold text-amber-600">{stats.restricted} văn bản</div>
          </div>
        </div>
      </div>

      {/* 3. Bộ lọc & Tìm kiếm */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex flex-wrap items-center gap-2">
          {/* Lọc phạm vi quyền */}
          <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200/90 shadow-2xs">
            {[
              { id: "all", label: "Tất cả quyền" },
              { id: "internal", label: "Nội bộ" },
              { id: "restricted", label: "Giới hạn" },
            ].map((sc) => (
              <button
                key={sc.id}
                type="button"
                onClick={() => setScopeFilter(sc.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  scopeFilter === sc.id
                    ? "bg-violet-600 text-white shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {sc.label}
              </button>
            ))}
          </div>

          {/* Lọc trạng thái */}
          <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200/90 shadow-2xs">
            {[
              { id: "all", label: "Tất cả trạng thái" },
              { id: "indexed", label: "Sẵn sàng" },
              { id: "processing", label: "Đang xử lý" },
            ].map((st) => (
              <button
                key={st.id}
                type="button"
                onClick={() => setStatusFilter(st.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  statusFilter === st.id
                    ? "bg-emerald-600 text-white shadow-2xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>
        </div>

        <div className="relative w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Tìm theo tên file tài liệu..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200/90 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 shadow-2xs"
          />
        </div>
      </div>

      {/* 4. Thông báo */}
      {successMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-emerald-50 text-emerald-800 text-xs border border-emerald-200 flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">✕</button>
        </div>
      )}

      {errorMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {/* 5. Bảng danh sách tài liệu */}
      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Tên tài liệu</th>
                  <th className="py-3 px-4 text-center">Quyền truy cập</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4">Ngày cập nhật</th>
                  <th className="py-3 px-4 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-48" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-100 rounded-md w-24" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-20 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredDocuments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <FileText className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Chưa có tài liệu nào phù hợp</p>
                      <p className="text-[11px] text-slate-400 mt-1">Bấm "Tải tài liệu mới" để đưa tài liệu PDF/DOCX vào kho RAG</p>
                    </td>
                  </tr>
                ) : (
                  filteredDocuments.map((doc) => (
                    <tr
                      key={doc.id}
                      className="hover:bg-slate-50/80 transition-colors"
                    >
                      <td className="py-3.5 px-4 font-semibold text-slate-800 flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                          <FileText className="w-3.5 h-3.5" />
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDownload(doc.id, doc.filename)}
                          className="text-left font-semibold text-slate-800 hover:text-blue-600 transition-colors truncate max-w-md cursor-pointer"
                          title="Bấm để tải tệp tin gốc về máy"
                        >
                          {doc.filename}
                        </button>
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {doc.access_scope === "restricted" ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            <Lock className="w-3 h-3 text-amber-600" />
                            Giới hạn
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                            <Globe className="w-3 h-3 text-blue-600" />
                            Nội bộ
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {doc.status === "indexed" ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Sẵn sàng
                          </span>
                        ) : doc.status === "failed" ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                            <AlertCircle className="w-3 h-3 text-rose-600" />
                            Lỗi
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                            <Clock className="w-3 h-3 text-amber-600" />
                            Đang xử lý
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 text-[11.5px]">
                        {doc.created_at ? new Date(doc.created_at).toLocaleDateString("vi-VN") : "—"}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleDownload(doc.id, doc.filename)}
                            className="inline-flex items-center gap-1.5 text-[11.5px] text-blue-600 hover:text-blue-800 bg-blue-50/80 hover:bg-blue-100 px-2.5 py-1 rounded-lg transition-colors font-semibold cursor-pointer"
                            title="Tải tệp tin gốc về máy"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>Tải tài liệu</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                            className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                            title="Xóa tài liệu khỏi hệ thống"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
            <span>Hiển thị {filteredDocuments.length} / {documents.length} tài liệu</span>
            <span>Kho tri thức doanh nghiệp tích hợp Trợ lý AI</span>
          </div>
        </div>
      </div>

      {/* 6. Modal Upload Tài liệu mới */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <Upload className="w-4 h-4 text-blue-600" />
                <h3 className="font-bold text-sm text-slate-900">Tải tài liệu vào Kho RAG</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsUploadModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="p-5 space-y-4">
              {/* Vùng chọn file */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-200 hover:border-blue-400 rounded-2xl p-6 text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-blue-50/30"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="hidden"
                  accept=".pdf,.docx,.doc,.txt"
                />
                <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-2">
                  <FileUp className="w-5 h-5" />
                </div>
                {uploadFile ? (
                  <div className="space-y-1">
                    <p className="text-xs font-bold text-blue-600 truncate">{uploadFile.name}</p>
                    <p className="text-[11px] text-slate-400">
                      {(uploadFile.size / 1024).toFixed(1)} KB • Bấm để chọn lại
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-semibold text-slate-700">Kéo thả hoặc bấm để chọn tệp</p>
                    <p className="text-[11px] text-slate-400">Hỗ trợ PDF, DOCX, TXT (tối đa 10MB)</p>
                  </div>
                )}
              </div>

              {/* Chọn phân quyền */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700">Phân quyền truy cập tài liệu:</label>
                <select
                  value={uploadScope}
                  onChange={(e) => setUploadScope(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20"
                >
                  <option value="internal">Nội bộ công ty (Tất cả nhân viên)</option>
                  <option value="restricted">Giới hạn (Chỉ Quản trị viên & Quản lý)</option>
                </select>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={uploading || !uploadFile}
                  className="px-4 py-2 bg-[#0066FF] hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang xử lý nội dung...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Bắt đầu xử lý</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}

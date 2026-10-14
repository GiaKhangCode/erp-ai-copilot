"use client";

import React, { useState, useRef } from "react";
import { 
  X, 
  Upload, 
  FileText, 
  Lock, 
  Globe, 
  Sparkles, 
  Loader2, 
  CheckCircle2, 
  AlertCircle,
  FileUp,
  Layers
} from "lucide-react";
import { uploadRagDocumentApi, RagDocumentItem } from "@/lib/api";
import { useToast } from "@/components/toast-provider";

interface RagUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (doc: RagDocumentItem) => void;
}

export function RagUploadModal({ isOpen, onClose, onSuccess }: RagUploadModalProps) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [accessScope, setAccessScope] = useState<string>("internal");
  const [uploading, setUploading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successDoc, setSuccessDoc] = useState<RagDocumentItem | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleClose = () => {
    setFile(null);
    setErrorMsg(null);
    setSuccessDoc(null);
    setUploading(false);
    onClose();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setErrorMsg(null);
      setSuccessDoc(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg("Vui lòng chọn tệp tin cần tải lên.");
      return;
    }

    setUploading(true);
    setErrorMsg(null);

    try {
      const res = await uploadRagDocumentApi(file, accessScope);
      setSuccessDoc(res);
      toast.success("Tải lên thành công", `Tài liệu "${res.filename}" đã được tải lên và sẵn sàng tra cứu.`);
      onSuccess?.(res);
    } catch (err: any) {
      const msg = err.message || "Đã xảy ra lỗi khi tải lên tài liệu.";
      setErrorMsg(msg);
      toast.error("Lỗi tải lên tài liệu", msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center shadow-xs">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 leading-tight">
                Tải lên Tài liệu Tham khảo
              </h3>
              <p className="text-[11px] text-slate-500">
                Bổ sung tài liệu nội bộ để Trợ lý AI tra cứu và giải đáp chính xác
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successDoc ? (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl space-y-2.5 text-xs text-emerald-800">
              <div className="flex items-center gap-2 font-bold text-sm">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                <span>Nạp tài liệu thành công!</span>
              </div>
              <p className="text-emerald-700">
                Tài liệu <strong>{successDoc.filename}</strong> đã được phân tích thành <strong>{successDoc.chunk_count || 1} đoạn nội dung</strong> và sẵn sàng để Trợ lý AI tra cứu.
              </p>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setSuccessDoc(null);
                    setFile(null);
                  }}
                  className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors cursor-pointer"
                >
                  Tải thêm tài liệu khác
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* File Dropzone */}
              <div
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-200 hover:border-violet-500 rounded-2xl p-6 text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-violet-50/20 group"
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  className="hidden"
                  accept=".pdf,.docx,.doc,.txt"
                />
                <div className="w-10 h-10 rounded-xl bg-violet-50 text-violet-600 group-hover:scale-105 transition-transform flex items-center justify-center mx-auto mb-2 shadow-2xs">
                  <FileUp className="w-5 h-5" />
                </div>
                {file ? (
                  <div className="space-y-0.5">
                    <p className="text-xs font-bold text-violet-600 truncate">{file.name}</p>
                    <p className="text-[11px] text-slate-400">
                      {(file.size / 1024).toFixed(1)} KB • Bấm để chọn lại
                    </p>
                  </div>
                ) : (
                  <div className="space-y-0.5">
                    <p className="text-xs font-bold text-slate-700">Bấm để chọn tệp tài liệu</p>
                    <p className="text-[11px] text-slate-400">Hỗ trợ PDF, DOCX, TXT (tối đa 10MB)</p>
                  </div>
                )}
              </div>

              {/* Scope Selector */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-700">Phân quyền truy cập tài liệu:</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setAccessScope("internal")}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center gap-2 ${
                      accessScope === "internal"
                        ? "bg-violet-50 border-violet-300 text-violet-900 font-bold"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <Globe className="w-4 h-4 text-violet-600 shrink-0" />
                    <div className="text-xs">Nội bộ chung</div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setAccessScope("restricted")}
                    className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer flex items-center gap-2 ${
                      accessScope === "restricted"
                        ? "bg-amber-50 border-amber-300 text-amber-900 font-bold"
                        : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    <Lock className="w-4 h-4 text-amber-600 shrink-0" />
                    <div className="text-xs">Giới hạn Quản lý</div>
                  </button>
                </div>
              </div>

              {/* Loading indicator */}
              {uploading && (
                <div className="p-3 rounded-xl bg-violet-50 border border-violet-200 flex items-center gap-2.5 text-xs text-violet-800">
                  <Loader2 className="w-4 h-4 animate-spin text-violet-600 shrink-0" />
                  <span>Đang tải lên và xử lý nội dung văn bản...</span>
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-2 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
                >
                  Đóng
                </button>
                <button
                  type="submit"
                  disabled={uploading || !file}
                  className="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl text-xs font-bold shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang xử lý...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-3.5 h-3.5" />
                      <span>Bắt đầu nạp</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

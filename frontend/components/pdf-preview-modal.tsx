"use client";

import React, { useState, useEffect } from "react";
import { X, Download, ExternalLink, FileText, Loader2 } from "lucide-react";
import { fetchOrderQuotationBlobApi } from "@/lib/api";

interface PdfPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  orderId?: string;
  orderNumber?: string;
  pdfUrl?: string;
  filename?: string;
}

export function PdfPreviewModal({
  isOpen,
  onClose,
  orderId,
  orderNumber,
  pdfUrl,
  filename: initialFilename,
}: PdfPreviewModalProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [filename, setFilename] = useState<string>(initialFilename || "Bao_Gia.pdf");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
        setBlobUrl(null);
      }
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    async function loadPdf() {
      try {
        if (orderId) {
          const { url, filename: fetchedName } = await fetchOrderQuotationBlobApi(orderId);
          if (isMounted) {
            setBlobUrl(url);
            if (fetchedName) setFilename(fetchedName);
            setIsLoading(false);
          }
        } else if (pdfUrl) {
          // If direct url provided
          const token = localStorage.getItem("erp_access_token");
          const fullUrl = pdfUrl.startsWith("http") ? pdfUrl : `${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1"}${pdfUrl.replace("/api/v1", "")}`;
          const res = await fetch(fullUrl, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (!res.ok) throw new Error("Không thể tải file PDF");
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          if (isMounted) {
            setBlobUrl(url);
            if (initialFilename) setFilename(initialFilename);
            setIsLoading(false);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Lỗi khi tải file báo giá.");
          setIsLoading(false);
        }
      }
    }

    loadPdf();

    return () => {
      isMounted = false;
    };
  }, [isOpen, orderId, pdfUrl]);

  if (!isOpen) return null;

  const handleDownload = () => {
    if (!blobUrl) return;
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const handleOpenNewTab = () => {
    if (!blobUrl) return;
    window.open(blobUrl, "_blank");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="bg-white w-full max-w-5xl h-[92vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-slate-200">
        {/* Modal Header */}
        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-100 shadow-2xs">
              <FileText className="w-5 h-5 text-rose-600" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-slate-900 leading-tight">
                  {filename}
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                  PDF Báo giá
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                {orderNumber ? `Đơn hàng ${orderNumber}` : "Bản in Báo giá / Proforma Invoice chuẩn doanh nghiệp"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleOpenNewTab}
              disabled={isLoading || !blobUrl}
              title="Mở tab mới để in hoặc xem toàn màn hình"
              className="p-2 text-slate-600 hover:text-blue-600 hover:bg-white rounded-xl transition-colors border border-slate-200/80 shadow-2xs cursor-pointer disabled:opacity-50 text-xs font-medium flex items-center gap-1.5"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Mở tab mới</span>
            </button>

            <button
              type="button"
              onClick={handleDownload}
              disabled={isLoading || !blobUrl}
              title="Tải file PDF về máy"
              className="bg-blue-600 hover:bg-blue-700 text-white px-3.5 py-1.5 rounded-xl transition-all shadow-xs cursor-pointer disabled:opacity-50 text-xs font-semibold flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Tải file</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-xl transition-colors ml-1 cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body / Viewer */}
        <div className="flex-1 bg-slate-100 flex items-center justify-center overflow-hidden relative">
          {isLoading && (
            <div className="flex flex-col items-center gap-3 text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              <span className="text-xs font-medium">Đang chuẩn bị file PDF Báo giá...</span>
            </div>
          )}

          {error && (
            <div className="p-6 text-center max-w-md bg-white rounded-2xl border border-rose-200 shadow-xs">
              <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto mb-3">
                <X className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-bold text-slate-800 mb-1">Không thể tải file báo giá</h4>
              <p className="text-xs text-slate-500 mb-4">{error}</p>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors"
              >
                Đóng
              </button>
            </div>
          )}

          {!isLoading && !error && blobUrl && (
            <iframe
              src={blobUrl}
              className="w-full h-full border-0"
              title="Xem trước PDF Báo giá"
            />
          )}
        </div>
      </div>
    </div>
  );
}

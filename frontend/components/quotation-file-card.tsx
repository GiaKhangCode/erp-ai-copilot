"use client";

import React, { useState } from "react";
import { FileText, Download, Eye, CheckCircle2, ShieldCheck } from "lucide-react";
import { formatVND } from "@/lib/utils";
import { fetchOrderQuotationBlobApi } from "@/lib/api";
import { PdfPreviewModal } from "@/components/pdf-preview-modal";

export interface QuotationFileCardProps {
  orderId: string;
  orderNumber: string;
  customerName?: string;
  totalAmount?: number;
  pdfUrl?: string;
  filename?: string;
}

export function QuotationFileCard({
  orderId,
  orderNumber,
  customerName,
  totalAmount,
  pdfUrl,
  filename = `Bao_Gia_${orderNumber}.pdf`,
}: QuotationFileCardProps) {
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setIsDownloading(true);
      const { url, filename: fetchedName } = await fetchOrderQuotationBlobApi(orderId);
      const a = document.createElement("a");
      a.href = url;
      a.download = fetchedName || filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message || "Không thể tải file PDF.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <>
      <div className="my-3 rounded-2xl border border-rose-200/90 bg-gradient-to-br from-white via-rose-50/20 to-orange-50/30 p-3.5 shadow-sm transition-all hover:shadow-md hover:border-rose-300">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* File Meta Info */}
          <div className="flex items-start gap-3">
            <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rose-500 to-red-600 text-white shadow-sm shadow-rose-200">
              <FileText className="h-6 w-6" />
              <span className="absolute -bottom-1 -right-1 rounded-sm bg-slate-900 px-1 py-0.2 text-[8px] font-extrabold uppercase tracking-wider text-white">
                PDF
              </span>
            </div>

            <div className="min-w-0 space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="truncate text-xs font-bold text-slate-900 tracking-tight">
                  {filename}
                </span>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">
                  <ShieldCheck className="w-2.5 h-2.5 text-emerald-600" />
                  Báo giá chính thức
                </span>
              </div>

              <div className="text-[11.5px] text-slate-500 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                {customerName && (
                  <span>
                    Khách hàng: <b className="text-slate-800">{customerName}</b>
                  </span>
                )}
                {totalAmount !== undefined && (
                  <>
                    <span>•</span>
                    <span className="font-bold text-blue-700">
                      {formatVND(totalAmount)}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 shrink-0 pt-1 sm:pt-0">
            <button
              type="button"
              onClick={() => setIsPreviewOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs transition-colors hover:border-blue-300 hover:bg-blue-50/80 hover:text-blue-700 cursor-pointer"
            >
              <Eye className="h-3.5 w-3.5 text-blue-600" />
              <span>Xem trước</span>
            </button>

            <button
              type="button"
              onClick={handleDownload}
              disabled={isDownloading}
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-blue-700 cursor-pointer disabled:opacity-50"
            >
              <Download className="h-3.5 w-3.5" />
              <span>{isDownloading ? "Đang tải..." : "Tải PDF"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Embedded PDF Viewer Modal */}
      <PdfPreviewModal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        orderId={orderId}
        orderNumber={orderNumber}
        filename={filename}
        pdfUrl={pdfUrl}
      />
    </>
  );
}

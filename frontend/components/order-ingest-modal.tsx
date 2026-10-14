"use client";

import React, { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { 
  X, 
  Upload, 
  FileText, 
  Mail, 
  Sparkles, 
  Loader2, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  Layers, 
  FileUp, 
  Check, 
  AlertCircle,
  Clock,
  ExternalLink
} from "lucide-react";
import { 
  uploadOrderDocumentApi, 
  uploadOrderEmlApi, 
  uploadOrderTextApi, 
  OrderIngestionResult 
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useToast } from "@/components/toast-provider";

interface OrderIngestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (result: OrderIngestionResult) => void;
}

export function OrderIngestModal({ isOpen, onClose, onSuccess }: OrderIngestModalProps) {
  const router = useRouter();
  const toast = useToast();
  const [activeTab, setActiveTab] = useState<"file" | "text">("file");
  const [file, setFile] = useState<File | null>(null);
  const [textInput, setTextInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<string>("");
  const [result, setResult] = useState<OrderIngestionResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleReset = () => {
    setFile(null);
    setTextInput("");
    setResult(null);
    setErrorMsg(null);
    setLoading(false);
  };

  const handleClose = () => {
    handleReset();
    onClose();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setErrorMsg(null);
    }
  };

  const handleSampleText = () => {
    setTextInput(
`Từ: mua.hang@cty-abc.vn
Tới: sales@erpcopilot.vn
Tiêu đề: Đơn đặt hàng PO-2026-088 - Công ty TNHH Công Nghệ ABC

Kính gửi phòng Kinh doanh,
Công ty TNHH Công Nghệ ABC (Mã KH: CUS-0001) xin gửi đơn đặt hàng như sau:
1. Laptop Pro 14-inch M3 (Mã: SKU-001) - Số lượng: 2 chiếc
2. Màn hình Dell UltraSharp 27-inch 4K (Mã: SKU-002) - Số lượng: 2 chiếc

Đề nghị giao hàng trước ngày 25/10/2026.
Người liên hệ: Anh Tuấn (0912.345.678)
Trân trọng cảm ơn!`
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);

    try {
      let res: OrderIngestionResult;

      if (activeTab === "file") {
        if (!file) {
          throw new Error("Vui lòng chọn tệp tin đơn hàng (.pdf, .docx, .eml, .txt)");
        }
        const fileNameLower = file.name.toLowerCase();
        setLoadingStep("1/3. Đang đọc cấu trúc tệp tin " + file.name + "...");
        
        if (fileNameLower.endsWith(".eml")) {
          setLoadingStep("2/3. Phân giải email RFC822 và bóc tách thực thể AI...");
          res = await uploadOrderEmlApi(file);
        } else {
          setLoadingStep("2/3. Phân giải văn bản và trích xuất bằng Gemini Document AI...");
          res = await uploadOrderDocumentApi(file);
        }
      } else {
        if (!textInput.trim() || textInput.trim().length < 10) {
          throw new Error("Vui lòng nhập hoặc dán nội dung đơn hàng (tối thiểu 10 ký tự)");
        }
        setLoadingStep("1/2. Đang phân tích nội dung văn bản email đặt hàng...");
        res = await uploadOrderTextApi(textInput, "direct_paste_input");
      }

      setLoadingStep("3/3. Hoàn tất đối chiếu tồn kho và tạo đơn nháp...");
      setResult(res);
      const custDesc = res.resolved_customer_name ? `cho ${res.resolved_customer_name}` : "";
      toast.success("Bóc tách đơn hàng thành công", `Đã tạo đơn nháp ${custDesc} và chuyển vào Hộp thư phê duyệt.`);
      onSuccess?.(res);
    } catch (err: any) {
      const msg = err.message || "Đã xảy ra lỗi khi bóc tách đơn hàng.";
      setErrorMsg(msg);
      toast.error("Lỗi bóc tách đơn hàng", msg);
    } finally {
      setLoading(false);
      setLoadingStep("");
    }
  };

  const handleNavigateToApprovals = () => {
    handleClose();
    router.push("/approvals?status=pending");
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl border border-slate-200/90 shadow-2xl w-full max-w-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-xs border border-blue-100">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900 leading-tight">
                Document AI • Bóc tách đơn hàng tự động
              </h3>
              <p className="text-[11px] text-slate-500">
                Tự động nhận diện khách hàng, mã SKU, số lượng, kiểm tra tồn kho và tạo đơn nháp phê duyệt (HITL)
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body Cuộn */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">{errorMsg}</div>
            </div>
          )}

          {/* Khi đã có kết quả bóc tách */}
          {result ? (
            <div className="space-y-4 animate-in fade-in duration-200">
              <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold text-sm">
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    <span>Trích xuất & Tạo đơn nháp thành công!</span>
                  </div>
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-bold">
                    Trạng thái: Chờ duyệt (Pending)
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                  <div>
                    <span className="text-slate-500 block text-[11px]">Khách hàng nhận diện:</span>
                    <strong className="text-slate-900 text-[12.5px]">
                      {result.resolved_customer_name || result.resolved_customer_code || "Khách hàng ERP"}
                    </strong>
                    <span className="text-slate-500 text-[11px] block font-mono">
                      Mã: {result.resolved_customer_code || "—"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[11px]">Tổng giá trị đơn hàng:</span>
                    <strong className="text-emerald-700 text-base font-extrabold">
                      {formatVND(result.total_amount || 0)}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Bảng vật tư bóc tách */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                  <span>Mặt hàng đã trích xuất ({result.resolved_items?.length || 0})</span>
                  <span className="text-[11px] text-slate-400 font-normal">Đã kiểm tra đối soát DB</span>
                </div>

                <div className="border border-slate-200/90 rounded-2xl overflow-hidden">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="bg-slate-50 text-[10.5px] font-bold uppercase text-slate-500 border-b border-slate-200/80">
                      <tr>
                        <th className="py-2.5 px-3">Mã SKU</th>
                        <th className="py-2.5 px-3">Tên sản phẩm</th>
                        <th className="py-2.5 px-2 text-center">SL</th>
                        <th className="py-2.5 px-3 text-right">Đơn giá</th>
                        <th className="py-2.5 px-3 text-right">Thành tiền</th>
                        <th className="py-2.5 px-2 text-center">Tồn kho</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {result.resolved_items?.map((item, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/60">
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-800">{item.sku}</td>
                          <td className="py-2.5 px-3 text-slate-700 truncate max-w-[160px]">{item.product_name}</td>
                          <td className="py-2.5 px-2 text-center font-bold text-slate-900">{item.quantity}</td>
                          <td className="py-2.5 px-3 text-right text-slate-600">{formatVND(item.db_unit_price)}</td>
                          <td className="py-2.5 px-3 text-right font-bold text-blue-600">{formatVND(item.line_total)}</td>
                          <td className="py-2.5 px-2 text-center">
                            {item.stock_sufficient ? (
                              <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700">
                                Đủ hàng
                              </span>
                            ) : (
                              <span className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-50 text-rose-700">
                                Thiếu
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Cảnh báo nếu có */}
              {result.warnings && result.warnings.length > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-1 text-xs text-amber-800">
                  <div className="font-bold flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                    <span>Lưu ý cần xem xét khi phê duyệt:</span>
                  </div>
                  <ul className="list-disc list-inside text-[11.5px] space-y-0.5 text-amber-700">
                    {result.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Tab Selector */}
              <div className="flex rounded-2xl bg-slate-100 p-1 border border-slate-200/80">
                <button
                  type="button"
                  onClick={() => setActiveTab("file")}
                  className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer ${
                    activeTab === "file"
                      ? "bg-white text-blue-600 shadow-xs font-bold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <FileUp className="w-4 h-4" />
                  <span>Tải tệp tin (.EML / .PDF / .DOCX)</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("text")}
                  className={`flex-1 py-2 text-xs font-semibold rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer ${
                    activeTab === "text"
                      ? "bg-white text-blue-600 shadow-xs font-bold"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Mail className="w-4 h-4" />
                  <span>Dán văn bản Email / PO</span>
                </button>
              </div>

              {activeTab === "file" ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-200 hover:border-blue-500 rounded-2xl p-8 text-center cursor-pointer transition-colors bg-slate-50/50 hover:bg-blue-50/20 group"
                >
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    className="hidden"
                    accept=".pdf,.docx,.doc,.eml,.txt"
                  />
                  <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 group-hover:scale-105 transition-transform flex items-center justify-center mx-auto mb-3 shadow-2xs">
                    <Upload className="w-6 h-6" />
                  </div>
                  {file ? (
                    <div className="space-y-1">
                      <p className="text-xs font-bold text-blue-600 truncate">{file.name}</p>
                      <p className="text-[11px] text-slate-400">
                        {(file.size / 1024).toFixed(1)} KB • Nhấn để chọn lại tệp
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <p className="text-xs font-bold text-slate-700">Kéo thả hoặc bấm để chọn tệp đơn hàng</p>
                      <p className="text-[11px] text-slate-400">
                        Hỗ trợ định dạng email <code>.eml</code>, tài liệu <code>.pdf</code>, <code>.docx</code>
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-700">Nội dung văn bản email đặt hàng:</label>
                    <button
                      type="button"
                      onClick={handleSampleText}
                      className="text-[11px] font-semibold text-blue-600 hover:underline cursor-pointer flex items-center gap-1"
                    >
                      <Sparkles className="w-3 h-3" />
                      <span>Dán nội dung mẫu</span>
                    </button>
                  </div>
                  <textarea
                    rows={6}
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    placeholder="Dán toàn bộ nội dung email hoặc tin nhắn đặt hàng của khách hàng vào đây..."
                    className="w-full p-3.5 bg-slate-50 border border-slate-200/90 rounded-2xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all font-mono leading-relaxed"
                  />
                </div>
              )}

              {/* Trạng thái Loading */}
              {loading && (
                <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200 flex items-center gap-3 text-xs text-blue-800 animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin text-blue-600 shrink-0" />
                  <span className="font-semibold">{loadingStep || "AI Copilot đang xử lý..."}</span>
                </div>
              )}
            </form>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-2.5 shrink-0">
          {result ? (
            <>
              <button
                type="button"
                onClick={handleReset}
                className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
              >
                Bóc tách đơn khác
              </button>
              <button
                type="button"
                onClick={handleNavigateToApprovals}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs transition-all flex items-center gap-2 cursor-pointer active:scale-95"
              >
                <span>Mở Hộp thư phê duyệt</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-xl text-xs font-semibold transition-colors cursor-pointer"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading || (activeTab === "file" && !file) || (activeTab === "text" && !textInput.trim())}
                className="px-5 py-2 bg-[#0066FF] hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white rounded-xl text-xs font-bold shadow-xs transition-all flex items-center gap-2 cursor-pointer disabled:cursor-not-allowed active:scale-95"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Đang bóc tách...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Bóc tách & Tạo đơn nháp</span>
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

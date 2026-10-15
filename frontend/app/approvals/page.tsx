"use client";

import React, { useState, useEffect, Suspense } from "react";
import { 
  CheckSquare, 
  FileText, 
  ChevronRight, 
  Check, 
  X, 
  Lightbulb, 
  AlertCircle,
  Loader2,
  RefreshCw,
  Search,
  CheckCircle2,
  Info
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { 
  fetchApprovalsApi, 
  approveRequestApi, 
  rejectRequestApi, 
  ApprovalItem,
  ApprovalPayloadItem
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useToast } from "@/components/toast-provider";
import { useAuth } from "@/lib/auth-context";

function ApprovalsInboxContent() {
  const searchParams = useSearchParams();
  const urlStatus = searchParams.get("status") || "pending";
  const toast = useToast();
  const { hasPermission, isAdmin } = useAuth();
  const canApprove = isAdmin || hasPermission("orders:approve");

  const [activeTab, setActiveTab] = useState<string>(urlStatus === "all" ? "all" : urlStatus);
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<ApprovalItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [notification, setNotification] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  // Sync tab with URL query if changes
  useEffect(() => {
    if (urlStatus && urlStatus !== activeTab) {
      setActiveTab(urlStatus === "all" ? "all" : urlStatus);
    }
  }, [urlStatus]);

  // Fetch approvals from real backend API
  const loadApprovals = async () => {
    setLoading(true);
    try {
      const data = await fetchApprovalsApi(activeTab === "all" ? undefined : activeTab);
      setItems(data);
      if (data.length > 0) {
        setSelectedItem((prev) => {
          if (!prev) return data[0];
          const found = data.find((it) => it.id === prev.id);
          return found || data[0];
        });
      } else {
        setSelectedItem(null);
      }
    } catch (err: any) {
      setNotification({ type: "error", msg: "Lỗi tải danh sách phê duyệt: " + err.message });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApprovals();
  }, [activeTab]);

  // Lọc theo search term
  const filteredItems = items.filter((row) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    const orderNo = (row.payload?.order_number || "").toLowerCase();
    const custName = (row.payload?.customer_name || "").toLowerCase();
    const custCode = (row.payload?.customer_code || "").toLowerCase();
    return orderNo.includes(term) || custName.includes(term) || custCode.includes(term);
  });

  // Đếm số lượng theo trạng thái
  const pendingCount = items.filter((it) => it.status === "pending").length;

  const handleApprove = async () => {
    if (!selectedItem) return;

    const confirmed = await toast.confirm({
      title: "Xác nhận phê duyệt đơn hàng",
      message: `Bạn có chắc chắn muốn phê duyệt đơn hàng ${orderNumber} trị giá ${formatVND(totalAmount)} không?\n\nĐơn hàng sẽ được chuyển sang trạng thái đã chốt (Confirmed) và hệ thống sẽ tự động giữ chỗ (reserve) số lượng tồn kho khả dụng.`,
      confirmText: "Phê duyệt đơn hàng",
      isDanger: false,
    });
    if (!confirmed) return;

    setActionLoading(true);
    setNotification(null);
    try {
      const res = await approveRequestApi(selectedItem.id);
      const orderCode = res.order_number || selectedItem.payload?.order_number || selectedItem.target_id;
      toast.success("Phê duyệt thành công", `Đơn hàng ${orderCode} đã được chuyển sang trạng thái đã chốt (Confirmed).`);
      setNotification({ 
        type: "success", 
        msg: `Phê duyệt thành công đơn hàng ${orderCode}! Đơn hàng đã chuyển sang trạng thái đã chốt (Confirmed).` 
      });
      setItems((prev) =>
        prev.map((it) => (it.id === selectedItem.id ? { ...it, status: "approved" as const } : it))
      );
      setSelectedItem((prev) => (prev ? { ...prev, status: "approved" } : null));
    } catch (err: any) {
      toast.error("Lỗi phê duyệt", err.message);
      setNotification({ type: "error", msg: "Lỗi phê duyệt: " + err.message });
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedItem) return;

    const reason = await toast.prompt({
      title: "Từ chối yêu cầu phê duyệt",
      message: `Vui lòng nhập lý do từ chối yêu cầu phê duyệt đơn hàng ${orderNumber}:`,
      defaultValue: "Sai số lượng, sai thỏa thuận đơn giá hoặc tồn kho không đáp ứng",
      placeholder: "Nhập lý do từ chối chi tiết...",
      confirmText: "Từ chối đơn hàng",
      isDanger: true,
    });
    if (reason === null) return;

    setActionLoading(true);
    setNotification(null);
    try {
      const res = await rejectRequestApi(selectedItem.id, reason);
      const orderCode = res.order_number || selectedItem.payload?.order_number || selectedItem.target_id;
      toast.warning("Đã từ chối đơn hàng", `Đơn hàng ${orderCode} đã bị từ chối với lý do: "${reason}"`);
      setNotification({ 
        type: "success", 
        msg: `Đã từ chối đơn hàng ${orderCode}! Lý do: "${reason}"` 
      });
      setItems((prev) =>
        prev.map((it) => (it.id === selectedItem.id ? { ...it, status: "rejected" as const } : it))
      );
      setSelectedItem((prev) => (prev ? { ...prev, status: "rejected" } : null));
    } catch (err: any) {
      toast.error("Lỗi từ chối", err.message);
      setNotification({ type: "error", msg: "Lỗi từ chối: " + err.message });
    } finally {
      setActionLoading(false);
    }
  };

  // Trích xuất thông tin payload của selected item
  const payload = selectedItem?.payload || {};
  const orderNumber = payload.order_number || `PO-${selectedItem?.target_id?.slice(0, 8).toUpperCase()}`;
  const customerName = payload.customer_name || "Khách hàng ERP";
  const customerCode = payload.customer_code || "CUS-UNKNOWN";
  const deliveryDate = payload.requested_delivery_date || "Theo thỏa thuận";
  const totalAmount = Number(payload.total_amount || 0);
  const products: ApprovalPayloadItem[] = payload.items || [];
  const sourceIdentifier = payload.source_identifier || (payload.source_type ? `Nguồn: ${payload.source_type}` : "Tạo từ hệ thống");
  const aiNote = payload.ai_notes || `Đơn hàng nháp được tạo tự động qua quy trình trích xuất thông minh từ ${sourceIdentifier}. Hệ thống đã tự động snapshot giá niêm yết và kiểm tra tính hợp lệ của khách hàng. Vui lòng xác nhận để chính thức giữ tồn kho và ghi nhận đơn hàng.`;

  return (
    <div className="flex-1 min-w-0 h-full flex flex-col lg:flex-row overflow-hidden bg-[#F8FAFC]">
      {/* ========================================================
          CỘT TRÁI: Danh sách bảng yêu cầu phê duyệt
         ======================================================== */}
      <div className="flex-1 min-w-0 flex flex-col h-full overflow-hidden border-r border-slate-200/80 bg-[#F8FAFC]">
        {/* 1. Header CỐ ĐỊNH ở trên cùng của cột trái */}
        <div className="p-5 pb-3 border-b border-slate-200/80 bg-[#F8FAFC] space-y-3 shrink-0">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2.5">
                <span className="text-blue-600 font-bold text-base">📌</span>
                <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                  Hộp thư phê duyệt (Human-In-The-Loop)
                </h1>
                <span className="bg-rose-50 text-rose-600 border border-rose-100 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                  {pendingCount} chờ xử lý
                </span>
              </div>
              <p className="text-slate-500 text-[11.5px]">
                Mọi hành vi tạo đơn hàng từ AI Copilot, email hoặc tài liệu đều cần người có thẩm quyền xác nhận trước khi chốt đơn.
              </p>
            </div>

            <button
              type="button"
              onClick={loadApprovals}
              disabled={loading}
              className="flex items-center gap-1.5 text-xs text-slate-600 hover:text-blue-600 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-2xs hover:bg-slate-50 transition-colors cursor-pointer shrink-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span>Làm mới</span>
            </button>
          </div>

          {/* Filter Bar & Search */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-0.5">
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setActiveTab("all")}
                className={`px-3 py-1 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                  activeTab === "all"
                    ? "bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200"
                    : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Tất cả ({items.length})
              </button>
              <button
                onClick={() => setActiveTab("pending")}
                className={`px-3 py-1 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === "pending"
                    ? "bg-[#0066FF] text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Chờ phê duyệt ({pendingCount})
              </button>
              <button
                onClick={() => setActiveTab("approved")}
                className={`px-3 py-1 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                  activeTab === "approved"
                    ? "bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200"
                    : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Đã duyệt
              </button>
              <button
                onClick={() => setActiveTab("rejected")}
                className={`px-3 py-1 rounded-xl text-xs font-medium transition-all cursor-pointer ${
                  activeTab === "rejected"
                    ? "bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200"
                    : "text-slate-600 hover:bg-slate-200/60"
                }`}
              >
                Đã từ chối
              </button>
            </div>

            <div className="relative w-60">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Tìm mã đơn, khách hàng..."
                className="w-full bg-white border border-slate-200 text-xs rounded-xl pl-8 pr-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-slate-400"
              />
            </div>
          </div>

          {/* Notification Alert Box */}
          {notification && (
            <div className={`p-2.5 rounded-xl text-xs flex items-center justify-between border ${
              notification.type === "success" 
                ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
                : "bg-rose-50 text-rose-800 border-rose-200"
            }`}>
              <div className="flex items-center gap-2">
                {notification.type === "success" ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                )}
                <span>{notification.msg}</span>
              </div>
              <button 
                type="button" 
                onClick={() => setNotification(null)}
                className="text-slate-400 hover:text-slate-600 ml-2 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* 2. Bảng Danh sách đơn hàng CUỘN ĐỘC LẬP */}
        <div className="flex-1 min-w-0 overflow-y-auto p-5 pt-3">
          <div className="bg-white border border-slate-200/90 rounded-2xl overflow-hidden shadow-2xs">
            {loading ? (
              <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                <span className="text-xs">Đang tải danh sách phê duyệt từ máy chủ...</span>
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="py-20 flex flex-col items-center justify-center gap-2 text-slate-400">
                <Info className="w-8 h-8 text-slate-300" />
                <p className="text-sm font-semibold text-slate-600">Không có yêu cầu phê duyệt nào</p>
                <p className="text-xs text-slate-400">Tất cả các đơn hàng đã được xử lý xong hoặc không tìm thấy kết quả phù hợp.</p>
              </div>
            ) : (
              <div className="overflow-x-auto w-full">
                <table className="w-full min-w-[700px] text-left text-xs">
                  {/* Table Header CỐ ĐỊNH khi cuộn bảng */}
                  <thead className="bg-[#F8FAFC] text-slate-500 font-semibold border-b border-slate-200/80 sticky top-0 z-10 shadow-2xs">
                    <tr>
                      <th className="py-2.5 px-4 font-medium w-12 text-center bg-[#F8FAFC]">STT</th>
                      <th className="py-2.5 px-4 font-medium bg-[#F8FAFC]">Loại yêu cầu</th>
                      <th className="py-2.5 px-4 font-medium bg-[#F8FAFC]">Mã đơn / Nội dung</th>
                      <th className="py-2.5 px-4 font-medium bg-[#F8FAFC]">Nguồn tiếp nhận</th>
                      <th className="py-2.5 px-4 font-medium bg-[#F8FAFC]">Thời gian</th>
                      <th className="py-2.5 px-4 font-medium text-center bg-[#F8FAFC]">Trạng thái</th>
                      <th className="py-2.5 px-3 w-10 bg-[#F8FAFC]"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {filteredItems.map((row, idx) => {
                      const isSelected = selectedItem?.id === row.id;
                      const rOrderNo = row.payload?.order_number || `PO-${row.target_id.slice(0, 8).toUpperCase()}`;
                      const rCustName = row.payload?.customer_name || "Khách hàng";
                      const rTotal = Number(row.payload?.total_amount || 0);
                      const rItemsCount = row.payload?.items?.length || 0;
                      const rDate = row.created_at ? new Date(row.created_at).toLocaleDateString("vi-VN") : "Hôm nay";
                      const rTime = row.created_at ? new Date(row.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

                      return (
                        <tr
                          key={row.id}
                          onClick={() => setSelectedItem(row)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? "bg-blue-50/70" : "hover:bg-slate-50/80"
                          }`}
                        >
                          <td className="py-3 px-4 text-center text-slate-400 font-medium">
                            {idx + 1}
                          </td>
                          <td className="py-3 px-4">
                            <span className="font-semibold text-slate-800 block text-xs">
                              {row.action_type === "create_sales_order_draft" || row.action_type === "create_sales_order"
                                ? "Đơn hàng nháp"
                                : row.action_type === "create_sales_order_from_document"
                                ? "Đơn từ tài liệu"
                                : row.action_type}
                            </span>
                            <span className="text-[11px] text-blue-600 font-mono">
                              {rOrderNo}
                            </span>
                          </td>
                          <td className="py-3 px-4 max-w-xs">
                            <div className="font-medium text-slate-900 truncate">
                              {rCustName}
                            </div>
                            <div className="text-[11px] text-slate-500">
                              {rItemsCount} sản phẩm • {formatVND(rTotal)}
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span className="text-[11.5px] text-slate-700 block truncate max-w-[130px]">
                              {row.payload?.source_identifier || row.payload?.source_type || "Copilot Chat"}
                            </span>
                            <span className="text-[10.5px] text-slate-400">
                              ERP System
                            </span>
                          </td>
                          <td className="py-3 px-4 whitespace-nowrap">
                            <div className="text-[11.5px] text-slate-800 font-medium">{rDate}</div>
                            <div className="text-[10.5px] text-slate-400">{rTime}</div>
                          </td>
                          <td className="py-3 px-4 text-center whitespace-nowrap">
                            {row.status === "pending" && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                Chờ phê duyệt
                              </span>
                            )}
                            {row.status === "approved" && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                Đã phê duyệt
                              </span>
                            )}
                            {row.status === "rejected" && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10.5px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
                                Đã từ chối
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-3 text-right">
                            <ChevronRight className={`w-4 h-4 transition-transform ${isSelected ? "text-blue-600 translate-x-1" : "text-slate-300"}`} />
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================
          CỘT PHẢI: Chi tiết yêu cầu phê duyệt đang chọn
         ======================================================== */}
      {selectedItem ? (
        <aside className="w-full lg:w-[380px] xl:w-[410px] bg-white border-l border-slate-200/90 flex flex-col h-full shrink-0 shadow-lg shadow-slate-900/5 overflow-hidden">
          {/* 1. Header Chi tiết CỐ ĐỊNH Ở TRÊN */}
          <div className="p-4 sm:p-5 border-b border-slate-100 space-y-2.5 shrink-0 bg-white">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <span className="text-[10.5px] font-bold uppercase tracking-wider text-blue-600">
                  Chi tiết đơn hàng nháp
                </span>
                <h2 className="text-lg font-extrabold text-slate-900 tracking-tight truncate">
                  {orderNumber}
                </h2>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {selectedItem.status === "pending" && (
                  <span className="bg-amber-50 text-amber-700 border border-amber-200 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                    Chờ duyệt
                  </span>
                )}
                {selectedItem.status === "approved" && (
                  <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                    Đã duyệt
                  </span>
                )}
                {selectedItem.status === "rejected" && (
                  <span className="bg-rose-50 text-rose-700 border border-rose-200 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                    Đã từ chối
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => setSelectedItem(null)}
                  title="Đóng chi tiết (Mở rộng bảng)"
                  className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer ml-1"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Thông tin Khách hàng */}
            <div className="bg-[#F8FAFC] border border-slate-200/80 rounded-xl p-3 space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Khách hàng:</span>
                <span className="font-bold text-slate-900 truncate max-w-[200px]">{customerName}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Mã khách hàng:</span>
                <span className="font-mono text-blue-600 font-semibold">{customerCode}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-500">Ngày giao dự kiến:</span>
                <span className="text-slate-700">{deliveryDate}</span>
              </div>
            </div>
          </div>

          {/* 2. Bảng sản phẩm chi tiết CUỘN ĐỘC LẬP Ở GIỮA */}
          <div className="p-5 space-y-4 flex-1 overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-900 tracking-tight uppercase">
                Danh sách mặt hàng ({products.length})
              </h3>
              <span className="text-xs font-extrabold text-blue-600">
                Tổng: {formatVND(totalAmount)}
              </span>
            </div>

            <div className="border border-slate-200/80 rounded-xl overflow-hidden text-xs">
              <table className="w-full text-left">
                <thead className="bg-[#F8FAFC] text-slate-400 font-medium border-b border-slate-200/80">
                  <tr>
                    <th className="py-2 px-3 font-medium">Sản phẩm / SKU</th>
                    <th className="py-2 px-2 text-center font-medium">SL</th>
                    <th className="py-2 px-3 text-right font-medium">Đơn giá</th>
                    <th className="py-2 px-3 text-right font-medium">Thành tiền</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {products.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-4 text-center text-slate-400">
                        Chưa có chi tiết mặt hàng
                      </td>
                    </tr>
                  ) : (
                    products.map((p, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/60">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-slate-900 truncate max-w-[130px]">
                            {p.product_name || p.sku}
                          </div>
                          <div className="text-[10px] text-blue-600 font-mono">
                            {p.sku}
                          </div>
                          {p.stock_sufficient === false && (
                            <span className="text-[9.5px] text-amber-600 font-medium block">
                              ⚠️ Tồn kho không đủ
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-2 text-center font-bold text-slate-800">
                          {p.quantity}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-600">
                          {formatVND(p.unit_price)}
                        </td>
                        <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                          {formatVND(p.line_total)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Ghi chú AI & Nguồn gốc */}
            <div className="bg-sky-50/60 border border-sky-100 rounded-xl p-3.5 space-y-1.5">
              <div className="flex items-center gap-1.5 text-sky-800 text-xs font-bold">
                <Lightbulb className="w-3.5 h-3.5 text-blue-600" />
                <span>Ghi chú từ AI Ingestion</span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed whitespace-pre-wrap">
                {aiNote}
              </p>
              <div className="pt-1 flex items-center gap-1.5 text-[10px] text-slate-400">
                <FileText className="w-3 h-3" />
                <span className="truncate">Tệp nguồn: {sourceIdentifier}</span>
              </div>
            </div>
          </div>

          {/* 3. Footer Actions: Phê duyệt / Từ chối CỐ ĐỊNH Ở ĐÁY */}
          <div className="p-4 border-t border-slate-200/80 bg-white shrink-0 shadow-lg">
            {selectedItem.status === "pending" ? (
              canApprove ? (
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={handleReject}
                    disabled={actionLoading}
                    className="flex-1 bg-white hover:bg-rose-50 text-rose-600 border border-rose-200 hover:border-rose-300 px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-2xs flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
                  >
                    <X className="w-4 h-4" />
                    <span>Từ chối</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={actionLoading}
                    className="flex-1 bg-[#0066FF] hover:bg-blue-700 text-white px-4 py-2.5 rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-600/20 flex items-center justify-center gap-1.5 active:scale-95 cursor-pointer disabled:opacity-50"
                  >
                    {actionLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    <span>Phê duyệt ngay</span>
                  </button>
                </div>
              ) : (
                <div className="text-center py-2.5 px-3 text-xs text-amber-800 font-medium bg-amber-50 rounded-xl border border-amber-200/80 flex items-center justify-center gap-2">
                  <Info className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>Chế độ chỉ xem: Bạn không có quyền phê duyệt đơn hàng. Vui lòng liên hệ Quản lý bán hàng.</span>
                </div>
              )
            ) : (
              <div className="text-center py-2 text-xs text-slate-500 font-medium bg-slate-50 rounded-xl border border-slate-100">
                {selectedItem.status === "approved" ? "✅ Yêu cầu này đã được phê duyệt thành công." : "❌ Yêu cầu này đã bị từ chối."}
              </div>
            )}
          </div>
        </aside>
      ) : (
        <aside className="w-full lg:w-[420px] xl:w-[450px] bg-white border-l border-slate-200/90 flex flex-col items-center justify-center p-8 text-center text-slate-400 shrink-0">
          <CheckSquare className="w-12 h-12 text-slate-200 mb-3" />
          <h3 className="text-sm font-bold text-slate-700">Chưa chọn yêu cầu</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Vui lòng nhấp vào một dòng trong bảng bên trái để xem đầy đủ thông tin đơn hàng và thực hiện phê duyệt.
          </p>
        </aside>
      )}
    </div>
  );
}

export default function ApprovalsPage() {
  return (
    <Suspense fallback={
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    }>
      <ApprovalsInboxContent />
    </Suspense>
  );
}

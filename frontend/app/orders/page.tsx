"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  ShoppingCart, 
  Search, 
  RefreshCw, 
  FileText, 
  Calendar, 
  ChevronRight, 
  X, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  Sparkles,
  ExternalLink,
  Package,
  Layers,
  DollarSign
} from "lucide-react";
import { fetchOrders, fetchOrderDetail, fetchCustomers, SalesOrderItem, CustomerItem } from "@/lib/api";
import { formatVND } from "@/lib/utils";

export default function OrdersPage() {
  const [orders, setOrders] = useState<SalesOrderItem[]>([]);
  const [customerMap, setCustomerMap] = useState<Record<string, CustomerItem>>({});
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedOrder, setSelectedOrder] = useState<SalesOrderItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchCustomers({ limit: 100 })
      .then((custs) => {
        const map: Record<string, CustomerItem> = {};
        custs.forEach((c) => {
          map[c.id] = c;
        });
        setCustomerMap(map);
      })
      .catch(() => {});
  }, []);

  const getCustomerInfo = (order: SalesOrderItem) => {
    const cust = customerMap[order.customer_id];
    const name = order.customer_name || cust?.name || "Khách hàng ERP";
    const code = order.customer_code || cust?.code || "";
    return { name, code };
  };

  const loadOrders = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchOrders({
        status: statusFilter === "all" ? undefined : statusFilter,
      });
      setOrders(data);
    } catch (err: any) {
      setErrorMsg("Lỗi khi tải danh sách đơn hàng: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, [statusFilter]);

  const handleSelectOrder = async (orderId: string) => {
    setDetailLoading(true);
    try {
      const detail = await fetchOrderDetail(orderId);
      setSelectedOrder(detail);
    } catch (err) {
      // Fallback to item in list
      const found = orders.find((o) => o.id === orderId);
      if (found) setSelectedOrder(found);
    } finally {
      setDetailLoading(false);
    }
  };

  // Filtered by search term
  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      if (!searchTerm.trim()) return true;
      const term = searchTerm.toLowerCase();
      const orderNo = (o.order_number || "").toLowerCase();
      const { name, code } = getCustomerInfo(o);
      const custId = (o.customer_id || "").toLowerCase();
      return (
        orderNo.includes(term) ||
        name.toLowerCase().includes(term) ||
        code.toLowerCase().includes(term) ||
        custId.includes(term)
      );
    });
  }, [orders, searchTerm, customerMap]);

  // Quick metrics calculations
  const metrics = useMemo(() => {
    const total = orders.length;
    const confirmed = orders.filter((o) => o.status === "confirmed").length;
    const draft = orders.filter((o) => o.status === "draft").length;
    const totalRevenue = orders
      .filter((o) => o.status === "confirmed")
      .reduce((sum, o) => sum + (o.total_amount || 0), 0);
    return { total, confirmed, draft, totalRevenue };
  }, [orders]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "confirmed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Đã xác nhận
          </span>
        );
      case "draft":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            Đơn nháp (Chờ xử lý)
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <XCircle className="w-3 h-3 text-rose-600" />
            Đã hủy
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Header phân hệ */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-xs border border-blue-100">
            <ShoppingCart className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Quản lý Đơn hàng Bán (Sales Orders)
            </h1>
            <p className="text-xs text-slate-500">
              Danh mục đơn đặt hàng, trạng thái xử lý và chi tiết từng dòng sản phẩm thời gian thực
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadOrders}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <Link
            href="/approvals"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer"
          >
            <Clock className="w-3.5 h-3.5 text-amber-500" />
            <span>Đơn chờ duyệt</span>
          </Link>

          <Link
            href="/copilot"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Tạo đơn bằng AI</span>
          </Link>
        </div>
      </div>

      {/* 2. Thẻ thống kê nhanh */}
      <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-4 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Package className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tổng số đơn hàng</div>
            <div className="text-base font-bold text-slate-900">{metrics.total} đơn</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Đã xác nhận</div>
            <div className="text-base font-bold text-emerald-600">{metrics.confirmed} đơn</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Đơn nháp (Chờ xử lý)</div>
            <div className="text-base font-bold text-amber-600">{metrics.draft} đơn</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center shrink-0">
            <DollarSign className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-medium text-slate-400">Doanh số xác nhận</div>
            <div className="text-sm font-bold text-slate-900 truncate">
              {formatVND(metrics.totalRevenue)}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Thanh tìm kiếm và bộ lọc trạng thái */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          {["all", "draft", "confirmed", "cancelled"].map((st) => {
            const labels: Record<string, string> = {
              all: "Tất cả đơn",
              draft: "Đơn nháp",
              confirmed: "Đã xác nhận",
              cancelled: "Đã hủy",
            };
            const active = statusFilter === st;
            return (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer border ${
                  active
                    ? "bg-blue-600 text-white border-blue-600 shadow-2xs"
                    : "bg-white text-slate-600 border-slate-200/90 hover:bg-slate-50"
                }`}
              >
                {labels[st]}
              </button>
            );
          })}
        </div>

        <div className="relative w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Tìm theo mã đơn hoặc khách hàng..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200/90 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-2xs"
          />
        </div>
      </div>

      {/* 4. Thông báo lỗi nếu có */}
      {errorMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {/* 5. Nội dung Bảng Đơn hàng (Cuộn mượt mà) */}
      <div className="flex-1 px-6 pb-6 overflow-hidden flex gap-4">
        <div className="flex-1 bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Mã đơn hàng</th>
                  <th className="py-3 px-4">Khách hàng</th>
                  <th className="py-3 px-4">Ngày tạo</th>
                  <th className="py-3 px-4 text-center">Số mục</th>
                  <th className="py-3 px-4 text-right">Tổng tiền</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-28" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-36" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-100 rounded-md w-24" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-4 bg-slate-100 rounded-md w-8 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-right"><div className="h-4 bg-slate-200 rounded-md w-24 ml-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-14 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredOrders.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <ShoppingCart className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Không tìm thấy đơn hàng nào</p>
                      <p className="text-[11px] text-slate-400 mt-1">Thử đổi từ khóa tìm kiếm hoặc lọc trạng thái khác</p>
                    </td>
                  </tr>
                ) : (
                  filteredOrders.map((order) => {
                    const isSelected = selectedOrder?.id === order.id;
                    const itemsCount = order.items?.length || 0;
                    const dateFormatted = order.created_at
                      ? new Date(order.created_at).toLocaleDateString("vi-VN", {
                          day: "2-digit",
                          month: "2-digit",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      : "—";

                    return (
                      <tr
                        key={order.id}
                        onClick={() => handleSelectOrder(order.id)}
                        className={`hover:bg-blue-50/40 transition-colors cursor-pointer ${
                          isSelected ? "bg-blue-50/70 font-medium" : ""
                        }`}
                      >
                        <td className="py-3.5 px-4 font-bold text-blue-600 flex items-center gap-1.5">
                          <FileText className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                          <span>{order.order_number}</span>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-900 leading-snug">
                            {getCustomerInfo(order).name}
                          </div>
                          {getCustomerInfo(order).code && (
                            <div className="text-[11px] font-mono text-blue-600 font-medium">
                              {getCustomerInfo(order).code}
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500">
                          {dateFormatted}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <span className="w-6 h-6 inline-flex items-center justify-center rounded-lg bg-slate-100 text-slate-700 text-[11px] font-semibold">
                            {itemsCount}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right font-bold text-slate-900">
                          {formatVND(order.total_amount)}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {getStatusBadge(order.status)}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectOrder(order.id);
                            }}
                            className="text-xs text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2.5 py-1 rounded-lg transition-colors font-semibold"
                          >
                            Chi tiết
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
            <span>Hiển thị {filteredOrders.length} / {orders.length} đơn hàng</span>
            <span>ERP AI Copilot Sales Order Service</span>
          </div>
        </div>

        {/* 6. Chi tiết đơn hàng (Side Drawer khi bấm chọn) */}
        {selectedOrder && (
          <div className="w-96 bg-white rounded-2xl border border-slate-200/90 shadow-md flex flex-col overflow-hidden shrink-0 animate-in slide-in-from-right-4 duration-150">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-600" />
                <span className="font-bold text-sm text-slate-900">
                  {selectedOrder.order_number}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Thông tin đơn hàng */}
              <div className="p-3 bg-[#F8FAFC] rounded-xl border border-slate-200/80 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Trạng thái:</span>
                  <div>{getStatusBadge(selectedOrder.status)}</div>
                </div>
                <div className="flex justify-between items-start gap-2">
                  <span className="text-slate-400 shrink-0">Khách hàng:</span>
                  <div className="text-right">
                    <span className="font-semibold text-slate-900 block">
                      {getCustomerInfo(selectedOrder).name}
                    </span>
                    {getCustomerInfo(selectedOrder).code && (
                      <span className="text-[11px] font-mono text-blue-600 font-medium">
                        {getCustomerInfo(selectedOrder).code}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Ngày tạo:</span>
                  <span className="text-slate-600">
                    {selectedOrder.created_at ? new Date(selectedOrder.created_at).toLocaleString("vi-VN") : "—"}
                  </span>
                </div>
                <div className="flex justify-between border-t border-slate-200/60 pt-2 font-bold">
                  <span className="text-slate-700">Tổng thanh toán:</span>
                  <span className="text-blue-600 text-sm">{formatVND(selectedOrder.total_amount)}</span>
                </div>
              </div>

              {/* Danh sách vật tư / sản phẩm */}
              <div className="space-y-2">
                <div className="text-xs font-bold text-slate-800 flex items-center justify-between">
                  <span>Mặt hàng đặt mua ({selectedOrder.items?.length || 0})</span>
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                </div>

                {detailLoading ? (
                  <div className="py-8 text-center text-xs text-slate-400">Đang tải chi tiết vật tư...</div>
                ) : !selectedOrder.items || selectedOrder.items.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-xl text-center text-xs text-slate-400">
                    Không có dòng sản phẩm nào trong đơn hàng này
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedOrder.items.map((item, idx) => (
                      <div
                        key={item.id || idx}
                        className="p-3 bg-white border border-slate-200/80 rounded-xl space-y-1.5 shadow-2xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-xs text-slate-800 truncate">
                            {item.product_name || item.sku}
                          </span>
                          <span className="text-[11px] font-bold text-blue-600 shrink-0 ml-2">
                            {formatVND(item.line_total)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>Mã: <code className="text-slate-700 font-mono">{item.sku}</code></span>
                          <span>SL: <strong>{item.quantity}</strong> × {formatVND(item.unit_price)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Footer hành động */}
            <div className="p-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between gap-2">
              <Link
                href={`/copilot?q=Kiểm tra chi tiết đơn hàng ${selectedOrder.order_number}`}
                className="flex-1 text-center py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>Hỏi AI về đơn này</span>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

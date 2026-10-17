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
  DollarSign,
  Truck,
  Loader2,
  Printer,
  CreditCard,
  AlertTriangle,
  Ban,
  Edit2,
  Trash2,
  Plus,
} from "lucide-react";
import {
  fetchOrders,
  fetchOrderDetail,
  fetchCustomers,
  fetchProducts,
  deliverOrderApi,
  cancelSalesOrderApi,
  fetchCustomerCreditCheckApi,
  createPaymentApi,
  createOrderDraftApi,
  updateOrderDraftApi,
  deleteOrderDraftApi,
  SalesOrderItem,
  CustomerItem,
  ProductItem,
  CustomerCreditInfo,
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/toast-provider";
import { PdfPreviewModal } from "@/components/pdf-preview-modal";

export default function OrdersPage() {
  const toast = useToast();
  const { hasPermission, isAdmin } = useAuth();
  const canDeliver = isAdmin || hasPermission("inventory:write");
  const canCancel = isAdmin || hasPermission("orders:cancel");
  const canPayment = isAdmin || hasPermission("payments:create");
  const canCreate = isAdmin || hasPermission("orders:create");

  const [orders, setOrders] = useState<SalesOrderItem[]>([]);
  const [customerMap, setCustomerMap] = useState<Record<string, CustomerItem>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [deliverLoading, setDeliverLoading] = useState(false);
  const [deliverModalOrder, setDeliverModalOrder] =
    useState<SalesOrderItem | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [cancelModalOrder, setCancelModalOrder] =
    useState<SalesOrderItem | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedOrder, setSelectedOrder] = useState<SalesOrderItem | null>(
    null,
  );
  const [detailLoading, setDetailLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [previewPdfOrder, setPreviewPdfOrder] = useState<{
    orderId: string;
    orderNumber: string;
  } | null>(null);
  const [creditInfo, setCreditInfo] = useState<CustomerCreditInfo | null>(null);
  const [creditLoading, setCreditLoading] = useState(false);

  // State Modal Thu tiền bán hàng
  const [paymentModalOrder, setPaymentModalOrder] =
    useState<SalesOrderItem | null>(null);
  const [paymentAmount, setPaymentAmount] = useState<number>(0);
  const [paymentMethod, setPaymentMethod] = useState<string>("bank_transfer");
  const [paymentRefCode, setPaymentRefCode] = useState<string>("");
  const [paymentNote, setPaymentNote] = useState<string>("");
  const [paymentSubmitting, setPaymentSubmitting] = useState(false);

  // State Modal Tạo/Sửa đơn hàng
  const [isOrderFormOpen, setIsOrderFormOpen] = useState(false);
  const [editingOrderId, setEditingOrderId] = useState<string | null>(null);
  const [formCustomerCode, setFormCustomerCode] = useState("");
  const [formCustomerPoNumber, setFormCustomerPoNumber] = useState("");
  const [formItems, setFormItems] = useState<
    Array<{ sku: string; quantity: number }>
  >([{ sku: "", quantity: 1 }]);
  const [formDeliveryDate, setFormDeliveryDate] = useState("");
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Danh mục sản phẩm catalog
  const [productsList, setProductsList] = useState<ProductItem[]>([]);
  const [productMap, setProductMap] = useState<Record<string, ProductItem>>({});

  // State Modal Xóa đơn nháp
  const [deleteModalOrder, setDeleteModalOrder] =
    useState<SalesOrderItem | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const handlePaymentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!paymentModalOrder) return;
    if (paymentAmount <= 0) {
      toast.warning("Số tiền không hợp lệ", "Số tiền thu phải lớn hơn 0 VND.");
      return;
    }
    setPaymentSubmitting(true);
    try {
      const res = await createPaymentApi({
        customer_id: paymentModalOrder.customer_id,
        order_id: paymentModalOrder.id,
        amount: Number(paymentAmount),
        payment_method: paymentMethod,
        reference_code: paymentRefCode.trim() || undefined,
        note: paymentNote.trim() || undefined,
      });
      toast.success(
        "Thu tiền thành công!",
        `Đã tạo phiếu thu ${res.payment_number} số tiền ${formatVND(res.amount)} và cấn trừ công nợ khách hàng.`,
      );
      setPaymentModalOrder(null);
      await loadOrders();
      if (selectedOrder && selectedOrder.id === paymentModalOrder.id) {
        handleSelectOrder(selectedOrder.id);
      }
    } catch (err: any) {
      toast.error(
        "Lỗi thu tiền",
        err.message || "Không thể tạo phiếu thu tiền",
      );
    } finally {
      setPaymentSubmitting(false);
    }
  };

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

    fetchProducts()
      .then((prods) => {
        setProductsList(prods);
        const map: Record<string, ProductItem> = {};
        prods.forEach((p) => {
          map[p.sku] = p;
        });
        setProductMap(map);
      })
      .catch(() => {});
  }, []);

  const formTotalAmount = useMemo(() => {
    return formItems.reduce((acc, item) => {
      const p = productMap[item.sku];
      const price = p ? Number(p.unit_price) : 0;
      return acc + (Number(item.quantity) || 0) * price;
    }, 0);
  }, [formItems, productMap]);

  const openCreateOrderModal = () => {
    setEditingOrderId(null);
    const firstCust = Object.values(customerMap)[0]?.code || "";
    setFormCustomerCode(firstCust);
    setFormCustomerPoNumber("");
    const firstSku = productsList[0]?.sku || "";
    setFormItems([{ sku: firstSku, quantity: 1 }]);
    setFormDeliveryDate("");
    setFormError(null);
    setIsOrderFormOpen(true);
  };

  const openEditOrderModal = (order: SalesOrderItem) => {
    setEditingOrderId(order.id);
    const cust = customerMap[order.customer_id];
    setFormCustomerCode(order.customer_code || cust?.code || "");
    setFormCustomerPoNumber(order.customer_po_number || "");
    if (order.items && order.items.length > 0) {
      setFormItems(
        order.items.map((it) => ({
          sku: it.sku,
          quantity: it.quantity,
        })),
      );
    } else {
      const firstSku = productsList[0]?.sku || "";
      setFormItems([{ sku: firstSku, quantity: 1 }]);
    }
    setFormDeliveryDate("");
    setFormError(null);
    setIsOrderFormOpen(true);
  };

  const handleOrderFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!formCustomerCode) {
      setFormError("Vui lòng chọn khách hàng.");
      return;
    }
    if (formItems.length === 0) {
      setFormError("Đơn hàng phải có ít nhất 1 dòng sản phẩm.");
      return;
    }
    for (const item of formItems) {
      if (!item.sku) {
        setFormError("Vui lòng chọn SKU sản phẩm cho tất cả các dòng.");
        return;
      }
      if (item.quantity <= 0) {
        setFormError(`Số lượng cho SKU ${item.sku} phải lớn hơn 0.`);
        return;
      }
    }

    setFormSubmitting(true);
    try {
      if (editingOrderId) {
        const res = await updateOrderDraftApi(editingOrderId, {
          customer_code: formCustomerCode,
          customer_po_number: formCustomerPoNumber.trim() || undefined,
          items: formItems,
          requested_delivery_date: formDeliveryDate || undefined,
        });
        toast.success(
          "Cập nhật đơn hàng thành công!",
          `Đơn hàng ${res.order_number} đã được cập nhật.`,
        );
      } else {
        const res = await createOrderDraftApi({
          customer_code: formCustomerCode,
          customer_po_number: formCustomerPoNumber.trim() || undefined,
          items: formItems,
          requested_delivery_date: formDeliveryDate || undefined,
        });
        toast.success(
          "Tạo đơn hàng thành công!",
          `Đã tạo đơn hàng nháp ${res.order_number}.`,
        );
      }
      setIsOrderFormOpen(false);
      await loadOrders();
      if (editingOrderId && selectedOrder?.id === editingOrderId) {
        handleSelectOrder(editingOrderId);
      }
    } catch (err: any) {
      setFormError(err.message || "Lỗi khi lưu đơn hàng.");
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleConfirmDeleteDraft = async () => {
    if (!deleteModalOrder) return;
    setDeleteLoading(true);
    try {
      await deleteOrderDraftApi(deleteModalOrder.id);
      toast.success(
        "Đã xóa đơn hàng nháp!",
        `Đơn ${deleteModalOrder.order_number} đã được xóa khỏi hệ thống.`,
      );
      if (selectedOrder?.id === deleteModalOrder.id) {
        setSelectedOrder(null);
      }
      setDeleteModalOrder(null);
      await loadOrders();
    } catch (err: any) {
      toast.error("Lỗi khi xóa đơn hàng", err.message);
    } finally {
      setDeleteLoading(false);
    }
  };

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
    setCreditInfo(null);
    try {
      const detail = await fetchOrderDetail(orderId);
      setSelectedOrder(detail);
      const custId = detail.customer_id;
      if (custId) {
        setCreditLoading(true);
        fetchCustomerCreditCheckApi(custId, 0)
          .then((c) => setCreditInfo(c))
          .catch(() => setCreditInfo(null))
          .finally(() => setCreditLoading(false));
      }
    } catch (err) {
      // Fallback to item in list
      const found = orders.find((o) => o.id === orderId);
      if (found) {
        setSelectedOrder(found);
        if (found.customer_id) {
          setCreditLoading(true);
          fetchCustomerCreditCheckApi(found.customer_id, 0)
            .then((c) => setCreditInfo(c))
            .catch(() => setCreditInfo(null))
            .finally(() => setCreditLoading(false));
        }
      }
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
    const delivered = orders.filter((o) => o.status === "delivered").length;
    const draft = orders.filter((o) => o.status === "draft").length;
    const totalRevenue = orders
      .filter((o) => o.status === "confirmed" || o.status === "delivered")
      .reduce((sum, o) => sum + (o.total_amount || 0), 0);
    return { total, confirmed, delivered, draft, totalRevenue };
  }, [orders]);

  const handleOpenDeliverModal = (order: SalesOrderItem) => {
    setDeliverModalOrder(order);
  };

  const handleConfirmDeliver = async () => {
    if (!deliverModalOrder) return;
    setDeliverLoading(true);
    try {
      const updated = await deliverOrderApi(deliverModalOrder.id);
      toast.success(
        "Xuất kho thành công!",
        `Đơn hàng ${updated.order_number} đã chuyển sang trạng thái Đã xuất kho (Delivered).`,
      );
      setOrders((prev) =>
        prev.map((o) =>
          o.id === deliverModalOrder.id ? { ...o, status: "delivered" } : o,
        ),
      );
      if (selectedOrder?.id === deliverModalOrder.id) {
        setSelectedOrder((prev) =>
          prev ? { ...prev, status: "delivered" } : null,
        );
      }
      setDeliverModalOrder(null);
    } catch (err: any) {
      toast.error("Lỗi khi xuất kho", err.message || "Không thể thực hiện xuất kho");
    } finally {
      setDeliverLoading(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!cancelModalOrder) return;
    setCancelLoading(true);
    try {
      const updated = await cancelSalesOrderApi(
        cancelModalOrder.id,
        cancelReason,
      );
      toast.success(
        "Hủy đơn thành công!",
        `Đơn hàng ${updated.order_number} đã được hủy và hoàn trả tồn kho dự lưu.`,
      );
      setOrders((prev) =>
        prev.map((o) =>
          o.id === cancelModalOrder.id ? { ...o, status: "cancelled" } : o,
        ),
      );
      if (selectedOrder?.id === cancelModalOrder.id) {
        setSelectedOrder((prev) =>
          prev ? { ...prev, status: "cancelled" } : null,
        );
      }
      setCancelModalOrder(null);
      setCancelReason("");
    } catch (err: any) {
      toast.error("Lỗi khi hủy đơn", err.message);
    } finally {
      setCancelLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "delivered":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <Truck className="w-3 h-3 text-emerald-700" />
            Đã xuất kho
          </span>
        );
      case "confirmed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <CheckCircle2 className="w-3 h-3 text-blue-600" />
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
              Danh mục đơn đặt hàng, trạng thái xử lý và chi tiết từng dòng sản
              phẩm thời gian thực
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
            <RefreshCw
              className={`w-3.5 h-3.5 ${loading ? "animate-spin text-blue-600" : "text-slate-500"}`}
            />
            <span>Làm mới</span>
          </button>

          <Link
            href="/approvals"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer"
          >
            <Clock className="w-3.5 h-3.5 text-amber-500" />
            <span>Đơn chờ duyệt</span>
          </Link>

          {canCreate && (
            <button
              type="button"
              onClick={openCreateOrderModal}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Tạo đơn thủ công</span>
            </button>
          )}

          {canCreate && (
            <Link
              href="/copilot"
              className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Tạo đơn bằng AI</span>
            </Link>
          )}
        </div>
      </div>

      {/* 2. Thẻ thống kê nhanh */}
      <div className="px-6 py-3.5 grid grid-cols-2 lg:grid-cols-4 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Package className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">
              Tổng số đơn hàng
            </div>
            <div className="text-base font-bold text-slate-900">
              {metrics.total} đơn
            </div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">
              Đã xác nhận
            </div>
            <div className="text-base font-bold text-blue-600">
              {metrics.confirmed} đơn
            </div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <Truck className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">
              Đã xuất kho
            </div>
            <div className="text-base font-bold text-emerald-600">
              {metrics.delivered} đơn
            </div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center shrink-0">
            <DollarSign className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-medium text-slate-400">
              Doanh số xác nhận
            </div>
            <div className="text-sm font-bold text-slate-900 truncate">
              {formatVND(metrics.totalRevenue)}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Thanh tìm kiếm và bộ lọc trạng thái */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          {["all", "draft", "confirmed", "delivered", "cancelled"].map((st) => {
            const labels: Record<string, string> = {
              all: "Tất cả đơn",
              draft: "Đơn nháp",
              confirmed: "Đã duyệt",
              delivered: "Đã xuất kho",
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
          <button
            onClick={() => setErrorMsg(null)}
            className="text-rose-500 hover:text-rose-700"
          >
            ✕
          </button>
        </div>
      )}

      {/* 5. Nội dung Bảng Đơn hàng (Cuộn mượt mà) */}
      <div className="flex-1 px-6 pb-6 overflow-hidden flex flex-col min-h-0">
        <div className="flex-1 bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col min-h-0">
          <div className="flex-1 overflow-y-auto overflow-x-auto min-h-0">
            <table className="w-full min-w-[850px] text-left border-collapse">
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
                      <td className="py-3.5 px-4">
                        <div className="h-4 bg-slate-200 rounded-md w-28" />
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="h-4 bg-slate-200 rounded-md w-36" />
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="h-4 bg-slate-100 rounded-md w-24" />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="h-4 bg-slate-100 rounded-md w-8 mx-auto" />
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="h-4 bg-slate-200 rounded-md w-24 ml-auto" />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" />
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="h-6 bg-slate-100 rounded-lg w-14 mx-auto" />
                      </td>
                    </tr>
                  ))
                ) : filteredOrders.length === 0 ? (
                  <tr>
                    <td
                      colSpan={7}
                      className="py-12 text-center text-slate-400"
                    >
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <ShoppingCart className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">
                        Không tìm thấy đơn hàng nào
                      </p>
                      <p className="text-[11px] text-slate-400 mt-1">
                        Thử đổi từ khóa tìm kiếm hoặc lọc trạng thái khác
                      </p>
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
                        <td className="py-3.5 px-4 font-bold text-blue-600">
                          <div className="flex items-center gap-1.5">
                            <FileText className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                            <span>{order.order_number}</span>
                          </div>
                          {order.customer_po_number && (
                            <div className="text-[10.5px] font-mono text-slate-500 font-normal mt-0.5">
                              PO: <span className="font-semibold text-slate-700">{order.customer_po_number}</span>
                            </div>
                          )}
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
                          <div className="flex items-center justify-center gap-1.5">
                            {order.status === "draft" && canCreate && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openEditOrderModal(order);
                                }}
                                className="inline-flex items-center gap-1 text-[11px] bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200/80 px-2 py-1 rounded-lg transition-colors font-semibold"
                                title="Chỉnh sửa đơn hàng nháp"
                              >
                                <Edit2 className="w-3 h-3 text-amber-600" />
                                <span>Sửa</span>
                              </button>
                            )}
                            {order.status === "draft" && canCreate && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setDeleteModalOrder(order);
                                }}
                                className="inline-flex items-center gap-1 text-[11px] bg-slate-50 hover:bg-rose-50 text-slate-500 hover:text-rose-600 border border-slate-200/80 px-2 py-1 rounded-lg transition-colors font-semibold"
                                title="Xóa hẳn đơn hàng nháp"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            )}
                            {order.status === "confirmed" && canDeliver && (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleOpenDeliverModal(order);
                                }}
                                disabled={deliverLoading}
                                className="inline-flex items-center gap-1 text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white px-2.5 py-1 rounded-lg transition-all font-semibold shadow-2xs active:scale-95 disabled:opacity-50 cursor-pointer"
                                title="Đóng gói và xuất hàng khỏi kho"
                              >
                                <Truck className="w-3 h-3" />
                                <span>Xuất kho</span>
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPreviewPdfOrder({
                                  orderId: order.id,
                                  orderNumber: order.order_number,
                                });
                              }}
                              className="inline-flex items-center gap-1 text-[11px] bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200/80 px-2 py-1 rounded-lg transition-colors font-semibold cursor-pointer"
                              title="In / Xem trước Phiếu Xác Nhận Đơn Hàng PDF"
                            >
                              <Printer className="w-3 h-3 text-blue-600" />
                              <span className="hidden sm:inline">Xác nhận</span>
                            </button>
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
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500 shrink-0">
            <span>
              Hiển thị {filteredOrders.length} / {orders.length} đơn hàng
            </span>
            <span>ERP AI Copilot Sales Order Service</span>
          </div>
        </div>
      </div>

      {/* 6. Chi tiết đơn hàng (Slide-over Overlay Drawer toàn màn hình dọc) */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30 backdrop-blur-2xs animate-in fade-in duration-200">
          {/* Backdrop click outside to close */}
          <div
            className="flex-1 cursor-pointer"
            onClick={() => setSelectedOrder(null)}
          />

          <div className="w-full sm:w-[520px] h-full bg-white shadow-2xl flex flex-col overflow-hidden border-l border-slate-200 animate-in slide-in-from-right duration-250">
            {/* Header */}
            <div className="p-4 px-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/90 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                  <FileText className="w-4 h-4" />
                </div>
                <div>
                  <span className="font-bold text-sm text-slate-900 block leading-tight">
                    {selectedOrder.order_number}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Chi tiết đơn hàng bán
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
                title="Đóng (Esc)"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Nội dung chi tiết cuộn độc lập full height */}
            <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-4">
              {/* Thông tin chung */}
              <div className="p-4 bg-[#F8FAFC] rounded-2xl border border-slate-200/80 space-y-2.5 text-xs">
                <div className="flex justify-between items-center">
                  <span className="text-slate-400 font-medium">Trạng thái:</span>
                  <div>{getStatusBadge(selectedOrder.status)}</div>
                </div>
                <div className="flex justify-between items-start gap-2">
                  <span className="text-slate-400 font-medium shrink-0">Khách hàng:</span>
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
                {selectedOrder.customer_po_number && (
                  <div className="flex justify-between items-center bg-blue-50/60 p-2 rounded-xl border border-blue-100">
                    <span className="text-blue-700 font-semibold flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-blue-600" />
                      <span>Số PO đối tác:</span>
                    </span>
                    <span className="font-mono font-bold text-blue-900 bg-white px-2 py-0.5 rounded-md border border-blue-200">
                      {selectedOrder.customer_po_number}
                    </span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-slate-400 font-medium">Ngày tạo:</span>
                  <span className="text-slate-600 font-medium">
                    {selectedOrder.created_at
                      ? new Date(selectedOrder.created_at).toLocaleString("vi-VN")
                      : "—"}
                  </span>
                </div>
                <div className="flex justify-between items-center border-t border-slate-200/70 pt-2.5 font-bold">
                  <span className="text-slate-700">Tổng thanh toán:</span>
                  <span className="text-blue-600 text-base">
                    {formatVND(selectedOrder.total_amount)}
                  </span>
                </div>
              </div>

              {/* Thẻ Hạn mức công nợ khách hàng (Credit Limit Check) */}
              {creditLoading ? (
                <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-xs text-slate-400 flex items-center justify-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
                  <span>Đang thẩm định công nợ khách hàng...</span>
                </div>
              ) : creditInfo ? (
                <div
                  className={`p-3.5 rounded-xl border text-xs space-y-2 transition-all ${
                    creditInfo.is_exceeded
                      ? "bg-rose-50/90 border-rose-300 text-rose-900"
                      : creditInfo.credit_utilization_rate >= 80
                        ? "bg-amber-50/90 border-amber-300 text-amber-900"
                        : "bg-blue-50/70 border-blue-200 text-blue-900"
                  }`}
                >
                  <div className="flex items-center justify-between font-bold">
                    <span className="flex items-center gap-1.5">
                      <CreditCard className="w-3.5 h-3.5 shrink-0" />
                      <span>Hạn mức công nợ khách hàng</span>
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                        creditInfo.is_exceeded
                          ? "bg-rose-200 text-rose-800"
                          : creditInfo.credit_utilization_rate >= 80
                            ? "bg-amber-200 text-amber-800"
                            : "bg-blue-200 text-blue-800"
                      }`}
                    >
                      {creditInfo.credit_utilization_rate}% Đã dùng
                    </span>
                  </div>

                  <div className="space-y-1 pt-1 text-[11px]">
                    <div className="flex justify-between">
                      <span className="opacity-75">Hạn mức cho phép:</span>
                      <span className="font-semibold">
                        {formatVND(creditInfo.credit_limit)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="opacity-75">Dư nợ hiện tại:</span>
                      <span className="font-bold">
                        {formatVND(creditInfo.current_debt)}
                      </span>
                    </div>
                    <div className="flex justify-between border-t border-current/15 pt-1">
                      <span className="opacity-75">Khả dụng còn lại:</span>
                      <span
                        className={`font-bold ${creditInfo.is_exceeded ? "text-rose-700" : "text-emerald-700"}`}
                      >
                        {formatVND(creditInfo.available_credit)}
                      </span>
                    </div>
                  </div>

                  {creditInfo.is_exceeded && (
                    <div className="flex items-center gap-1.5 text-[10.5px] font-bold text-rose-700 pt-1 border-t border-rose-200">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                      <span>Cảnh báo: Khách hàng đã vượt hạn mức tín dụng!</span>
                    </div>
                  )}
                </div>
              ) : null}

              {/* Danh sách vật tư / sản phẩm */}
              <div className="space-y-2.5">
                <div className="text-xs font-bold text-slate-800 flex items-center justify-between">
                  <span>
                    Mặt hàng đặt mua ({selectedOrder.items?.length || 0})
                  </span>
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                </div>

                {detailLoading ? (
                  <div className="py-8 text-center text-xs text-slate-400">
                    Đang tải chi tiết vật tư...
                  </div>
                ) : !selectedOrder.items || selectedOrder.items.length === 0 ? (
                  <div className="p-4 bg-slate-50 rounded-xl text-center text-xs text-slate-400">
                    Không có dòng sản phẩm nào trong đơn hàng này
                  </div>
                ) : (
                  <div className="space-y-2">
                    {selectedOrder.items.map((item, idx) => {
                      const hasPriceDiff =
                        item.catalog_price !== undefined &&
                        item.catalog_price !== null &&
                        Number(item.catalog_price) > 0 &&
                        Number(item.catalog_price) !== Number(item.unit_price);
                      const isBackordered =
                        item.backorder_quantity !== undefined &&
                        item.backorder_quantity !== null &&
                        Number(item.backorder_quantity) > 0;

                      return (
                        <div
                          key={item.id || idx}
                          className="p-3.5 bg-white border border-slate-200/90 rounded-xl space-y-2 shadow-2xs"
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
                            <span>
                              Mã:{" "}
                              <code className="text-slate-700 font-mono font-medium">
                                {item.sku}
                              </code>
                            </span>
                            <span>
                              SL đặt: <strong>{item.quantity}</strong> ×{" "}
                              {formatVND(item.unit_price)}
                            </span>
                          </div>

                          {/* So sánh giá thỏa thuận vs niêm yết (Phase 2) */}
                          {hasPriceDiff && (
                            <div className="flex items-center justify-between text-[10.5px] bg-amber-50/80 px-2.5 py-1 rounded-lg border border-amber-200/70 text-amber-900">
                              <span className="flex items-center gap-1 font-medium">
                                <AlertTriangle className="w-3 h-3 text-amber-600" />
                                <span>Giá niêm yết ERP:</span>
                              </span>
                              <span>
                                <span className="line-through text-slate-400 mr-1.5">
                                  {formatVND(item.catalog_price || 0)}
                                </span>
                                <strong className="text-amber-800">
                                  Đã áp dụng giá PO (
                                  {Number(item.unit_price) < Number(item.catalog_price)
                                    ? `-${Math.round(
                                        ((Number(item.catalog_price) - Number(item.unit_price)) /
                                          Number(item.catalog_price)) *
                                          100,
                                      )}%`
                                    : `+${Math.round(
                                        ((Number(item.unit_price) - Number(item.catalog_price)) /
                                          Number(item.catalog_price)) *
                                          100,
                                      )}%`}
                                  )
                                </strong>
                              </span>
                            </div>
                          )}

                          {/* Tình trạng phân bổ kho & Chờ giao Backorder (Phase 3) */}
                          {item.allocated_quantity !== undefined && (
                            <div className="flex items-center justify-between text-[10.5px] pt-1 border-t border-slate-100">
                              <span className="text-emerald-700 font-medium">
                                Sẵn sàng xuất:{" "}
                                <strong>{item.allocated_quantity}</strong>
                              </span>
                              {isBackordered ? (
                                <span className="inline-flex items-center gap-1 text-amber-700 font-bold bg-amber-100/80 px-2 py-0.5 rounded-md border border-amber-300">
                                  <Clock className="w-3 h-3 text-amber-600" />
                                  Chờ giao (Backorder): {item.backorder_quantity}
                                </span>
                              ) : (
                                <span className="text-slate-400 text-[10px]">
                                  Đủ tồn kho 100%
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Footer hành động tinh gọn & tiện lợi */}
            <div className="p-4 px-6 border-t border-slate-100 bg-slate-50/90 shrink-0 space-y-2.5">
              {/* Hành động chính theo trạng thái */}
              {selectedOrder.status === "confirmed" && canDeliver && (
                <button
                  type="button"
                  onClick={() => handleOpenDeliverModal(selectedOrder)}
                  disabled={deliverLoading}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer active:scale-95 disabled:opacity-50"
                >
                  {deliverLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Truck className="w-4 h-4" />
                  )}
                  <span>Xác nhận đóng gói & Xuất kho</span>
                </button>
              )}

              {selectedOrder.status === "delivered" && (
                <div className="w-full py-2 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 border border-emerald-200">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Đơn hàng đã xuất kho hoàn tất</span>
                </div>
              )}

              {selectedOrder.status === "cancelled" && (
                <div className="w-full py-2 bg-slate-100 text-slate-600 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 border border-slate-200">
                  <XCircle className="w-3.5 h-3.5 text-slate-500" />
                  <span>Đơn hàng đã bị hủy</span>
                </div>
              )}

              {/* Sửa / Xóa đơn nháp */}
              {selectedOrder.status === "draft" && canCreate && (
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => openEditOrderModal(selectedOrder)}
                    className="py-2 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                    <span>Sửa đơn nháp</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteModalOrder(selectedOrder)}
                    className="py-2 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Xóa đơn nháp</span>
                  </button>
                </div>
              )}

              {/* Hàng nút phụ: Thu tiền - In Phiếu xác nhận PDF - Hỏi AI */}
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() =>
                    setPreviewPdfOrder({
                      orderId: selectedOrder.id,
                      orderNumber: selectedOrder.order_number,
                    })
                  }
                  className="py-2 bg-white hover:bg-blue-50 text-slate-800 hover:text-blue-700 border border-slate-200/90 hover:border-blue-200 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-2xs"
                  title="In / Xem trước Phiếu Xác Nhận Đơn Hàng PDF"
                >
                  <Printer className="w-3.5 h-3.5 text-blue-600" />
                  <span>Phiếu xác nhận (PDF)</span>
                </button>

                {canPayment && selectedOrder.status !== "cancelled" ? (
                  <button
                    type="button"
                    onClick={() => {
                      setPaymentModalOrder(selectedOrder);
                      setPaymentAmount(Number(selectedOrder.total_amount) || 0);
                      setPaymentMethod("bank_transfer");
                      setPaymentRefCode("");
                      setPaymentNote(
                        `Thu tiền thanh toán cho đơn hàng ${selectedOrder.order_number}`,
                      );
                    }}
                    className="py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-1.5 cursor-pointer active:scale-95"
                  >
                    <CreditCard className="w-3.5 h-3.5" />
                    <span>Thu tiền</span>
                  </button>
                ) : (
                  <Link
                    href={`/copilot?q=Kiểm tra chi tiết đơn hàng ${selectedOrder.order_number}`}
                    className="py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Hỏi AI</span>
                  </Link>
                )}
              </div>

              {/* Hàng bổ sung khi có Thu tiền: Hỏi AI + Hủy đơn */}
              <div className="flex items-center gap-2">
                {canPayment && selectedOrder.status !== "cancelled" && (
                  <Link
                    href={`/copilot?q=Kiểm tra chi tiết đơn hàng ${selectedOrder.order_number}`}
                    className="flex-1 py-2 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Hỏi AI về đơn này</span>
                  </Link>
                )}

                {canCancel &&
                  selectedOrder.status !== "delivered" &&
                  selectedOrder.status !== "cancelled" && (
                    <button
                      type="button"
                      onClick={() => {
                        setCancelModalOrder(selectedOrder);
                        setCancelReason("");
                      }}
                      className="px-3 py-2 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200/90 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1 cursor-pointer shadow-2xs"
                      title="Hủy đơn hàng"
                    >
                      <Ban className="w-3.5 h-3.5 text-rose-600" />
                      <span>Hủy</span>
                    </button>
                  )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PDF Quotation Preview Modal */}
      <PdfPreviewModal
        isOpen={!!previewPdfOrder}
        onClose={() => setPreviewPdfOrder(null)}
        orderId={previewPdfOrder?.orderId}
        orderNumber={previewPdfOrder?.orderNumber}
      />

      {/* Modal xác nhận Hủy đơn hàng */}
      {cancelModalOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white w-full max-w-md rounded-2xl border border-slate-200 shadow-2xl p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
                <Ban className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Xác nhận Hủy Đơn Hàng
                </h3>
                <p className="text-xs text-slate-500 font-mono">
                  #{cancelModalOrder.order_number}
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed bg-amber-50 p-3 rounded-xl border border-amber-200 text-amber-900">
              ⚠️ Hệ thống sẽ chuyển trạng thái đơn hàng sang{" "}
              <strong>Đã hủy (Cancelled)</strong> và{" "}
              <strong>
                tự động hoàn trả toàn bộ số lượng tồn kho dự lưu (Reserved)
              </strong>{" "}
              về lại kho khả dụng.
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Lý do hủy đơn hàng:
              </label>
              <textarea
                rows={3}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="VD: Khách hàng đổi ý, hết ngân sách, hủy thỏa thuận..."
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCancelModalOrder(null)}
                className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Giữ lại đơn
              </button>
              <button
                type="button"
                disabled={cancelLoading}
                onClick={handleConfirmCancel}
                className="flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer disabled:opacity-50"
              >
                {cancelLoading && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Xác nhận Hủy đơn</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 8. Modal Thu tiền đơn hàng & Cấn trừ nợ */}
      {paymentModalOrder && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <CreditCard className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900">
                    Thu tiền bán hàng
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Đơn hàng: {paymentModalOrder.order_number}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setPaymentModalOrder(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handlePaymentSubmit} className="space-y-3.5">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-500">Khách hàng:</span>
                  <span className="font-semibold text-slate-800">
                    {getCustomerInfo(paymentModalOrder).name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Tổng tiền đơn hàng:</span>
                  <span className="font-bold text-blue-600">
                    {formatVND(paymentModalOrder.total_amount)}
                  </span>
                </div>
                {creditInfo && (
                  <div className="flex justify-between border-t border-slate-200/60 pt-1.5">
                    <span className="text-slate-500">Dư nợ hiện tại:</span>
                    <span className="font-semibold text-amber-700">
                      {formatVND(creditInfo.current_debt)}
                    </span>
                  </div>
                )}
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Số tiền thu (VND) <span className="text-rose-500">*</span>
                </label>
                <input
                  type="number"
                  min={1000}
                  step={1000}
                  required
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm font-semibold border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Phương thức thanh toán
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 bg-white"
                >
                  <option value="bank_transfer">
                    Chuyển khoản ngân hàng (Bank Transfer)
                  </option>
                  <option value="cash">Tiền mặt tại quầy (Cash)</option>
                  <option value="credit_card">
                    Thẻ tín dụng / POS (Credit Card)
                  </option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Mã tham chiếu / Số hóa đơn ngân hàng
                </label>
                <input
                  type="text"
                  placeholder="VD: FT261017888999, VCB-098877..."
                  value={paymentRefCode}
                  onChange={(e) => setPaymentRefCode(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">
                  Ghi chú thu tiền
                </label>
                <textarea
                  rows={2}
                  placeholder="Nhập ghi chú hoặc lý do cấn trừ..."
                  value={paymentNote}
                  onChange={(e) => setPaymentNote(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setPaymentModalOrder(null)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={paymentSubmitting}
                  className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer disabled:opacity-50 active:scale-95 transition-all"
                >
                  {paymentSubmitting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CreditCard className="w-3.5 h-3.5" />
                  )}
                  <span>Xác nhận Thu tiền & Cấn trừ nợ</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 9. Modal Tạo mới / Chỉnh sửa đơn hàng nháp */}
      {isOrderFormOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <ShoppingCart className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900">
                    {editingOrderId
                      ? "Chỉnh sửa đơn hàng nháp"
                      : "Tạo đơn hàng bán mới (Thủ công)"}
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    {editingOrderId
                      ? "Cập nhật sản phẩm và thông tin đơn hàng nháp"
                      : "Nhập thông tin khách hàng và danh sách mặt hàng đặt mua"}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOrderFormOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form
              onSubmit={handleOrderFormSubmit}
              className="flex-1 overflow-y-auto space-y-4 pr-1 text-xs"
            >
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Khách hàng */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">
                    Khách hàng đặt mua:
                  </label>
                  <select
                    value={formCustomerCode}
                    onChange={(e) => setFormCustomerCode(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  >
                    <option value="">-- Chọn khách hàng --</option>
                    {Object.values(customerMap).map((c) => (
                      <option key={c.code} value={c.code}>
                        {c.code} - {c.name}{" "}
                        {c.status === "inactive" ? "(Ngừng hoạt động)" : ""}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">
                    Số đơn đặt hàng của khách (PO Number):
                  </label>
                  <input
                    type="text"
                    value={formCustomerPoNumber}
                    onChange={(e) => setFormCustomerPoNumber(e.target.value)}
                    placeholder="VD: PO-2026-HUE-001 (tùy chọn)"
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                  />
                </div>
              </div>

              {/* Danh sách mặt hàng */}
              <div className="space-y-2">
                <div className="flex items-center justify-between font-semibold text-slate-700">
                  <span>Danh sách sản phẩm / SKU:</span>
                  <button
                    type="button"
                    onClick={() => {
                      const firstSku = productsList[0]?.sku || "";
                      setFormItems([
                        ...formItems,
                        { sku: firstSku, quantity: 1 },
                      ]);
                    }}
                    className="inline-flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-700 font-bold cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>+ Thêm dòng</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {formItems.map((item, idx) => {
                    const matchedProduct = productMap[item.sku];
                    const unitPrice = matchedProduct
                      ? Number(matchedProduct.unit_price)
                      : 0;
                    const lineTotal = (Number(item.quantity) || 0) * unitPrice;

                    return (
                      <div
                        key={idx}
                        className="p-3 bg-slate-50/80 rounded-2xl border border-slate-200 grid grid-cols-12 gap-2 items-center"
                      >
                        <div className="col-span-6 space-y-1">
                          <label className="text-[10px] text-slate-500 font-medium">
                            Sản phẩm (SKU):
                          </label>
                          <select
                            value={item.sku}
                            onChange={(e) => {
                              const newItems = [...formItems];
                              newItems[idx].sku = e.target.value;
                              setFormItems(newItems);
                            }}
                            className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs"
                          >
                            <option value="">-- Chọn SKU --</option>
                            {productsList.map((p) => (
                              <option key={p.sku} value={p.sku}>
                                {p.sku} - {p.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="col-span-2 space-y-1">
                          <label className="text-[10px] text-slate-500 font-medium">
                            Số lượng:
                          </label>
                          <input
                            type="number"
                            min={1}
                            value={item.quantity}
                            onChange={(e) => {
                              const newItems = [...formItems];
                              newItems[idx].quantity =
                                parseInt(e.target.value, 10) || 1;
                              setFormItems(newItems);
                            }}
                            className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-center font-bold text-slate-900"
                          />
                        </div>

                        <div className="col-span-3 space-y-1 text-right">
                          <label className="text-[10px] text-slate-500 font-medium">
                            Thành tiền:
                          </label>
                          <div className="font-bold text-blue-600 text-xs pt-1">
                            {formatVND(lineTotal)}
                          </div>
                          <div className="text-[10px] text-slate-400">
                            {formatVND(unitPrice)}/sp
                          </div>
                        </div>

                        <div className="col-span-1 flex justify-center pt-3">
                          {formItems.length > 1 && (
                            <button
                              type="button"
                              onClick={() => {
                                setFormItems(
                                  formItems.filter((_, i) => i !== idx),
                                );
                              }}
                              className="p-1 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                              title="Xóa dòng này"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Tổng cộng & Ngày giao dự kiến */}
              <div className="p-3 bg-emerald-50/60 rounded-2xl border border-emerald-200 flex items-center justify-between">
                <div>
                  <span className="text-slate-600 font-medium">
                    Tổng giá trị đơn hàng (Tạm tính):
                  </span>
                  <div className="text-lg font-bold text-emerald-700">
                    {formatVND(formTotalAmount)}
                  </div>
                </div>
                <div className="text-right text-[11px] text-slate-500">
                  Giá bán snapshot tự động từ bảng giá ERP
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsOrderFormOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting || formItems.length === 0}
                  className="flex items-center gap-1.5 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer disabled:opacity-50 active:scale-95 transition-all"
                >
                  {formSubmitting && (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  )}
                  <span>
                    {editingOrderId
                      ? "Lưu thay đổi đơn hàng"
                      : "Tạo đơn hàng nháp"}
                  </span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 10. Modal Xác nhận Xóa đơn hàng nháp */}
      {deleteModalOrder && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="font-bold text-base text-slate-900">
                Xóa đơn hàng nháp?
              </h3>
              <p className="text-xs text-slate-500">
                Bạn có chắc chắn muốn xóa vĩnh viễn đơn hàng{" "}
                <strong>{deleteModalOrder.order_number}</strong>? Hành động này
                sẽ được ghi nhận vào nhật ký kiểm toán AuditLog.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setDeleteModalOrder(null)}
                className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Giữ lại
              </button>
              <button
                type="button"
                disabled={deleteLoading}
                onClick={handleConfirmDeleteDraft}
                className="flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer disabled:opacity-50"
              >
                {deleteLoading && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Xác nhận Xóa đơn</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 11. Modal Xác nhận Xuất kho Đóng gói (Thay thế alert/confirm native) */}
      {deliverModalOrder && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                <Truck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Xác nhận Đóng gói & Xuất kho
                </h3>
                <p className="text-xs text-slate-500 font-mono">
                  #{deliverModalOrder.order_number}
                </p>
              </div>
            </div>

            <div className="bg-emerald-50/70 p-3.5 rounded-xl border border-emerald-200/80 text-xs text-emerald-900 space-y-2">
              <div className="flex items-center gap-2 font-bold text-emerald-800">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                <span>Thao tác trừ kho vật lý tự động</span>
              </div>
              <p className="leading-relaxed opacity-90">
                Hệ thống sẽ chuyển trạng thái đơn hàng sang{" "}
                <strong>Đã xuất kho (Delivered)</strong>, tự động trừ số lượng
                hàng sẵn sàng trong kho thực tế và lưu vết vào AuditLog.
              </p>
            </div>

            <div className="text-xs text-slate-500 flex justify-between border-t border-slate-100 pt-3">
              <span>Khách hàng nhận:</span>
              <strong className="text-slate-800">
                {getCustomerInfo(deliverModalOrder).name}
              </strong>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setDeliverModalOrder(null)}
                className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                disabled={deliverLoading}
                onClick={handleConfirmDeliver}
                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-xs cursor-pointer disabled:opacity-50 active:scale-95 transition-all"
              >
                {deliverLoading && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Xác nhận Xuất kho</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

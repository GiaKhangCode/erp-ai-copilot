"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  ShoppingBag, 
  Search, 
  RefreshCw, 
  FileText, 
  Plus, 
  Truck, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Package, 
  Building2, 
  ChevronRight, 
  X, 
  Loader2, 
  DollarSign, 
  AlertTriangle, 
  Ban, 
  Warehouse,
  Sparkles,
  Layers,
  Trash2
} from "lucide-react";
import { 
  fetchPurchaseOrders, 
  fetchSuppliers, 
  fetchProducts, 
  createPurchaseOrderApi, 
  receivePurchaseOrderApi, 
  cancelPurchaseOrderApi, 
  createSupplierApi, 
  PurchaseOrderItem, 
  SupplierItem, 
  ProductItem 
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/toast-provider";

export default function PurchasingPage() {
  const toast = useToast();
  const { hasPermission, isAdmin } = useAuth();
  const canRead = isAdmin || hasPermission("purchasing:read");
  const canCreate = isAdmin || hasPermission("purchasing:create");
  const canReceive = isAdmin || hasPermission("purchasing:receive");
  const canCancel = isAdmin || hasPermission("purchasing:cancel");

  const [activeTab, setActiveTab] = useState<"orders" | "suppliers">("orders");
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrderItem[]>([]);
  const [suppliers, setSuppliers] = useState<SupplierItem[]>([]);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedPO, setSelectedPO] = useState<PurchaseOrderItem | null>(null);

  // Modal Tạo PO
  const [isCreatePOModalOpen, setIsCreatePOModalOpen] = useState(false);
  const [poSupplierCode, setPoSupplierCode] = useState("");
  const [poWarehouseCode, setPoWarehouseCode] = useState("WH-HN");
  const [poItems, setPoItems] = useState<Array<{ sku: string; quantity: number; unit_price: number }>>([
    { sku: "", quantity: 1, unit_price: 0 },
  ]);
  const [poNotes, setPoNotes] = useState("");
  const [poSubmitting, setPoSubmitting] = useState(false);
  const [poError, setPoError] = useState<string | null>(null);

  // Modal Tạo Nhà Cung Cấp
  const [isSupplierModalOpen, setIsSupplierModalOpen] = useState(false);
  const [supCode, setSupCode] = useState("");
  const [supName, setSupName] = useState("");
  const [supTax, setSupTax] = useState("");
  const [supEmail, setSupEmail] = useState("");
  const [supPhone, setSupPhone] = useState("");
  const [supAddress, setSupAddress] = useState("");
  const [supSubmitting, setSupSubmitting] = useState(false);
  const [supError, setSupError] = useState<string | null>(null);

  // Receiving state
  const [receivingId, setReceivingId] = useState<string | null>(null);

  // Cancel PO state
  const [cancelPOModalOrder, setCancelPOModalOrder] = useState<PurchaseOrderItem | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelSubmitting, setCancelSubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [pos, sups, prods] = await Promise.all([
        fetchPurchaseOrders({ status: statusFilter === "all" ? undefined : statusFilter }),
        fetchSuppliers(),
        fetchProducts(),
      ]);
      setPurchaseOrders(pos);
      setSuppliers(sups);
      setProducts(prods);
    } catch (err: any) {
      setErrorMsg("Lỗi khi tải dữ liệu mua hàng: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter]);

  // Thống kê metrics
  const metrics = useMemo(() => {
    const total = purchaseOrders.length;
    const received = purchaseOrders.filter((p) => p.status === "received").length;
    const pending = purchaseOrders.filter((p) => p.status === "draft" || p.status === "ordered").length;
    const totalSpent = purchaseOrders
      .filter((p) => p.status === "received")
      .reduce((sum, p) => sum + (Number(p.total_amount) || 0), 0);
    return { total, received, pending, totalSpent };
  }, [purchaseOrders]);

  // Bộ lọc tìm kiếm PO
  const filteredPOs = useMemo(() => {
    return purchaseOrders.filter((po) => {
      if (!searchTerm.trim()) return true;
      const term = searchTerm.toLowerCase();
      const matchNum = po.po_number.toLowerCase().includes(term);
      const matchSup = (po.supplier_name || "").toLowerCase().includes(term) ||
                       (po.supplier_code || "").toLowerCase().includes(term);
      const matchWh = (po.warehouse_name || "").toLowerCase().includes(term) ||
                      (po.warehouse_code || "").toLowerCase().includes(term);
      return matchNum || matchSup || matchWh;
    });
  }, [purchaseOrders, searchTerm]);

  // Bộ lọc tìm kiếm Nhà cung cấp
  const filteredSuppliers = useMemo(() => {
    return suppliers.filter((s) => {
      if (!searchTerm.trim()) return true;
      const term = searchTerm.toLowerCase();
      return (
        s.name.toLowerCase().includes(term) ||
        s.code.toLowerCase().includes(term) ||
        (s.phone && s.phone.includes(term))
      );
    });
  }, [suppliers, searchTerm]);

  // Live total preview cho Modal tạo PO
  const poTotalAmount = useMemo(() => {
    return poItems.reduce((acc, it) => acc + (Number(it.quantity) || 0) * (Number(it.unit_price) || 0), 0);
  }, [poItems]);

  const openCreatePO = () => {
    setPoSupplierCode(suppliers[0]?.code || "");
    setPoWarehouseCode("WH-HN");
    const firstSku = products[0]?.sku || "";
    setPoItems([{ sku: firstSku, quantity: 10, unit_price: 1000000 }]);
    setPoNotes("");
    setPoError(null);
    setIsCreatePOModalOpen(true);
  };

  const handleCreatePOSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPoError(null);

    if (!poSupplierCode) {
      setPoError("Vui lòng chọn nhà cung cấp.");
      return;
    }
    if (poItems.length === 0) {
      setPoError("Đơn mua hàng phải có ít nhất 1 dòng sản phẩm.");
      return;
    }
    for (const it of poItems) {
      if (!it.sku) {
        setPoError("Vui lòng chọn SKU sản phẩm cho mọi dòng.");
        return;
      }
      if (it.quantity <= 0) {
        setPoError(`Số lượng cho SKU ${it.sku} phải lớn hơn 0.`);
        return;
      }
      if (it.unit_price < 0) {
        setPoError(`Đơn giá cho SKU ${it.sku} không được âm.`);
        return;
      }
    }

    setPoSubmitting(true);
    try {
      const res = await createPurchaseOrderApi({
        supplier_code: poSupplierCode,
        warehouse_code: poWarehouseCode,
        items: poItems,
        notes: poNotes.trim() || undefined,
      });
      toast.success("Lập đơn PO thành công!", `Đã tạo đơn mua hàng ${res.po_number} tổng giá trị ${formatVND(res.total_amount)}.`);
      setIsCreatePOModalOpen(false);
      await loadData();
    } catch (err: any) {
      setPoError(err.message || "Lỗi khi tạo đơn mua hàng.");
    } finally {
      setPoSubmitting(false);
    }
  };

  const handleCreateSupplierSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSupError(null);

    if (!supCode.trim() || !supName.trim()) {
      setSupError("Vui lòng nhập Mã và Tên nhà cung cấp.");
      return;
    }

    setSupSubmitting(true);
    try {
      const res = await createSupplierApi({
        code: supCode.trim().toUpperCase(),
        name: supName.trim(),
        tax_code: supTax.trim() || undefined,
        contact_email: supEmail.trim() || undefined,
        phone: supPhone.trim() || undefined,
        address: supAddress.trim() || undefined,
      });
      toast.success("Thêm nhà cung cấp thành công!", `Đã tạo nhà cung cấp [${res.code}] ${res.name}.`);
      setIsSupplierModalOpen(false);
      setSupCode("");
      setSupName("");
      setSupTax("");
      setSupEmail("");
      setSupPhone("");
      setSupAddress("");
      await loadData();
    } catch (err: any) {
      setSupError(err.message || "Lỗi khi thêm nhà cung cấp.");
    } finally {
      setSupSubmitting(false);
    }
  };

  const handleReceivePO = async (po: PurchaseOrderItem) => {
    if (!confirm(`Xác nhận Nhập kho cho đơn mua hàng ${po.po_number}? Tồn kho thực tế tại [${po.warehouse_name}] sẽ được tự động cộng thêm.`)) {
      return;
    }
    setReceivingId(po.id);
    try {
      const updated = await receivePurchaseOrderApi(po.id);
      toast.success("Nhập kho thành công!", `Đơn ${updated.po_number} đã chuyển sang trạng thái Đã nhập kho (Received) và tồn kho đã được cập nhật.`);
      setPurchaseOrders((prev) => prev.map((p) => (p.id === po.id ? updated : p)));
      if (selectedPO?.id === po.id) {
        setSelectedPO(updated);
      }
    } catch (err: any) {
      toast.error("Lỗi khi nhập kho", err.message);
    } finally {
      setReceivingId(null);
    }
  };

  const handleCancelPOSubmit = async () => {
    if (!cancelPOModalOrder) return;
    setCancelSubmitting(true);
    try {
      const updated = await cancelPurchaseOrderApi(cancelPOModalOrder.id, cancelReason);
      toast.success("Hủy đơn PO thành công!", `Đơn ${updated.po_number} đã được chuyển sang trạng thái Đã hủy.`);
      setPurchaseOrders((prev) => prev.map((p) => (p.id === cancelPOModalOrder.id ? updated : p)));
      if (selectedPO?.id === cancelPOModalOrder.id) {
        setSelectedPO(updated);
      }
      setCancelPOModalOrder(null);
      setCancelReason("");
    } catch (err: any) {
      toast.error("Lỗi khi hủy đơn PO", err.message);
    } finally {
      setCancelSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "received":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-700" />
            Đã nhập kho
          </span>
        );
      case "ordered":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <Truck className="w-3 h-3 text-blue-600" />
            Đang vận chuyển
          </span>
        );
      case "draft":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            Đơn nháp
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
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#F8FAFC] overflow-hidden">
      {/* 1. Tiêu đề và Thao tác chính */}
      <div className="px-6 py-4 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 shrink-0 shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-600">
            <ShoppingBag className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 tracking-tight">
              Quản lý Mua hàng & Nhà cung cấp (Purchasing)
            </h1>
            <p className="text-xs text-slate-500">
              Lập đơn mua hàng PO, theo dõi nhà cung cấp và xác nhận nhập kho thực tế
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-amber-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          {canCreate && (
            <button
              type="button"
              onClick={() => setIsSupplierModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer active:scale-95"
            >
              <Building2 className="w-3.5 h-3.5 text-slate-500" />
              <span>+ Thêm NCC</span>
            </button>
          )}

          {canCreate && (
            <button
              type="button"
              onClick={openCreatePO}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>+ Lập đơn mua hàng PO</span>
            </button>
          )}
        </div>
      </div>

      {/* 2. Thẻ chỉ số tổng quan Mua hàng */}
      <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-4 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
            <ShoppingBag className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tổng số đơn mua PO</div>
            <div className="text-base font-bold text-slate-900">{metrics.total} đơn</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Đã nhập kho</div>
            <div className="text-base font-bold text-emerald-600">{metrics.received} đơn</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Chờ nhập kho</div>
            <div className="text-base font-bold text-blue-600">{metrics.pending} đơn</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center shrink-0">
            <DollarSign className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-medium text-slate-400">Tổng giá trị đã nhập</div>
            <div className="text-sm font-bold text-slate-900 truncate">{formatVND(metrics.totalSpent)}</div>
          </div>
        </div>
      </div>

      {/* 3. Chuyển Tab & Thanh tìm kiếm */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="bg-slate-200/70 p-1 rounded-xl flex items-center gap-1">
            <button
              type="button"
              onClick={() => setActiveTab("orders")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "orders" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Đơn mua hàng PO ({purchaseOrders.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("suppliers")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === "suppliers" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Nhà cung cấp ({suppliers.length})
            </button>
          </div>

          {activeTab === "orders" && (
            <div className="flex items-center gap-1.5 ml-2">
              {["all", "draft", "received", "cancelled"].map((st) => {
                const labels: Record<string, string> = {
                  all: "Tất cả",
                  draft: "Đơn nháp",
                  received: "Đã nhập kho",
                  cancelled: "Đã hủy",
                };
                const active = statusFilter === st;
                return (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                      active ? "bg-slate-900 text-white" : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200/80"
                    }`}
                  >
                    {labels[st]}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="relative w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder={activeTab === "orders" ? "Tìm theo mã PO, NCC, kho..." : "Tìm nhà cung cấp theo tên, mã..."}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs placeholder:text-slate-400 focus:outline-hidden focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 transition-all"
          />
        </div>
      </div>

      {/* 4. Thông báo lỗi */}
      {errorMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {/* 5. Nội dung Bảng */}
      <div className="flex-1 px-6 pb-6 overflow-hidden flex flex-col min-h-0">
        {activeTab === "orders" ? (
          <div className="flex-1 bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col min-h-0">
            <div className="flex-1 overflow-y-auto overflow-x-auto min-h-0">
              <table className="w-full min-w-[850px] text-left border-collapse">
                <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="py-3 px-4">Mã đơn PO</th>
                    <th className="py-3 px-4">Nhà cung cấp</th>
                    <th className="py-3 px-4">Kho nhập</th>
                    <th className="py-3 px-4">Ngày tạo</th>
                    <th className="py-3 px-4 text-center">Số mặt hàng</th>
                    <th className="py-3 px-4 text-right">Tổng giá trị</th>
                    <th className="py-3 px-4 text-center">Trạng thái</th>
                    <th className="py-3 px-4 text-center">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {loading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i} className="animate-pulse">
                        <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-24" /></td>
                        <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-36" /></td>
                        <td className="py-3.5 px-4"><div className="h-4 bg-slate-100 rounded-md w-20" /></td>
                        <td className="py-3.5 px-4"><div className="h-4 bg-slate-100 rounded-md w-24" /></td>
                        <td className="py-3.5 px-4 text-center"><div className="h-4 bg-slate-100 rounded-md w-8 mx-auto" /></td>
                        <td className="py-3.5 px-4 text-right"><div className="h-4 bg-slate-200 rounded-md w-24 ml-auto" /></td>
                        <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                        <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-16 mx-auto" /></td>
                      </tr>
                    ))
                  ) : filteredPOs.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-slate-400">
                        <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                          <ShoppingBag className="w-6 h-6" />
                        </div>
                        <p className="font-medium text-slate-600">Không tìm thấy đơn mua hàng nào</p>
                        <p className="text-[11px] text-slate-400 mt-1">Bấm "+ Lập đơn mua hàng PO" để tạo đơn nhập hàng đầu tiên</p>
                      </td>
                    </tr>
                  ) : (
                    filteredPOs.map((po) => {
                      const isSelected = selectedPO?.id === po.id;
                      const dateFormatted = po.created_at
                        ? new Date(po.created_at).toLocaleDateString("vi-VN", {
                            day: "2-digit",
                            month: "2-digit",
                            year: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—";

                      return (
                        <tr
                          key={po.id}
                          onClick={() => setSelectedPO(po)}
                          className={`hover:bg-amber-50/40 transition-colors cursor-pointer ${
                            isSelected ? "bg-amber-50/70 font-medium" : ""
                          }`}
                        >
                          <td className="py-3.5 px-4 font-bold text-amber-700 flex items-center gap-1.5">
                            <FileText className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                            <span>{po.po_number}</span>
                          </td>
                          <td className="py-3.5 px-4">
                            <div className="font-semibold text-slate-900 leading-snug">{po.supplier_name}</div>
                            <div className="text-[11px] font-mono text-slate-500">{po.supplier_code}</div>
                          </td>
                          <td className="py-3.5 px-4 font-medium text-slate-700">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-[11px] font-bold text-slate-700">
                              <Warehouse className="w-3 h-3 text-slate-500" />
                              {po.warehouse_code}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-slate-500">{dateFormatted}</td>
                          <td className="py-3.5 px-4 text-center">
                            <span className="w-6 h-6 inline-flex items-center justify-center rounded-lg bg-slate-100 text-slate-700 text-[11px] font-semibold">
                              {po.items.length}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 text-right font-bold text-slate-900">
                            {formatVND(po.total_amount)}
                          </td>
                          <td className="py-3.5 px-4 text-center">
                            {getStatusBadge(po.status)}
                          </td>
                          <td className="py-3.5 px-4 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              {po.status !== "received" && po.status !== "cancelled" && canReceive && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleReceivePO(po);
                                  }}
                                  disabled={receivingId === po.id}
                                  className="inline-flex items-center gap-1 text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white px-2.5 py-1 rounded-lg transition-all font-semibold shadow-2xs active:scale-95 disabled:opacity-50"
                                  title="Xác nhận hàng về và nhập vào kho vật lý"
                                >
                                  {receivingId === po.id ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <Truck className="w-3 h-3" />
                                  )}
                                  <span>Nhập kho</span>
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedPO(po);
                                }}
                                className="text-xs text-amber-700 hover:text-amber-900 hover:bg-amber-50 px-2 py-1 rounded-lg transition-colors font-semibold"
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

            <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
              <span>Hiển thị {filteredPOs.length} / {purchaseOrders.length} đơn mua hàng</span>
              <span>Nghiệp vụ: Nhập kho tự động tăng On Hand tại kho đích</span>
            </div>
          </div>
        ) : (
          /* Danh sách Nhà cung cấp */
          <div className="flex-1 bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
            <div className="flex-1 overflow-y-auto">
              <table className="w-full text-left border-collapse">
                <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="py-3 px-4">Mã NCC</th>
                    <th className="py-3 px-4">Tên Nhà cung cấp</th>
                    <th className="py-3 px-4">Mã số thuế</th>
                    <th className="py-3 px-4">Email liên hệ</th>
                    <th className="py-3 px-4">Điện thoại</th>
                    <th className="py-3 px-4">Địa chỉ trụ sở</th>
                    <th className="py-3 px-4 text-center">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {filteredSuppliers.map((sup) => (
                    <tr key={sup.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4 font-mono font-bold text-blue-600">{sup.code}</td>
                      <td className="py-3 px-4 font-bold text-slate-900">{sup.name}</td>
                      <td className="py-3 px-4 font-mono text-slate-600">{sup.tax_code || "—"}</td>
                      <td className="py-3 px-4 text-slate-600">{sup.contact_email || "—"}</td>
                      <td className="py-3 px-4 text-slate-600">{sup.phone || "—"}</td>
                      <td className="py-3 px-4 text-slate-600 max-w-xs truncate" title={sup.address || ""}>
                        {sup.address || "—"}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-[10.5px] font-semibold ${
                          sup.status === "active" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-slate-100 text-slate-600"
                        }`}>
                          {sup.status === "active" ? "Đang giao dịch" : "Ngừng giao dịch"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Side Panel Chi tiết PO dạng Slide-over Overlay */}
      {selectedPO && activeTab === "orders" && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30 backdrop-blur-2xs animate-in fade-in duration-200">
          <div
            className="flex-1 cursor-pointer"
            onClick={() => setSelectedPO(null)}
          />

          <div className="w-full sm:w-[520px] h-full bg-white shadow-2xl flex flex-col overflow-hidden border-l border-slate-200 animate-in slide-in-from-right duration-250">
            <div className="p-4 px-6 border-b border-slate-100 bg-slate-50/90 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                  <ShoppingBag className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900">{selectedPO.po_number}</h3>
                  <p className="text-[11px] text-slate-500">{selectedPO.supplier_name}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPO(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
                title="Đóng (Esc)"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-4 text-xs">
              {/* Trạng thái & Kho */}
              <div className="p-4 bg-slate-50 rounded-2xl space-y-2.5 border border-slate-200/80">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Trạng thái đơn:</span>
                  {getStatusBadge(selectedPO.status)}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Kho nhận hàng:</span>
                  <span className="font-bold text-slate-800">{selectedPO.warehouse_name} ({selectedPO.warehouse_code})</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Người tạo đơn:</span>
                  <span className="font-medium text-slate-700">{selectedPO.creator_name || "Hệ thống"}</span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-slate-200 text-sm font-bold">
                  <span className="text-slate-700">Tổng giá trị PO:</span>
                  <span className="text-amber-700 text-base">{formatVND(selectedPO.total_amount)}</span>
                </div>
              </div>

              {/* Danh sách mặt hàng */}
              <div className="space-y-2.5">
                <div className="text-xs font-bold text-slate-800 flex items-center justify-between">
                  <span>Mặt hàng đặt mua ({selectedPO.items.length})</span>
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                </div>
                <div className="space-y-2">
                  {selectedPO.items.map((it, idx) => (
                    <div key={idx} className="p-3.5 bg-white border border-slate-200/90 rounded-xl space-y-1.5 shadow-2xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-slate-800">{it.product_name}</span>
                        <span className="text-[11px] font-bold text-amber-700">{formatVND(it.line_total)}</span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-slate-500">
                        <span>Mã SKU: <code className="font-mono font-bold text-slate-700">{it.sku}</code></span>
                        <span>SL: <strong>{it.quantity}</strong> × {formatVND(it.unit_price)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {selectedPO.notes && (
                <div className="p-3.5 bg-amber-50/60 rounded-xl border border-amber-200/80 text-[11px] text-amber-900">
                  <span className="font-bold block mb-1">Ghi chú đơn hàng:</span>
                  {selectedPO.notes}
                </div>
              )}
            </div>

            {/* Actions footer */}
            <div className="p-4 px-6 border-t border-slate-100 bg-slate-50/90 shrink-0 space-y-2.5">
              {selectedPO.status !== "received" && selectedPO.status !== "cancelled" && canReceive && (
                <button
                  type="button"
                  onClick={() => handleReceivePO(selectedPO)}
                  disabled={receivingId === selectedPO.id}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer active:scale-95 disabled:opacity-50"
                >
                  {receivingId === selectedPO.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Truck className="w-4 h-4" />
                  )}
                  <span>Xác nhận Nhập kho PO này</span>
                </button>
              )}

              {selectedPO.status === "received" && (
                <div className="w-full py-2 bg-emerald-50 text-emerald-800 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 border border-emerald-200">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Đơn mua hàng đã nhập kho hoàn tất</span>
                </div>
              )}

              {selectedPO.status !== "received" && selectedPO.status !== "cancelled" && canCancel && (
                <button
                  type="button"
                  onClick={() => {
                    setCancelPOModalOrder(selectedPO);
                    setCancelReason("");
                  }}
                  className="w-full py-2 bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 rounded-xl text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-2xs"
                >
                  <Ban className="w-3.5 h-3.5 text-rose-600" />
                  <span>Hủy đơn mua hàng này</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 1: TẠO ĐƠN MUA HÀNG PO */}
      {isCreatePOModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-2xl w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
                  <ShoppingBag className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900">Lập đơn mua hàng (Purchase Order)</h3>
                  <p className="text-[11px] text-slate-500">Đặt hàng từ nhà cung cấp và chỉ định kho lưu giữ</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsCreatePOModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreatePOSubmit} className="flex-1 overflow-y-auto space-y-4 pr-1 text-xs">
              {poError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <span>{poError}</span>
                </div>
              )}

              {/* Nhà cung cấp & Kho nhập */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Nhà cung cấp:</label>
                  <select
                    value={poSupplierCode}
                    onChange={(e) => setPoSupplierCode(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                  >
                    <option value="">-- Chọn Nhà cung cấp --</option>
                    {suppliers.map((s) => (
                      <option key={s.code} value={s.code}>
                        {s.code} - {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="font-semibold text-slate-700">Kho tiếp nhận nhập hàng:</label>
                  <select
                    value={poWarehouseCode}
                    onChange={(e) => setPoWarehouseCode(e.target.value)}
                    className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                  >
                    <option value="WH-HN">WH-HN - Kho Tổng Hà Nội</option>
                    <option value="WH-HCM">WH-HCM - Kho Chi nhánh TP.HCM</option>
                  </select>
                </div>
              </div>

              {/* Danh sách mặt hàng đặt mua */}
              <div className="space-y-2">
                <div className="flex items-center justify-between font-semibold text-slate-700">
                  <span>Mặt hàng đặt mua:</span>
                  <button
                    type="button"
                    onClick={() => {
                      const firstSku = products[0]?.sku || "";
                      setPoItems([...poItems, { sku: firstSku, quantity: 10, unit_price: 1000000 }]);
                    }}
                    className="inline-flex items-center gap-1 text-[11px] text-amber-600 hover:text-amber-700 font-bold cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>+ Thêm dòng</span>
                  </button>
                </div>

                <div className="space-y-2">
                  {poItems.map((item, idx) => {
                    const lineTotal = (Number(item.quantity) || 0) * (Number(item.unit_price) || 0);

                    return (
                      <div key={idx} className="p-3 bg-slate-50/80 rounded-2xl border border-slate-200 grid grid-cols-12 gap-2 items-center">
                        <div className="col-span-5 space-y-1">
                          <label className="text-[10px] text-slate-500 font-medium">Sản phẩm (SKU):</label>
                          <select
                            value={item.sku}
                            onChange={(e) => {
                              const newItems = [...poItems];
                              newItems[idx].sku = e.target.value;
                              setPoItems(newItems);
                            }}
                            className="w-full px-2.5 py-1.5 bg-white border border-slate-200 rounded-lg text-xs"
                          >
                            <option value="">-- Chọn SKU --</option>
                            {products.map((p) => (
                              <option key={p.sku} value={p.sku}>
                                {p.sku} - {p.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div className="col-span-2 space-y-1">
                          <label className="text-[10px] text-slate-500 font-medium">Số lượng:</label>
                          <input
                            type="number"
                            min={1}
                            value={item.quantity}
                            onChange={(e) => {
                              const newItems = [...poItems];
                              newItems[idx].quantity = parseInt(e.target.value, 10) || 1;
                              setPoItems(newItems);
                            }}
                            className="w-full px-2 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-center font-bold text-slate-900"
                          />
                        </div>

                        <div className="col-span-2 space-y-1">
                          <label className="text-[10px] text-slate-500 font-medium">Đơn giá nhập:</label>
                          <input
                            type="number"
                            min={0}
                            value={item.unit_price}
                            onChange={(e) => {
                              const newItems = [...poItems];
                              newItems[idx].unit_price = parseFloat(e.target.value) || 0;
                              setPoItems(newItems);
                            }}
                            className="w-full px-2 py-1.5 bg-white border border-slate-200 rounded-lg text-xs text-right font-medium text-slate-900"
                          />
                        </div>

                        <div className="col-span-2 space-y-1 text-right">
                          <label className="text-[10px] text-slate-500 font-medium">Thành tiền:</label>
                          <div className="font-bold text-amber-700 text-xs pt-1.5">
                            {formatVND(lineTotal)}
                          </div>
                        </div>

                        <div className="col-span-1 flex justify-center pt-3">
                          {poItems.length > 1 && (
                            <button
                              type="button"
                              onClick={() => {
                                setPoItems(poItems.filter((_, i) => i !== idx));
                              }}
                              className="p-1 text-slate-400 hover:text-rose-600 transition-colors cursor-pointer"
                              title="Xóa dòng"
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

              {/* Tổng cộng */}
              <div className="p-3 bg-amber-50/60 rounded-2xl border border-amber-200 flex items-center justify-between">
                <div>
                  <span className="text-slate-600 font-medium">Tổng giá trị đơn mua hàng (PO):</span>
                  <div className="text-lg font-bold text-amber-700">{formatVND(poTotalAmount)}</div>
                </div>
                <div className="text-right text-[11px] text-slate-500">
                  Kho nhận: <strong>{poWarehouseCode}</strong>
                </div>
              </div>

              {/* Ghi chú */}
              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Ghi chú đơn hàng:</label>
                <textarea
                  rows={2}
                  placeholder="Ghi chú điều kiện giao hàng, tiến độ thanh toán..."
                  value={poNotes}
                  onChange={(e) => setPoNotes(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreatePOModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={poSubmitting || poItems.length === 0}
                  className="flex items-center gap-1.5 px-5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer disabled:opacity-50 active:scale-95 transition-all"
                >
                  {poSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Xác nhận lập đơn PO</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: THÊM NHÀ CUNG CẤP */}
      {isSupplierModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-sm text-slate-900">Thêm Nhà cung cấp mới</h3>
                  <p className="text-[11px] text-slate-500">Đăng ký thông tin đối tác cung ứng hàng hóa</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsSupplierModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSupplierSubmit} className="space-y-3.5 text-xs">
              {supError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl">
                  {supError}
                </div>
              )}

              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Mã nhà cung cấp (*):</label>
                <input
                  type="text"
                  placeholder="VD: NCC-ASUS, NCC-LENOVO..."
                  value={supCode}
                  onChange={(e) => setSupCode(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl font-mono uppercase"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Tên Nhà cung cấp (*):</label>
                <input
                  type="text"
                  placeholder="VD: Công ty TNHH Asus Vietnam"
                  value={supName}
                  onChange={(e) => setSupName(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl font-medium"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Mã số thuế:</label>
                  <input
                    type="text"
                    placeholder="VD: 0100999888"
                    value={supTax}
                    onChange={(e) => setSupTax(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Điện thoại:</label>
                  <input
                    type="text"
                    placeholder="VD: 028-3829-1111"
                    value={supPhone}
                    onChange={(e) => setSupPhone(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-xl"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Email liên hệ:</label>
                <input
                  type="email"
                  placeholder="contact@supplier.com"
                  value={supEmail}
                  onChange={(e) => setSupEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl"
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Địa chỉ trụ sở:</label>
                <textarea
                  rows={2}
                  placeholder="Địa chỉ văn phòng / kho bãi..."
                  value={supAddress}
                  onChange={(e) => setSupAddress(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsSupplierModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={supSubmitting}
                  className="flex items-center gap-1.5 px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-xs cursor-pointer disabled:opacity-50 active:scale-95 transition-all"
                >
                  {supSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Lưu Nhà cung cấp</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: XÁC NHẬN HỦY ĐƠN MUA HÀNG */}
      {cancelPOModalOrder && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 animate-in zoom-in-95 duration-150 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <Ban className="w-6 h-6" />
            </div>
            <div className="text-center space-y-1">
              <h3 className="font-bold text-base text-slate-900">Hủy đơn mua hàng PO?</h3>
              <p className="text-xs text-slate-500">
                Bạn có chắc chắn muốn hủy đơn mua hàng <strong>{cancelPOModalOrder.po_number}</strong>?
              </p>
            </div>

            <div className="space-y-1.5 text-xs">
              <label className="font-semibold text-slate-700">Lý do hủy đơn:</label>
              <textarea
                rows={2}
                placeholder="VD: Nhà cung cấp hết hàng, thay đổi kế hoạch sản xuất..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-xl"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setCancelPOModalOrder(null)}
                className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Giữ lại
              </button>
              <button
                type="button"
                disabled={cancelSubmitting}
                onClick={handleCancelPOSubmit}
                className="flex items-center gap-1.5 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer disabled:opacity-50"
              >
                {cancelSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>Xác nhận Hủy PO</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

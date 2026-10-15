"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  Warehouse, 
  Search, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Sparkles, 
  Package, 
  ShieldAlert, 
  Boxes,
  ArrowUpRight,
  Filter,
  SlidersHorizontal,
  History,
  X,
  Plus,
  Loader2,
  ArrowRight,
  Calendar
} from "lucide-react";
import { fetchInventory, adjustInventoryApi, fetchStockAdjustmentsApi, InventoryItem, StockAdjustmentItem } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/toast-provider";

export default function InventoryPage() {
  const toast = useToast();
  const { hasPermission, isAdmin } = useAuth();
  const canAdjust = isAdmin || hasPermission("inventory:write");

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedWarehouse, setSelectedWarehouse] = useState<string>("all");
  const [stockLevelFilter, setStockLevelFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Adjustment Modal State
  const [isAdjustModalOpen, setIsAdjustModalOpen] = useState(false);
  const [adjustSku, setAdjustSku] = useState("");
  const [adjustWh, setAdjustWh] = useState("");
  const [adjustDelta, setAdjustDelta] = useState<string>("");
  const [adjustReason, setAdjustReason] = useState("");
  const [adjustSubmitting, setAdjustSubmitting] = useState(false);
  const [adjustError, setAdjustError] = useState<string | null>(null);

  // History State
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [historyItems, setHistoryItems] = useState<StockAdjustmentItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const loadInventory = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchInventory();
      setInventory(data);
    } catch (err: any) {
      setErrorMsg("Lỗi khi tải dữ liệu tồn kho: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await fetchStockAdjustmentsApi();
      setHistoryItems(data);
    } catch (err: any) {
      toast.error("Lỗi tải lịch sử kiểm kê", err.message);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    loadInventory();
  }, []);

  const openAdjustModal = (defaultSku?: string, defaultWh?: string) => {
    setAdjustSku(defaultSku || (uniqueProducts[0]?.sku || ""));
    setAdjustWh(defaultWh || (uniqueWarehouses[0]?.code || "WH-HN"));
    setAdjustDelta("");
    setAdjustReason("");
    setAdjustError(null);
    setIsAdjustModalOpen(true);
  };

  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdjustError(null);

    const delta = parseInt(adjustDelta, 10);
    if (isNaN(delta) || delta === 0) {
      setAdjustError("Vui lòng nhập số lượng điều chỉnh khác 0 (dương để tăng, âm để giảm).");
      return;
    }
    if (!adjustReason.trim()) {
      setAdjustError("Vui lòng nhập lý do kiểm kê / điều chỉnh.");
      return;
    }

    setAdjustSubmitting(true);
    try {
      const res = await adjustInventoryApi({
        sku: adjustSku,
        warehouse_code: adjustWh,
        delta_quantity: delta,
        reason: adjustReason.trim(),
      });
      toast.success(
        "Điều chỉnh kho thành công!",
        `${res.sku} (${res.warehouse_code}): ${res.quantity_before} -> ${res.quantity_after} (${res.delta_quantity > 0 ? "+" : ""}${res.delta_quantity})`
      );
      setIsAdjustModalOpen(false);
      await loadInventory();
    } catch (err: any) {
      setAdjustError(err.message || "Lỗi khi điều chỉnh tồn kho.");
    } finally {
      setAdjustSubmitting(false);
    }
  };

  // Danh sách các kho duy nhất
  const uniqueWarehouses = useMemo(() => {
    const map = new Map<string, string>();
    inventory.forEach((item) => {
      if (item.warehouse_code) {
        map.set(item.warehouse_code, item.warehouse_name || item.warehouse_code);
      }
    });
    return Array.from(map.entries()).map(([code, name]) => ({ code, name }));
  }, [inventory]);

  // Danh sách sản phẩm duy nhất
  const uniqueProducts = useMemo(() => {
    const map = new Map<string, string>();
    inventory.forEach((item) => {
      if (item.product_sku) {
        map.set(item.product_sku, item.product_name || item.product_sku);
      }
    });
    return Array.from(map.entries()).map(([sku, name]) => ({ sku, name }));
  }, [inventory]);

  // Current item selected in modal for live preview
  const currentItemInModal = useMemo(() => {
    return inventory.find(
      (it) => it.product_sku === adjustSku && it.warehouse_code === adjustWh
    );
  }, [inventory, adjustSku, adjustWh]);

  // Bộ lọc tổng hợp
  const filteredInventory = useMemo(() => {
    return inventory.filter((item) => {
      // 1. Tìm kiếm SKU hoặc tên
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const skuMatch = (item.product_sku || "").toLowerCase().includes(term);
        const nameMatch = (item.product_name || "").toLowerCase().includes(term);
        const whMatch = (item.warehouse_code || "").toLowerCase().includes(term) || 
                        (item.warehouse_name || "").toLowerCase().includes(term);
        if (!skuMatch && !nameMatch && !whMatch) return false;
      }

      // 2. Lọc kho
      if (selectedWarehouse !== "all" && item.warehouse_code !== selectedWarehouse) {
        return false;
      }

      // 3. Lọc mức tồn
      if (stockLevelFilter === "out_of_stock") {
        return item.quantity_available <= 0;
      }
      if (stockLevelFilter === "low_stock") {
        return item.quantity_available > 0 && item.quantity_available < 10;
      }
      if (stockLevelFilter === "in_stock") {
        return item.quantity_available >= 10;
      }

      return true;
    });
  }, [inventory, searchTerm, selectedWarehouse, stockLevelFilter]);

  // Thống kê nhanh
  const stats = useMemo(() => {
    let totalOnHand = 0;
    let totalReserved = 0;
    let totalAvailable = 0;
    let lowStockCount = 0;

    inventory.forEach((it) => {
      totalOnHand += it.quantity_on_hand || 0;
      totalReserved += it.quantity_reserved || 0;
      totalAvailable += it.quantity_available || 0;
      if (it.quantity_available < 10) lowStockCount++;
    });

    return { totalOnHand, totalReserved, totalAvailable, lowStockCount };
  }, [inventory]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Tiêu đề phân hệ */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-xs border border-emerald-100">
            <Warehouse className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Tồn kho Thời gian thực (Real-time Inventory)
            </h1>
            <p className="text-xs text-slate-500">
              Kiểm soát số lượng tồn thực tế, hàng đang giữ đơn (HITL reserved) và số lượng khả dụng
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => {
              loadHistory();
              setIsHistoryOpen(true);
            }}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 cursor-pointer"
          >
            <History className="w-3.5 h-3.5 text-slate-500" />
            <span>Lịch sử kiểm kê</span>
          </button>

          {canAdjust && (
            <button
              type="button"
              onClick={() => openAdjustModal()}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span>Điều chỉnh tồn kho</span>
            </button>
          )}

          <button
            type="button"
            onClick={loadInventory}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <Link
            href="/copilot?q=Kiểm tra tồn kho các sản phẩm sắp hết hàng"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Tra cứu tồn kho</span>
          </Link>
        </div>
      </div>

      {/* 2. Thẻ chỉ số tồn kho ERP */}
      <div className="px-6 py-4 grid grid-cols-2 md:grid-cols-4 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
            <Package className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tồn kho vật lý (On Hand)</div>
            <div className="text-base font-bold text-slate-900">{stats.totalOnHand.toLocaleString()} sp</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
            <Clock className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Đang giữ đơn (Reserved)</div>
            <div className="text-base font-bold text-amber-600">{stats.totalReserved.toLocaleString()} sp</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Khả dụng để bán (Available)</div>
            <div className="text-base font-bold text-emerald-600">{stats.totalAvailable.toLocaleString()} sp</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Cảnh báo sắp hết / hết hàng</div>
            <div className="text-base font-bold text-rose-600">{stats.lowStockCount} mặt hàng</div>
          </div>
        </div>
      </div>

      {/* 3. Bộ lọc kho & mức tồn */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex flex-wrap items-center gap-2">
          {/* Lọc theo kho */}
          <select
            value={selectedWarehouse}
            onChange={(e) => setSelectedWarehouse(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-200/90 rounded-xl text-xs font-semibold text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 shadow-2xs cursor-pointer"
          >
            <option value="all">Tất cả kho hàng</option>
            {uniqueWarehouses.map((wh) => (
              <option key={wh.code} value={wh.code}>
                {wh.name} ({wh.code})
              </option>
            ))}
          </select>

          {/* Lọc theo mức tồn */}
          {[
            { id: "all", label: "Tất cả mức tồn" },
            { id: "in_stock", label: "Còn hàng (≥10)" },
            { id: "low_stock", label: "Sắp hết (<10)" },
            { id: "out_of_stock", label: "Hết hàng (≤0)" },
          ].map((st) => {
            const active = stockLevelFilter === st.id;
            return (
              <button
                key={st.id}
                type="button"
                onClick={() => setStockLevelFilter(st.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer border ${
                  active
                    ? "bg-emerald-600 text-white border-emerald-600 shadow-2xs"
                    : "bg-white text-slate-600 border-slate-200/90 hover:bg-slate-50"
                }`}
              >
                {st.label}
              </button>
            );
          })}
        </div>

        <div className="relative w-72">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Tìm theo SKU, tên sản phẩm hoặc kho..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200/90 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 shadow-2xs"
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

      {/* 5. Bảng tồn kho chi tiết */}
      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Mã SKU</th>
                  <th className="py-3 px-4">Tên sản phẩm</th>
                  <th className="py-3 px-4">Kho hàng</th>
                  <th className="py-3 px-4 text-center">Tồn thực tế</th>
                  <th className="py-3 px-4 text-center">Đang giữ đơn</th>
                  <th className="py-3 px-4 text-center">Khả dụng</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4 text-center">Hỏi Copilot</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {loading ? (
                  Array.from({ length: 7 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-24" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-44" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-100 rounded-md w-28" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-4 bg-slate-100 rounded-md w-12 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-4 bg-slate-100 rounded-md w-12 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-4 bg-slate-200 rounded-md w-12 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-16 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredInventory.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <Warehouse className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Không tìm thấy thông tin tồn kho</p>
                      <p className="text-[11px] text-slate-400 mt-1">Vui lòng điều chỉnh lại bộ lọc hoặc từ khóa tìm kiếm</p>
                    </td>
                  </tr>
                ) : (
                  filteredInventory.map((item, idx) => {
                    const isOutOfStock = item.quantity_available <= 0;
                    const isLowStock = item.quantity_available > 0 && item.quantity_available < 10;

                    return (
                      <tr
                        key={`${item.product_sku}-${item.warehouse_code}-${idx}`}
                        className="hover:bg-slate-50/80 transition-colors"
                      >
                        <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                          {item.product_sku}
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {item.product_name}
                        </td>
                        <td className="py-3.5 px-4 text-slate-600">
                          <span className="font-medium">{item.warehouse_name || item.warehouse_code}</span>
                          <span className="text-[10.5px] text-slate-400 block font-mono">{item.warehouse_code}</span>
                        </td>
                        <td className="py-3.5 px-4 text-center font-bold text-slate-800">
                          {item.quantity_on_hand.toLocaleString()}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {item.quantity_reserved > 0 ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                              {item.quantity_reserved.toLocaleString()}
                            </span>
                          ) : (
                            <span className="text-slate-400">0</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-center font-bold">
                          <span className={`text-xs px-2 py-0.5 rounded-md ${
                            isOutOfStock
                              ? "bg-rose-50 text-rose-700 font-extrabold"
                              : isLowStock
                              ? "bg-amber-50 text-amber-700 font-bold"
                              : "bg-emerald-50 text-emerald-700 font-bold"
                          }`}>
                            {item.quantity_available.toLocaleString()}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {isOutOfStock ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                              Hết hàng
                            </span>
                          ) : isLowStock ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                              Sắp hết hàng
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              Đủ hàng
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            {canAdjust && (
                              <button
                                type="button"
                                onClick={() => openAdjustModal(item.product_sku, item.warehouse_code)}
                                className="inline-flex items-center gap-1 text-[11px] text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50 px-2 py-1 rounded-lg transition-colors font-semibold"
                                title="Lập phiếu điều chỉnh kiểm kê cho mặt hàng này"
                              >
                                <SlidersHorizontal className="w-3 h-3" />
                                <span>Kiểm kê</span>
                              </button>
                            )}
                            <Link
                              href={`/copilot?q=Kiểm tra tồn kho và dự báo nhu cầu cho sản phẩm ${item.product_sku}`}
                              className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors font-medium"
                            >
                              <Sparkles className="w-3 h-3" />
                              <span>Hỏi AI</span>
                            </Link>
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
            <span>Hiển thị {filteredInventory.length} / {inventory.length} bản ghi tồn kho</span>
            <span>Công thức: Khả dụng = Tồn thực tế - Đang giữ đơn (Reserved)</span>
          </div>
        </div>
      </div>

      {/* MODAL: ĐIỀU CHỈNH TỒN KHO */}
      {isAdjustModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl border border-slate-200/90 shadow-2xl max-w-lg w-full overflow-hidden flex flex-col animate-in zoom-in-95 duration-150">
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
                  <SlidersHorizontal className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Phiếu kiểm kê & Điều chỉnh tồn kho</h3>
                  <p className="text-[11px] text-slate-500">Cập nhật số lượng tồn thực tế vào cơ sở dữ liệu ERP</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsAdjustModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Form */}
            <form onSubmit={handleAdjustSubmit} className="p-6 space-y-4 text-xs">
              {adjustError && (
                <div className="p-3 rounded-xl bg-rose-50 text-rose-800 border border-rose-200 text-xs">
                  {adjustError}
                </div>
              )}

              {/* Sản phẩm */}
              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Mặt hàng / Sản phẩm (SKU):</label>
                <select
                  value={adjustSku}
                  onChange={(e) => setAdjustSku(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  {uniqueProducts.map((p) => (
                    <option key={p.sku} value={p.sku}>
                      {p.sku} - {p.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Kho hàng */}
              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Kho hàng điều chỉnh:</label>
                <select
                  value={adjustWh}
                  onChange={(e) => setAdjustWh(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-medium focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                >
                  {uniqueWarehouses.map((w) => (
                    <option key={w.code} value={w.code}>
                      {w.code} - {w.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Số lượng thay đổi */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="font-semibold text-slate-700">Số lượng điều chỉnh (Delta):</label>
                  <span className="text-[11px] text-slate-400">Dương (+) tăng, Âm (-) giảm</span>
                </div>
                <input
                  type="number"
                  placeholder="Ví dụ: 15 hoặc -5"
                  value={adjustDelta}
                  onChange={(e) => setAdjustDelta(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-900 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              {/* Live Preview Card */}
              {currentItemInModal && (
                <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-200 space-y-2">
                  <div className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">Xem trước thay đổi</div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 bg-white rounded-xl border border-slate-100">
                      <div className="text-[10px] text-slate-400">Tồn hiện tại</div>
                      <div className="font-bold text-slate-800 text-sm">{currentItemInModal.quantity_on_hand}</div>
                    </div>
                    <div className="p-2 bg-white rounded-xl border border-slate-100">
                      <div className="text-[10px] text-slate-400">Đang giữ đơn</div>
                      <div className="font-bold text-amber-600 text-sm">{currentItemInModal.quantity_reserved}</div>
                    </div>
                    <div className="p-2 bg-white rounded-xl border border-slate-100">
                      <div className="text-[10px] text-slate-400">Tồn sau chỉnh</div>
                      <div className={`font-bold text-sm ${
                        (currentItemInModal.quantity_on_hand + (parseInt(adjustDelta, 10) || 0)) >= currentItemInModal.quantity_reserved
                          ? "text-emerald-600"
                          : "text-rose-600"
                      }`}>
                        {isNaN(parseInt(adjustDelta, 10))
                          ? currentItemInModal.quantity_on_hand
                          : currentItemInModal.quantity_on_hand + parseInt(adjustDelta, 10)}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Lý do */}
              <div className="space-y-1.5">
                <label className="font-semibold text-slate-700">Lý do điều chỉnh kiểm kê:</label>
                <textarea
                  rows={2}
                  placeholder="Ví dụ: Kiểm kê định kỳ tháng 10, phát hiện dư 2 sản phẩm do sai sót nhập liệu..."
                  value={adjustReason}
                  onChange={(e) => setAdjustReason(e.target.value)}
                  className="w-full px-3 py-2 bg-white border border-slate-200 rounded-xl text-xs font-normal focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                />
              </div>

              {/* Buttons */}
              <div className="pt-2 flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setIsAdjustModalOpen(false)}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-semibold text-xs transition-colors"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={adjustSubmitting}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-xs shadow-xs transition-all active:scale-95 disabled:opacity-50 flex items-center gap-1.5 cursor-pointer"
                >
                  {adjustSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Xác nhận điều chỉnh</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DRAWER: LỊCH SỬ KIỂM KÊ */}
      {isHistoryOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-3xl border border-slate-200/90 shadow-2xl max-w-3xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-100">
                  <History className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Lịch sử phiếu kiểm kê & Điều chỉnh tồn kho</h3>
                  <p className="text-[11px] text-slate-500">Truy vết số liệu thay đổi kho vật lý theo thời gian</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsHistoryOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {historyLoading ? (
                <div className="py-12 text-center text-xs text-slate-400 flex flex-col items-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                  <span>Đang tải lịch sử kiểm kê...</span>
                </div>
              ) : historyItems.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400">
                  Chưa có phiếu kiểm kê hoặc điều chỉnh nào được ghi nhận.
                </div>
              ) : (
                <div className="border border-slate-200 rounded-2xl overflow-hidden shadow-2xs">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50/80 border-b border-slate-200 text-[11px] font-bold uppercase text-slate-500">
                      <tr>
                        <th className="py-2.5 px-3">Thời gian</th>
                        <th className="py-2.5 px-3">Mã SKU</th>
                        <th className="py-2.5 px-3">Kho</th>
                        <th className="py-2.5 px-3 text-center">Thay đổi (Delta)</th>
                        <th className="py-2.5 px-3 text-center">Trước → Sau</th>
                        <th className="py-2.5 px-3">Lý do điều chỉnh</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {historyItems.map((h) => (
                        <tr key={h.id} className="hover:bg-slate-50/60 transition-colors">
                          <td className="py-2.5 px-3 text-slate-500 text-[11px] whitespace-nowrap">
                            {new Date(h.created_at).toLocaleString("vi-VN", {
                              day: "2-digit",
                              month: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-900">{h.sku}</td>
                          <td className="py-2.5 px-3 font-semibold text-slate-600">{h.warehouse_code}</td>
                          <td className="py-2.5 px-3 text-center">
                            <span className={`inline-flex px-2 py-0.5 rounded-full font-bold text-[10.5px] ${
                              h.delta_quantity > 0
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-rose-50 text-rose-700 border border-rose-200"
                            }`}>
                              {h.delta_quantity > 0 ? `+${h.delta_quantity}` : h.delta_quantity}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-center font-medium text-slate-600">
                            {h.quantity_before} → <strong className="text-slate-900">{h.quantity_after}</strong>
                          </td>
                          <td className="py-2.5 px-3 text-slate-600 max-w-xs truncate" title={h.reason}>
                            {h.reason}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end">
              <button
                type="button"
                onClick={() => setIsHistoryOpen(false)}
                className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

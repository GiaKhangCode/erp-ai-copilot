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
  Filter
} from "lucide-react";
import { fetchInventory, InventoryItem } from "@/lib/api";

export default function InventoryPage() {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedWarehouse, setSelectedWarehouse] = useState<string>("all");
  const [stockLevelFilter, setStockLevelFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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

  useEffect(() => {
    loadInventory();
  }, []);

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
                          <Link
                            href={`/copilot?q=Kiểm tra tồn kho và dự báo nhu cầu cho sản phẩm ${item.product_sku}`}
                            className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors font-medium"
                          >
                            <Sparkles className="w-3 h-3" />
                            <span>Hỏi AI</span>
                          </Link>
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
    </div>
  );
}

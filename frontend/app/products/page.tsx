"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  Package, 
  Search, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Sparkles, 
  Warehouse, 
  Tag, 
  ArrowUpRight,
  Boxes
} from "lucide-react";
import { fetchProducts, ProductItem } from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

export default function ProductsPage() {
  const { hasPermission } = useAuth();
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadProducts = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err: any) {
      setErrorMsg("Lỗi khi tải danh mục sản phẩm: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, []);

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const skuMatch = (p.sku || "").toLowerCase().includes(term);
        const nameMatch = (p.name || "").toLowerCase().includes(term);
        if (!skuMatch && !nameMatch) return false;
      }
      if (statusFilter === "active") return p.is_active;
      if (statusFilter === "inactive") return !p.is_active;
      return true;
    });
  }, [products, searchTerm, statusFilter]);

  const stats = useMemo(() => {
    const total = products.length;
    const active = products.filter((p) => p.is_active).length;
    const inactive = total - active;
    return { total, active, inactive };
  }, [products]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Header phân hệ */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center shadow-xs border border-indigo-100">
            <Package className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Danh mục Sản phẩm (Product Catalog)
            </h1>
            <p className="text-xs text-slate-500">
              Quản lý mã hàng hóa SKU, đơn giá niêm yết và trạng thái kinh doanh
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadProducts}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-indigo-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <Link
            href="/inventory"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer"
          >
            <Warehouse className="w-3.5 h-3.5 text-emerald-600" />
            <span>Xem tồn kho</span>
          </Link>

          <Link
            href="/copilot?q=Kiểm tra danh sách giá niêm yết các sản phẩm"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Tra cứu bằng AI</span>
          </Link>
        </div>
      </div>

      {/* 2. Thẻ thống kê */}
      <div className="px-6 py-4 grid grid-cols-3 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
            <Boxes className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tổng mặt hàng niêm yết</div>
            <div className="text-base font-bold text-slate-900">{stats.total} sản phẩm</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Đang kinh doanh</div>
            <div className="text-base font-bold text-emerald-600">{stats.active} sản phẩm</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
            <XCircle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tạm ngừng kinh doanh</div>
            <div className="text-base font-bold text-slate-600">{stats.inactive} sản phẩm</div>
          </div>
        </div>
      </div>

      {/* 3. Tìm kiếm & Lọc */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          {[
            { id: "all", label: "Tất cả" },
            { id: "active", label: "Đang bán" },
            { id: "inactive", label: "Tạm ngừng" },
          ].map((st) => {
            const active = statusFilter === st.id;
            return (
              <button
                key={st.id}
                type="button"
                onClick={() => setStatusFilter(st.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all cursor-pointer border ${
                  active
                    ? "bg-indigo-600 text-white border-indigo-600 shadow-2xs"
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
            placeholder="Tìm theo SKU hoặc tên sản phẩm..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200/90 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 shadow-2xs"
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

      {/* 5. Bảng danh mục sản phẩm */}
      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Mã SKU</th>
                  <th className="py-3 px-4">Tên hàng hóa</th>
                  <th className="py-3 px-4 text-right">Đơn giá niêm yết</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-28" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-48" /></td>
                      <td className="py-3.5 px-4 text-right"><div className="h-4 bg-slate-200 rounded-md w-24 ml-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-16 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <Package className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Không tìm thấy sản phẩm nào</p>
                      <p className="text-[11px] text-slate-400 mt-1">Vui lòng điều chỉnh lại bộ lọc hoặc từ khóa tìm kiếm</p>
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((prod) => (
                    <tr
                      key={prod.id || prod.sku}
                      className="hover:bg-slate-50/80 transition-colors"
                    >
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-900 flex items-center gap-2">
                        <Tag className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                        <span>{prod.sku}</span>
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-slate-800">
                        {prod.name}
                      </td>
                      <td className="py-3.5 px-4 text-right font-bold text-slate-900 text-xs">
                        {formatVND(prod.unit_price)}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {prod.is_active ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            Đang kinh doanh
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                            <XCircle className="w-3 h-3 text-slate-400" />
                            Tạm ngừng
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex items-center justify-center gap-2">
                          <Link
                            href={`/inventory`}
                            className="inline-flex items-center gap-1 text-[11px] text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 px-2 py-1 rounded-lg transition-colors font-semibold"
                            title="Kiểm tra tồn kho thời gian thực"
                          >
                            <Warehouse className="w-3 h-3" />
                            <span>Tồn kho</span>
                          </Link>
                          {hasPermission("orders:create") && (
                            <Link
                              href={`/copilot?q=Tạo đơn hàng nháp cho 1 sản phẩm ${prod.sku}`}
                              className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors font-semibold"
                              title="Tạo đơn hàng nhanh với AI"
                            >
                              <Sparkles className="w-3 h-3" />
                              <span>Đặt hàng</span>
                            </Link>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
            <span>Hiển thị {filteredProducts.length} / {products.length} sản phẩm</span>
            <span>Đơn giá niêm yết đã bao gồm thuế VAT</span>
          </div>
        </div>
      </div>
    </div>
  );
}

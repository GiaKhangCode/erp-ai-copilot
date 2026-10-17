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
  Boxes,
  Plus,
  Pencil,
  Ban,
  X,
  Loader2,
  DollarSign
} from "lucide-react";
import { 
  fetchProducts, 
  ProductItem, 
  createProductApi, 
  updateProductApi, 
  deleteProductApi 
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

export default function ProductsPage() {
  const { hasPermission, isAdmin } = useAuth();
  const canWriteProduct = isAdmin || hasPermission("products:write");

  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // State Modal Thêm / Sửa
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Form Fields
  const [formSku, setFormSku] = useState("");
  const [formName, setFormName] = useState("");
  const [formUnitPrice, setFormUnitPrice] = useState<number>(100000);
  const [formCostPrice, setFormCostPrice] = useState<number>(60000);
  const [formIsActive, setFormIsActive] = useState<boolean>(true);

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

  const openCreateModal = () => {
    setEditingProduct(null);
    setFormSku(`SKU-${String(products.length + 1).padStart(3, "0")}`);
    setFormName("");
    setFormUnitPrice(500000);
    setFormCostPrice(300000);
    setFormIsActive(true);
    setIsModalOpen(true);
  };

  const openEditModal = (prod: ProductItem) => {
    setEditingProduct(prod);
    setFormSku(prod.sku);
    setFormName(prod.name);
    setFormUnitPrice(prod.unit_price || 0);
    setFormCostPrice((prod as any).cost_price || 0);
    setFormIsActive(prod.is_active);
    setIsModalOpen(true);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setErrorMsg("Tên sản phẩm không được để trống.");
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      if (editingProduct) {
        await updateProductApi(editingProduct.id, {
          name: formName.trim(),
          unit_price: Number(formUnitPrice),
          cost_price: Number(formCostPrice),
          is_active: formIsActive,
        });
        setSuccessMsg(`Đã cập nhật sản phẩm '${formName}' thành công.`);
      } else {
        await createProductApi({
          sku: formSku.trim().toUpperCase(),
          name: formName.trim(),
          unit_price: Number(formUnitPrice),
          cost_price: Number(formCostPrice),
          is_active: formIsActive,
        });
        setSuccessMsg(`Đã thêm mới mặt hàng '${formName}' (${formSku.toUpperCase()}) thành công.`);
      }
      setIsModalOpen(false);
      await loadProducts();
    } catch (err: any) {
      setErrorMsg(err.message || "Không thể lưu sản phẩm.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (prod: ProductItem) => {
    const newStatus = !prod.is_active;
    const confirmMsg = !newStatus 
      ? `Ngừng kinh doanh sản phẩm '${prod.name}' (${prod.sku})?` 
      : `Kích hoạt mở bán lại cho sản phẩm '${prod.name}'?`;

    if (!window.confirm(confirmMsg)) return;

    try {
      await updateProductApi(prod.id, { is_active: newStatus });
      setSuccessMsg(`Đã chuyển trạng thái sản phẩm '${prod.sku}' sang ${newStatus ? "Đang bán" : "Ngừng bán"}.`);
      await loadProducts();
    } catch (err: any) {
      setErrorMsg(err.message || "Không thể cập nhật trạng thái kinh doanh.");
    }
  };

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
              Danh mục Sản phẩm & Bảng giá (Product Catalog)
            </h1>
            <p className="text-xs text-slate-500">
              Quản lý mã hàng hóa SKU, đơn giá niêm yết, giá vốn COGS và trạng thái kinh doanh
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Nút thêm sản phẩm (RBAC check: products:write) */}
          {canWriteProduct && (
            <button
              type="button"
              onClick={openCreateModal}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <Plus className="w-4 h-4" />
              <span>Thêm sản phẩm</span>
            </button>
          )}

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
            className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer active:scale-95"
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

      {/* Thông báo */}
      {errorMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}
      {successMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-emerald-50 text-emerald-800 text-xs border border-emerald-200 flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">✕</button>
        </div>
      )}

      {/* 4. Bảng danh mục sản phẩm */}
      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Mã SKU</th>
                  <th className="py-3 px-4">Tên sản phẩm</th>
                  <th className="py-3 px-4 text-right">Giá bán niêm yết</th>
                  <th className="py-3 px-4 text-right">Giá vốn (COGS)</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-20" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-52" /></td>
                      <td className="py-3.5 px-4 text-right"><div className="h-4 bg-slate-100 rounded-md w-24 ml-auto" /></td>
                      <td className="py-3.5 px-4 text-right"><div className="h-4 bg-slate-100 rounded-md w-20 ml-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-16 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredProducts.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <Package className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Không tìm thấy sản phẩm nào</p>
                      <p className="text-[11px] text-slate-400 mt-1">Vui lòng kiểm tra lại từ khóa hoặc tạo sản phẩm mới</p>
                    </td>
                  </tr>
                ) : (
                  filteredProducts.map((prod) => {
                    const costPrice = (prod as any).cost_price || 0;
                    return (
                      <tr key={prod.id || prod.sku} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-bold text-indigo-700 flex items-center gap-2">
                          <Tag className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                          <span>{prod.sku}</span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {prod.name}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-bold text-slate-900">
                          {formatVND(prod.unit_price)}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono text-slate-500">
                          {costPrice > 0 ? formatVND(costPrice) : <span className="text-slate-300 italic">Chưa set</span>}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {prod.is_active ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              Đang bán
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-slate-100 text-slate-600 border border-slate-200">
                              <XCircle className="w-3 h-3 text-slate-400" />
                              Tạm ngừng
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            {/* Nút sửa (chỉ hiện khi có quyền products:write) */}
                            {canWriteProduct && (
                              <button
                                type="button"
                                onClick={() => openEditModal(prod)}
                                className="inline-flex items-center gap-1 text-[11px] text-slate-600 hover:text-indigo-700 hover:bg-indigo-50 px-2 py-1 rounded-md transition-colors cursor-pointer"
                                title="Chỉnh sửa thông số & giá"
                              >
                                <Pencil className="w-3 h-3" />
                                <span>Sửa</span>
                              </button>
                            )}

                            {/* Nút ngừng kinh doanh */}
                            {canWriteProduct && (
                              <button
                                type="button"
                                onClick={() => handleToggleStatus(prod)}
                                className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md transition-colors cursor-pointer ${
                                  prod.is_active
                                    ? "text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                    : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                }`}
                                title={prod.is_active ? "Ngừng kinh doanh sản phẩm này" : "Mở bán lại"}
                              >
                                <Ban className="w-3 h-3" />
                                <span>{prod.is_active ? "Ngừng bán" : "Mở bán"}</span>
                              </button>
                            )}

                            <Link
                              href={`/inventory`}
                              className="inline-flex items-center gap-1 text-[11px] text-emerald-600 hover:text-emerald-800 hover:bg-emerald-50 px-2 py-1 rounded-md transition-colors font-semibold"
                              title="Kiểm tra tồn kho sản phẩm này"
                            >
                              <Warehouse className="w-3 h-3" />
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
            <span>Hiển thị {filteredProducts.length} / {products.length} sản phẩm</span>
            <span>ERP Product Master Data Service</span>
          </div>
        </div>
      </div>

      {/* 5. Modal Form Thêm / Chỉnh sửa Sản phẩm */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white w-full max-w-lg rounded-2xl border border-slate-200 shadow-2xl overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
                  {editingProduct ? <Pencil className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {editingProduct ? "Chỉnh sửa sản phẩm & Bảng giá" : "Thêm mới sản phẩm vào danh mục"}
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    {editingProduct ? `Mã SKU: ${editingProduct.sku}` : "Khởi tạo mã SKU và thiết lập giá bán/giá vốn"}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleFormSubmit} className="p-6 space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Mã SKU *</label>
                  <input
                    type="text"
                    disabled={!!editingProduct}
                    value={formSku}
                    onChange={(e) => setFormSku(e.target.value)}
                    placeholder="VD: SKU-010"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 disabled:bg-slate-100"
                    required
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Trạng thái kinh doanh</label>
                  <select
                    value={formIsActive ? "true" : "false"}
                    onChange={(e) => setFormIsActive(e.target.value === "true")}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  >
                    <option value="true">Đang kinh doanh</option>
                    <option value="false">Tạm ngừng kinh doanh</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Tên sản phẩm / Mặt hàng *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="VD: Màn hình Dell UltraSharp 27 inch 4K"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Giá bán niêm yết (VND) *</label>
                  <input
                    type="number"
                    min="1000"
                    step="10000"
                    value={formUnitPrice}
                    onChange={(e) => setFormUnitPrice(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                    required
                  />
                  <p className="text-[10px] text-slate-400 mt-0.5">Đơn giá bán ra cho khách hàng</p>
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Giá vốn hàng bán COGS (VND)</label>
                  <input
                    type="number"
                    min="0"
                    step="10000"
                    value={formCostPrice}
                    onChange={(e) => setFormCostPrice(Number(e.target.value))}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                  <p className="text-[10px] text-slate-400 mt-0.5">Giá nhập kho để tính lợi nhuận gộp</p>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70 text-[11px] text-slate-500 space-y-1">
                <div className="flex justify-between">
                  <span>Lợi nhuận gộp dự kiến:</span>
                  <span className="font-mono font-bold text-emerald-600">
                    {formatVND(Math.max(0, formUnitPrice - formCostPrice))}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Tỷ suất biên lợi nhuận:</span>
                  <span className="font-mono font-bold text-slate-700">
                    {formUnitPrice > 0 ? ((formUnitPrice - formCostPrice) / formUnitPrice * 100).toFixed(1) : 0}%
                  </span>
                </div>
              </div>

              <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold shadow-xs transition-all cursor-pointer disabled:opacity-50"
                >
                  {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{editingProduct ? "Lưu thay đổi" : "Tạo sản phẩm"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

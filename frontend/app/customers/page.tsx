"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  Users, 
  Search, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Sparkles, 
  ShoppingCart, 
  Building2, 
  Mail, 
  UserCheck,
  UserPlus,
  Pencil,
  Ban,
  X,
  CreditCard,
  Phone,
  MapPin,
  Loader2
} from "lucide-react";
import { 
  fetchCustomers, 
  CustomerItem, 
  createCustomerApi, 
  updateCustomerApi, 
  deleteCustomerApi 
} from "@/lib/api";
import { PermissionGate, AccessDeniedView } from "@/components/permission-gate";
import { useAuth } from "@/lib/auth-context";

export default function CustomersPage() {
  return (
    <PermissionGate
      permission="customers:read"
      fallback={
        <AccessDeniedView
          permission="customers:read"
          title="Quản lý Khách hàng & Đối tác"
          description="Tài khoản của bạn chưa được cấp quyền xem danh sách khách hàng & đối tác doanh nghiệp."
        />
      }
    >
      <CustomersContent />
    </PermissionGate>
  );
}

function CustomersContent() {
  const { hasPermission, isAdmin } = useAuth();
  const canWriteCustomer = isAdmin || hasPermission("customers:write");

  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // State Modal Thêm / Sửa
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<CustomerItem | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Form Fields
  const [formCode, setFormCode] = useState("");
  const [formName, setFormName] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formPhone, setFormPhone] = useState("");
  const [formAddress, setFormAddress] = useState("");
  const [formCreditLimit, setFormCreditLimit] = useState<number>(50000000);
  const [formStatus, setFormStatus] = useState("active");

  const loadCustomers = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchCustomers();
      setCustomers(data);
    } catch (err: any) {
      if (err.message?.includes("403")) {
        setErrorMsg("Tài khoản của bạn không có quyền xem danh sách khách hàng (403 Forbidden). Vui lòng liên hệ Quản trị viên.");
      } else {
        setErrorMsg("Lỗi khi tải danh sách khách hàng: " + err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, []);

  const openCreateModal = () => {
    setEditingCustomer(null);
    setFormCode(`CUS-${String(customers.length + 1).padStart(4, "0")}`);
    setFormName("");
    setFormEmail("");
    setFormPhone("");
    setFormAddress("");
    setFormCreditLimit(50000000);
    setFormStatus("active");
    setIsModalOpen(true);
  };

  const openEditModal = (cust: CustomerItem) => {
    setEditingCustomer(cust);
    setFormCode(cust.code);
    setFormName(cust.name);
    setFormEmail(cust.email || "");
    setFormPhone(cust.phone || "");
    setFormAddress(cust.address || "");
    setFormCreditLimit(cust.credit_limit || 50000000);
    setFormStatus(cust.status || "active");
    setIsModalOpen(true);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setErrorMsg("Tên khách hàng không được để trống.");
      return;
    }
    setSubmitting(true);
    setErrorMsg(null);
    try {
      if (editingCustomer) {
        // Cập nhật
        await updateCustomerApi(editingCustomer.id, {
          name: formName.trim(),
          email: formEmail.trim() || undefined,
          phone: formPhone.trim() || undefined,
          address: formAddress.trim() || undefined,
          credit_limit: Number(formCreditLimit) || 0,
          status: formStatus,
        });
        setSuccessMsg(`Đã cập nhật thông tin khách hàng '${formName}' thành công.`);
      } else {
        // Thêm mới
        await createCustomerApi({
          code: formCode.trim().toUpperCase(),
          name: formName.trim(),
          email: formEmail.trim() || undefined,
          phone: formPhone.trim() || undefined,
          address: formAddress.trim() || undefined,
          credit_limit: Number(formCreditLimit) || 50000000,
          status: formStatus,
        });
        setSuccessMsg(`Đã thêm mới đối tác khách hàng '${formName}' thành công.`);
      }
      setIsModalOpen(false);
      await loadCustomers();
    } catch (err: any) {
      setErrorMsg(err.message || "Không thể lưu thông tin khách hàng.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (cust: CustomerItem) => {
    const newStatus = cust.status === "active" ? "inactive" : "active";
    const confirmMsg = newStatus === "inactive" 
      ? `Bạn có chắc chắn muốn tạm dừng giao dịch với đối tác '${cust.name}'?` 
      : `Kích hoạt lại trạng thái hoạt động cho đối tác '${cust.name}'?`;

    if (!window.confirm(confirmMsg)) return;

    try {
      await updateCustomerApi(cust.id, { status: newStatus });
      setSuccessMsg(`Đã chuyển trạng thái đối tác '${cust.name}' sang ${newStatus === "active" ? "Hoạt động" : "Tạm ngừng"}.`);
      await loadCustomers();
    } catch (err: any) {
      setErrorMsg(err.message || "Không thể thay đổi trạng thái đối tác.");
    }
  };

  const filteredCustomers = useMemo(() => {
    return customers.filter((c) => {
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const codeMatch = (c.code || "").toLowerCase().includes(term);
        const nameMatch = (c.name || "").toLowerCase().includes(term);
        const emailMatch = (c.email || "").toLowerCase().includes(term);
        if (!codeMatch && !nameMatch && !emailMatch) return false;
      }
      if (statusFilter === "active") return c.status === "active";
      if (statusFilter === "inactive") return c.status !== "active";
      return true;
    });
  }, [customers, searchTerm, statusFilter]);

  const stats = useMemo(() => {
    const total = customers.length;
    const active = customers.filter((c) => c.status === "active").length;
    const inactive = total - active;
    return { total, active, inactive };
  }, [customers]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Header phân hệ */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-sky-50 text-sky-600 flex items-center justify-center shadow-xs border border-sky-100">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Quản lý Khách hàng & Đối tác (Customers)
            </h1>
            <p className="text-xs text-slate-500">
              Danh bạ khách hàng doanh nghiệp, hạn mức tín dụng và công nợ bán hàng
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Nút thêm khách hàng (RBAC check) */}
          {canWriteCustomer && (
            <button
              type="button"
              onClick={openCreateModal}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
            >
              <UserPlus className="w-4 h-4" />
              <span>Thêm khách hàng</span>
            </button>
          )}

          <button
            type="button"
            onClick={loadCustomers}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-sky-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <Link
            href="/orders"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer"
          >
            <ShoppingCart className="w-3.5 h-3.5 text-blue-600" />
            <span>Xem đơn hàng</span>
          </Link>

          <Link
            href="/copilot?q=Tổng hợp thông tin doanh số top khách hàng lớn nhất"
            className="flex items-center gap-1.5 px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 rounded-xl text-xs font-semibold shadow-2xs transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Phân tích khách hàng</span>
          </Link>
        </div>
      </div>

      {/* 2. Thẻ thống kê */}
      <div className="px-6 py-4 grid grid-cols-3 gap-3.5 shrink-0 bg-[#F8FAFC]">
        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center shrink-0">
            <Building2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tổng số đối tác</div>
            <div className="text-base font-bold text-slate-900">{stats.total} khách hàng</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
            <UserCheck className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Đang hoạt động (Active)</div>
            <div className="text-base font-bold text-emerald-600">{stats.active} khách hàng</div>
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-2xs flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
            <XCircle className="w-4 h-4" />
          </div>
          <div>
            <div className="text-[11px] font-medium text-slate-400">Tạm dừng giao dịch</div>
            <div className="text-base font-bold text-slate-600">{stats.inactive} khách hàng</div>
          </div>
        </div>
      </div>

      {/* 3. Tìm kiếm & Lọc */}
      <div className="px-6 pb-3 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2">
          {[
            { id: "all", label: "Tất cả" },
            { id: "active", label: "Đang hoạt động" },
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
                    ? "bg-sky-600 text-white border-sky-600 shadow-2xs"
                    : "bg-white text-slate-600 border-slate-200/90 hover:bg-slate-50"
                }`}
              >
                {st.label}
              </button>
            );
          })}
        </div>

        <div className="relative w-80">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Tìm theo mã đối tác, tên hoặc email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200/90 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 shadow-2xs"
          />
        </div>
      </div>

      {/* Thông báo thông điệp */}
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

      {/* 4. Bảng danh sách khách hàng */}
      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Mã đối tác</th>
                  <th className="py-3 px-4">Tên doanh nghiệp / Đối tác</th>
                  <th className="py-3 px-4">Liên hệ & Địa chỉ</th>
                  <th className="py-3 px-4 text-right">Hạn mức nợ (Limit)</th>
                  <th className="py-3 px-4 text-center">Trạng thái</th>
                  <th className="py-3 px-4 text-center">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-24" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-200 rounded-md w-48" /></td>
                      <td className="py-3.5 px-4"><div className="h-4 bg-slate-100 rounded-md w-36" /></td>
                      <td className="py-3.5 px-4 text-right"><div className="h-4 bg-slate-100 rounded-md w-24 ml-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-20 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredCustomers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <Users className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Không tìm thấy khách hàng nào</p>
                      <p className="text-[11px] text-slate-400 mt-1">Vui lòng điều chỉnh lại bộ lọc hoặc tạo đối tác mới</p>
                    </td>
                  </tr>
                ) : (
                  filteredCustomers.map((cust) => {
                    const limitFmt = Number(cust.credit_limit || 0).toLocaleString("vi-VN") + " đ";
                    return (
                      <tr key={cust.id || cust.code} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3.5 px-4 font-mono font-bold text-sky-700 flex items-center gap-2">
                          <Building2 className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                          <span>{cust.code}</span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-800">
                          {cust.name}
                        </td>
                        <td className="py-3.5 px-4 text-slate-500 space-y-0.5">
                          {cust.email && (
                            <div className="flex items-center gap-1.5">
                              <Mail className="w-3 h-3 text-slate-400 shrink-0" />
                              <span>{cust.email}</span>
                            </div>
                          )}
                          {cust.phone && (
                            <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                              <Phone className="w-3 h-3 text-slate-400 shrink-0" />
                              <span>{cust.phone}</span>
                            </div>
                          )}
                          {cust.address && (
                            <div className="flex items-center gap-1.5 text-slate-400 text-[11px] truncate max-w-xs" title={cust.address}>
                              <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                              <span className="truncate">{cust.address}</span>
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-right font-mono font-semibold text-slate-700">
                          {limitFmt}
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          {cust.status === "active" ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10.5px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                              Hoạt động
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
                            {/* Nút sửa (chỉ hiện khi có quyền customers:write) */}
                            {canWriteCustomer && (
                              <button
                                type="button"
                                onClick={() => openEditModal(cust)}
                                className="inline-flex items-center gap-1 text-[11px] text-slate-600 hover:text-blue-700 hover:bg-blue-50 px-2 py-1 rounded-md transition-colors cursor-pointer"
                                title="Chỉnh sửa thông tin đối tác"
                              >
                                <Pencil className="w-3 h-3" />
                                <span>Sửa</span>
                              </button>
                            )}

                            {/* Nút khóa/mở khóa */}
                            {canWriteCustomer && (
                              <button
                                type="button"
                                onClick={() => handleToggleStatus(cust)}
                                className={`inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-md transition-colors cursor-pointer ${
                                  cust.status === "active"
                                    ? "text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                    : "text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50"
                                }`}
                                title={cust.status === "active" ? "Tạm ngừng đối tác" : "Kích hoạt lại"}
                              >
                                <Ban className="w-3 h-3" />
                                <span>{cust.status === "active" ? "Khóa" : "Mở"}</span>
                              </button>
                            )}

                            <Link
                              href="/orders"
                              className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded-md transition-colors font-semibold"
                              title="Xem đơn hàng của khách này"
                            >
                              <ShoppingCart className="w-3 h-3" />
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
            <span>Hiển thị {filteredCustomers.length} / {customers.length} đối tác doanh nghiệp</span>
            <span>ERP Customer Master Data Service</span>
          </div>
        </div>
      </div>

      {/* 5. Modal Form Thêm / Chỉnh sửa Khách hàng */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white w-full max-w-lg rounded-2xl border border-slate-200 shadow-2xl overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-sky-50 text-sky-600 flex items-center justify-center font-bold">
                  {editingCustomer ? <Pencil className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">
                    {editingCustomer ? "Chỉnh sửa thông tin đối tác" : "Thêm mới đối tác khách hàng"}
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    {editingCustomer ? `Mã đối tác: ${editingCustomer.code}` : "Khởi tạo hồ sơ khách hàng mới vào ERP"}
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
                  <label className="font-semibold text-slate-700 block mb-1">Mã khách hàng *</label>
                  <input
                    type="text"
                    disabled={!!editingCustomer}
                    value={formCode}
                    onChange={(e) => setFormCode(e.target.value)}
                    placeholder="VD: CUS-0010"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500 disabled:bg-slate-100"
                    required
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Trạng thái</label>
                  <select
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                  >
                    <option value="active">Đang hoạt động</option>
                    <option value="inactive">Tạm dừng giao dịch</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Tên doanh nghiệp / Đối tác *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="VD: Công ty TNHH Giải Pháp Công Nghệ Alpha"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Email liên hệ</label>
                  <input
                    type="email"
                    value={formEmail}
                    onChange={(e) => setFormEmail(e.target.value)}
                    placeholder="contact@alpha.vn"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700 block mb-1">Số điện thoại</label>
                  <input
                    type="text"
                    value={formPhone}
                    onChange={(e) => setFormPhone(e.target.value)}
                    placeholder="0912345678"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                  />
                </div>
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Địa chỉ trụ sở / Giao hàng</label>
                <input
                  type="text"
                  value={formAddress}
                  onChange={(e) => setFormAddress(e.target.value)}
                  placeholder="Số 10 Mai Dịch, Cầu Giấy, Hà Nội"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
              </div>

              <div>
                <label className="font-semibold text-slate-700 block mb-1">
                  Hạn mức tín dụng / Công nợ (VND)
                </label>
                <input
                  type="number"
                  min="0"
                  step="1000000"
                  value={formCreditLimit}
                  onChange={(e) => setFormCreditLimit(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono focus:ring-2 focus:ring-sky-500/20 focus:border-sky-500"
                />
                <p className="text-[10.5px] text-slate-400 mt-1">
                  Hạn mức cho phép khách nợ tối đa trước khi hệ thống cảnh báo hoặc chặn lên đơn hàng.
                </p>
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
                  className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold shadow-xs transition-all cursor-pointer disabled:opacity-50"
                >
                  {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{editingCustomer ? "Lưu thay đổi" : "Tạo khách hàng"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

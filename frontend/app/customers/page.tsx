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
  ExternalLink,
  UserCheck
} from "lucide-react";
import { fetchCustomers, CustomerItem } from "@/lib/api";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadCustomers = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchCustomers();
      setCustomers(data);
    } catch (err: any) {
      setErrorMsg("Lỗi khi tải danh sách khách hàng: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, []);

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
              Danh bạ khách hàng doanh nghiệp, mã đối tác ERP và lịch sử đặt hàng
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
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
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
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

      {/* 4. Thông báo lỗi */}
      {errorMsg && (
        <div className="mx-6 mb-3 p-3 rounded-xl bg-rose-50 text-rose-800 text-xs border border-rose-200 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {/* 5. Bảng danh sách khách hàng */}
      <div className="flex-1 px-6 pb-6 overflow-hidden">
        <div className="h-full bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse">
              <thead className="bg-slate-50/80 sticky top-0 border-b border-slate-200/80 z-10 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Mã đối tác</th>
                  <th className="py-3 px-4">Tên doanh nghiệp / Đối tác</th>
                  <th className="py-3 px-4">Email liên hệ</th>
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
                      <td className="py-3.5 px-4 text-center"><div className="h-5 bg-slate-100 rounded-full w-20 mx-auto" /></td>
                      <td className="py-3.5 px-4 text-center"><div className="h-6 bg-slate-100 rounded-lg w-16 mx-auto" /></td>
                    </tr>
                  ))
                ) : filteredCustomers.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-slate-400">
                      <div className="w-12 h-12 rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                        <Users className="w-6 h-6" />
                      </div>
                      <p className="font-medium text-slate-600">Không tìm thấy khách hàng nào</p>
                      <p className="text-[11px] text-slate-400 mt-1">Vui lòng điều chỉnh lại bộ lọc hoặc từ khóa tìm kiếm</p>
                    </td>
                  </tr>
                ) : (
                  filteredCustomers.map((cust) => (
                    <tr
                      key={cust.id || cust.code}
                      className="hover:bg-slate-50/80 transition-colors"
                    >
                      <td className="py-3.5 px-4 font-mono font-bold text-sky-700 flex items-center gap-2">
                        <Building2 className="w-3.5 h-3.5 text-sky-500 shrink-0" />
                        <span>{cust.code}</span>
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-slate-800">
                        {cust.name}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500">
                        {cust.email ? (
                          <span className="flex items-center gap-1.5 font-normal">
                            <Mail className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span>{cust.email}</span>
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">Chưa cập nhật</span>
                        )}
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
                        <div className="flex items-center justify-center gap-2">
                          <Link
                            href={`/orders`}
                            className="inline-flex items-center gap-1 text-[11px] text-blue-600 hover:text-blue-800 hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors font-semibold"
                            title="Xem đơn hàng của khách này"
                          >
                            <ShoppingCart className="w-3 h-3" />
                            <span>Đơn hàng</span>
                          </Link>
                          <Link
                            href={`/copilot?q=Tạo đơn hàng nháp cho khách hàng ${cust.code}`}
                            className="inline-flex items-center gap-1 text-[11px] text-sky-600 hover:text-sky-800 hover:bg-sky-50 px-2 py-1 rounded-lg transition-colors font-semibold"
                            title="Tạo đơn hàng nháp bằng AI"
                          >
                            <Sparkles className="w-3 h-3" />
                            <span>Tạo đơn</span>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between text-xs text-slate-500">
            <span>Hiển thị {filteredCustomers.length} / {customers.length} đối tác doanh nghiệp</span>
            <span>ERP Customer Relationship Service</span>
          </div>
        </div>
      </div>
    </div>
  );
}

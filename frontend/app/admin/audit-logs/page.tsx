"use client";

import React, { useEffect, useState, useTransition } from "react";
import {
  History,
  Shield,
  ShieldCheck,
  Search,
  Filter,
  RefreshCw,
  Eye,
  AlertCircle,
  CheckCircle2,
  Lock,
  User,
  Package,
  Boxes,
  KeyRound,
  FileText,
  ChevronLeft,
  ChevronRight,
  Database,
  Calendar,
  X,
  Code,
} from "lucide-react";
import {
  AuditLogItem,
  AuditLogListResponse,
  AuditLogStatsResponse,
  fetchAuditLogsApi,
  fetchAuditLogStatsApi,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function AuditLogsPage() {
  const { user, isAdmin, hasPermission } = useAuth();
  const [isPending, startTransition] = useTransition();

  // Dữ liệu danh sách & Thống kê
  const [logsData, setLogsData] = useState<AuditLogListResponse | null>(null);
  const [statsData, setStatsData] = useState<AuditLogStatsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Bộ lọc
  const [page, setPage] = useState<number>(1);
  const [emailQuery, setEmailQuery] = useState<string>("");
  const [selectedAction, setSelectedAction] = useState<string>("");
  const [selectedResource, setSelectedResource] = useState<string>("");

  // Modal chi tiết log
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  const loadLogs = async (currentPage = page) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [logsRes, statsRes] = await Promise.all([
        fetchAuditLogsApi({
          page: currentPage,
          limit: 15,
          actor_email: emailQuery.trim() || undefined,
          action: selectedAction || undefined,
          resource_type: selectedResource || undefined,
        }),
        fetchAuditLogStatsApi().catch(() => null),
      ]);
      setLogsData(logsRes);
      if (statsRes) setStatsData(statsRes);
    } catch (err: any) {
      setErrorMsg(err.message || "Không thể tải nhật ký kiểm toán. Vui lòng thử lại sau.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs(page);
  }, [page, selectedAction, selectedResource]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadLogs(1);
  };

  const handleResetFilter = () => {
    setEmailQuery("");
    setSelectedAction("");
    setSelectedResource("");
    setPage(1);
  };

  // Helper hiển thị Badge loại hành động
  const getActionBadge = (action: string) => {
    const act = action.toUpperCase();
    if (act.includes("LOGIN")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
          <KeyRound className="w-3 h-3" />
          <span>{action}</span>
        </span>
      );
    }
    if (act.includes("USER") || act.includes("PASSWORD")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
          <User className="w-3 h-3" />
          <span>{action}</span>
        </span>
      );
    }
    if (act.includes("ROLE") || act.includes("PERMISSION")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200">
          <ShieldCheck className="w-3 h-3" />
          <span>{action}</span>
        </span>
      );
    }
    if (act.includes("DELIVER") || act.includes("ORDER")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
          <Package className="w-3 h-3" />
          <span>{action}</span>
        </span>
      );
    }
    if (act.includes("STOCK") || act.includes("ADJUST")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
          <Boxes className="w-3 h-3" />
          <span>{action}</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
        <FileText className="w-3 h-3" />
        <span>{action}</span>
      </span>
    );
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* 1. Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-indigo-600 to-blue-500 text-white flex items-center justify-center shadow-md shadow-indigo-100">
            <History className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <span>Nhật ký Kiểm toán & Truy vết Bảo mật</span>
              <span className="text-xs px-2.5 py-0.5 rounded-md font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200/70">
                Enterprise Audit Trail
              </span>
            </h1>
            <p className="text-sm text-slate-500 mt-0.5">
              Minh bạch hóa toàn bộ các hoạt động đăng nhập, phân quyền vai trò, xuất kho và thao tác dữ liệu nhạy cảm.
            </p>
          </div>
        </div>

        <button
          onClick={() => loadLogs(page)}
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition-all shadow-2xs cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-600" : "text-slate-500"}`} />
          <span>Làm mới nhật ký</span>
        </button>
      </div>

      {/* 2. Stat Metric Cards */}
      {statsData && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Tổng số bản ghi</p>
              <p className="text-2xl font-bold text-slate-900 mt-0.5">
                {statsData.total_logs.toLocaleString("vi-VN")}
              </p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Phân hệ hoạt động</p>
              <p className="text-2xl font-bold text-slate-900 mt-0.5">
                {statsData.by_resource.length} <span className="text-xs font-normal text-slate-400">modules</span>
              </p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Loại hành động</p>
              <p className="text-2xl font-bold text-slate-900 mt-0.5">
                {statsData.by_action.length} <span className="text-xs font-normal text-slate-400">actions</span>
              </p>
            </div>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200/80 shadow-2xs flex items-center gap-4">
            <div className="w-11 h-11 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
              <User className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Nhân viên thao tác nhiều nhất</p>
              <p className="text-sm font-bold text-slate-900 mt-0.5 truncate max-w-[150px]" title={statsData.top_users[0]?.email || "N/A"}>
                {statsData.top_users[0]?.email?.split("@")[0] || "Chưa có"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Filter Controls */}
      <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-2xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Tìm theo email nhân viên..."
              value={emailQuery}
              onChange={(e) => setEmailQuery(e.target.value)}
              className="w-full pl-9 pr-3.5 py-2 text-sm bg-slate-50/70 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
            />
          </div>

          <div className="md:col-span-3">
            <select
              value={selectedResource}
              onChange={(e) => {
                setSelectedResource(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 text-sm bg-slate-50/70 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-slate-700"
            >
              <option value="">Tất cả phân hệ (Resource)</option>
              <option value="auth">Xác thực & Phiên (Auth)</option>
              <option value="user">Quản lý Tài khoản (User)</option>
              <option value="role">Vai trò & Phân quyền (Role)</option>
              <option value="sales_order">Đơn hàng (Sales Order)</option>
              <option value="inventory">Kho vận (Inventory)</option>
            </select>
          </div>

          <div className="md:col-span-3">
            <select
              value={selectedAction}
              onChange={(e) => {
                setSelectedAction(e.target.value);
                setPage(1);
              }}
              className="w-full px-3 py-2 text-sm bg-slate-50/70 border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 text-slate-700"
            >
              <option value="">Tất cả hành động (Action)</option>
              <option value="AUTH_LOGIN">AUTH_LOGIN (Đăng nhập)</option>
              <option value="USER_CREATE">USER_CREATE (Tạo nhân viên)</option>
              <option value="USER_PASSWORD_RESET">USER_PASSWORD_RESET (Đổi mật khẩu)</option>
              <option value="ROLE_PERMISSIONS_UPDATE">ROLE_PERMISSIONS_UPDATE (Sửa quyền)</option>
              <option value="DELIVER_ORDER">DELIVER_ORDER (Xuất kho)</option>
              <option value="STOCK_ADJUSTMENT">STOCK_ADJUSTMENT (Kiểm kê kho)</option>
            </select>
          </div>

          <div className="md:col-span-1 flex items-center justify-end">
            {(emailQuery || selectedAction || selectedResource) && (
              <button
                type="button"
                onClick={handleResetFilter}
                className="text-xs font-semibold text-rose-600 hover:text-rose-700 hover:underline cursor-pointer"
              >
                Xóa lọc
              </button>
            )}
          </div>
        </form>
      </div>

      {/* 4. Audit Log Table */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs overflow-hidden">
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
            <p className="text-sm font-medium text-slate-500">Đang tải dữ liệu nhật ký kiểm toán...</p>
          </div>
        ) : errorMsg ? (
          <div className="p-8 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-rose-700">{errorMsg}</p>
            <button
              onClick={() => loadLogs(page)}
              className="px-4 py-1.5 text-xs font-semibold text-white bg-rose-600 rounded-lg hover:bg-rose-700 transition-colors"
            >
              Thử lại
            </button>
          </div>
        ) : !logsData || logsData.items.length === 0 ? (
          <div className="py-16 text-center space-y-2">
            <History className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-sm font-medium text-slate-600">Không có bản ghi nhật ký nào</p>
            <p className="text-xs text-slate-400">Thử thay đổi bộ lọc hoặc thực hiện các thao tác trên hệ thống.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-200/80 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Thời gian</th>
                  <th className="py-3 px-4">Người thực hiện</th>
                  <th className="py-3 px-4">Loại hành động</th>
                  <th className="py-3 px-4">Tài nguyên</th>
                  <th className="py-3 px-4">Địa chỉ IP</th>
                  <th className="py-3 px-4">Trạng thái</th>
                  <th className="py-3 px-4 text-right">Chi tiết</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {logsData.items.map((log) => {
                  const dateStr = log.created_at
                    ? new Date(log.created_at).toLocaleString("vi-VN", {
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })
                    : "N/A";

                  return (
                    <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4 whitespace-nowrap text-slate-500 font-mono text-[11.5px]">
                        {dateStr}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-600 font-bold flex items-center justify-center text-xs shrink-0">
                            {log.actor_email ? log.actor_email[0].toUpperCase() : "S"}
                          </div>
                          <div>
                            <p className="font-semibold text-slate-800 leading-tight">
                              {log.actor_email || "Hệ thống"}
                            </p>
                            <span className="text-[10px] text-slate-400 uppercase font-medium">
                              {log.actor_role || "system"}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">{getActionBadge(log.action)}</td>
                      <td className="py-3 px-4">
                        <span className="font-mono text-[11px] px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200/80">
                          {log.resource_type} #{log.resource_id.substring(0, 8)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                        {log.ip_address || "127.0.0.1"}
                      </td>
                      <td className="py-3 px-4">
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                          <span>{log.result || "SUCCESS"}</span>
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => setSelectedLog(log)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-[11.5px] font-medium text-indigo-600 hover:text-indigo-700 bg-indigo-50/80 hover:bg-indigo-100/80 rounded-lg transition-colors cursor-pointer"
                        >
                          <Eye className="w-3.5 h-3.5" />
                          <span>Xem payload</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* 5. Pagination */}
        {logsData && logsData.total_pages > 1 && (
          <div className="px-4 py-3 bg-slate-50/50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500">
            <div>
              Trang <span className="font-semibold text-slate-700">{logsData.page}</span> /{" "}
              <span className="font-semibold text-slate-700">{logsData.total_pages}</span> (Tổng{" "}
              <span className="font-semibold text-slate-700">{logsData.total}</span> bản ghi)
            </div>
            <div className="flex items-center gap-1.5">
              <button
                disabled={logsData.page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded-md border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all inline-flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Trước</span>
              </button>
              <button
                disabled={logsData.page >= logsData.total_pages || loading}
                onClick={() => setPage((p) => p + 1)}
                className="px-2.5 py-1 rounded-md border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all inline-flex items-center gap-1"
              >
                <span>Sau</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 6. Modal Chi tiết Payload Log (JSON Diff / Snapshot Viewer) */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white w-full max-w-2xl rounded-2xl border border-slate-200 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center font-bold">
                  <Code className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">Chi tiết Sự kiện Kiểm toán</h3>
                  <p className="text-xs text-slate-400 font-mono">ID: {selectedLog.id}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4 overflow-y-auto">
              <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-4 rounded-xl border border-slate-200/70">
                <div>
                  <span className="text-slate-400">Người thực hiện:</span>
                  <p className="font-semibold text-slate-800 mt-0.5">{selectedLog.actor_email}</p>
                </div>
                <div>
                  <span className="text-slate-400">Vai trò:</span>
                  <p className="font-semibold text-slate-800 mt-0.5">{selectedLog.actor_role}</p>
                </div>
                <div>
                  <span className="text-slate-400">Hành động:</span>
                  <p className="font-semibold text-slate-800 mt-0.5">{selectedLog.action}</p>
                </div>
                <div>
                  <span className="text-slate-400">Tài nguyên tác động:</span>
                  <p className="font-semibold text-slate-800 mt-0.5 font-mono">
                    {selectedLog.resource_type} #{selectedLog.resource_id}
                  </p>
                </div>
                <div>
                  <span className="text-slate-400">Địa chỉ IP:</span>
                  <p className="font-semibold text-slate-800 mt-0.5 font-mono">{selectedLog.ip_address || "N/A"}</p>
                </div>
                <div>
                  <span className="text-slate-400">Thời gian tạo:</span>
                  <p className="font-semibold text-slate-800 mt-0.5">{selectedLog.created_at}</p>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-600 mb-1.5 block">
                  Dữ liệu Payload thay đổi (JSON Snapshot):
                </label>
                <pre className="bg-slate-900 text-slate-100 p-4 rounded-xl text-xs font-mono overflow-x-auto max-h-60 leading-relaxed">
                  {selectedLog.details
                    ? JSON.stringify(selectedLog.details, null, 2)
                    : JSON.stringify({ message: "Không có dữ liệu payload chi tiết kèm theo" }, null, 2)}
                </pre>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 border-t border-slate-100 bg-slate-50/50 flex justify-end">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Đóng hộp thoại
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

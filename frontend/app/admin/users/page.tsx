"use client";

import React, { useState, useEffect } from "react";
import { 
  Users, 
  UserPlus, 
  Search, 
  Filter, 
  Shield, 
  CheckCircle2, 
  XCircle, 
  Lock, 
  Unlock, 
  Key, 
  Edit3, 
  Trash2, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight, 
  Building, 
  Briefcase, 
  Phone, 
  Mail,
  X,
  Loader2,
  AlertCircle
} from "lucide-react";
import { 
  AdminUserItem, 
  AdminRoleDetail, 
  fetchAdminUsersApi, 
  createAdminUserApi, 
  updateAdminUserApi, 
  toggleAdminUserStatusApi, 
  resetAdminUserPasswordApi, 
  deleteAdminUserApi, 
  fetchAdminRolesApi,
  CreateAdminUserPayload,
  UpdateAdminUserPayload
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/toast-provider";

export default function AdminUsersPage() {
  const { user: currentUser, isAdmin } = useAuth();
  const toast = useToast();

  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [roles, setRoles] = useState<AdminRoleDetail[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [pageSize] = useState(10);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<AdminUserItem | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);

  // Create Form State
  const [createForm, setCreateForm] = useState<CreateAdminUserPayload>({
    full_name: "",
    email: "",
    password: "",
    phone: "",
    department: "",
    job_title: "",
    role_ids: [],
    is_active: true,
  });

  // Edit Form State
  const [editForm, setEditForm] = useState<UpdateAdminUserPayload>({
    full_name: "",
    phone: "",
    department: "",
    job_title: "",
    role_ids: [],
    is_active: true,
  });

  // Load roles list for dropdowns and checkboxes
  const loadRoles = async () => {
    try {
      const data = await fetchAdminRolesApi();
      setRoles(data);
    } catch (err: any) {
      console.error("Failed to load roles", err);
    }
  };

  // Load users with filters & pagination
  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await fetchAdminUsersApi({
        page,
        page_size: pageSize,
        search: search.trim() || undefined,
        role: roleFilter !== "all" ? roleFilter : undefined,
        department: deptFilter !== "all" ? deptFilter : undefined,
        is_active: statusFilter === "all" ? undefined : statusFilter === "active",
      });
      setUsers(res.items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err: any) {
      toast.error("Không thể tải danh sách người dùng", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRoles();
  }, []);

  useEffect(() => {
    loadUsers();
  }, [page, roleFilter, deptFilter, statusFilter]);

  // Handle Search submit / debounce
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadUsers();
  };

  // Quick Lock / Unlock
  const handleToggleStatus = async (targetUser: AdminUserItem) => {
    const actionText = targetUser.is_active ? "khóa tài khoản" : "kích hoạt lại tài khoản";
    const confirmed = await toast.confirm({
      title: `Xác nhận ${actionText}`,
      message: `Bạn có chắc chắn muốn ${actionText} của nhân viên "${targetUser.full_name}" (${targetUser.email}) không? ${targetUser.is_active ? "Mọi phiên đăng nhập hiện tại sẽ bị thu hồi ngay lập tức." : ""}`,
      confirmText: targetUser.is_active ? "Khóa tài khoản" : "Kích hoạt",
      isDanger: targetUser.is_active,
    });
    if (!confirmed) return;

    try {
      await toggleAdminUserStatusApi(targetUser.id, !targetUser.is_active);
      toast.success(
        "Cập nhật trạng thái thành công",
        `Tài khoản ${targetUser.email} đã được ${targetUser.is_active ? "khóa" : "kích hoạt"}.`
      );
      loadUsers();
    } catch (err: any) {
      toast.error("Lỗi cập nhật trạng thái", err.message);
    }
  };

  // Reset Password
  const handleResetPassword = async (targetUser: AdminUserItem) => {
    const newPwd = await toast.prompt({
      title: "Đặt lại mật khẩu nhân viên",
      message: `Nhập mật khẩu mới cho tài khoản "${targetUser.full_name}" (${targetUser.email}):`,
      placeholder: "Tối thiểu 6 ký tự...",
      confirmText: "Đổi mật khẩu",
    });
    if (!newPwd) return;

    if (newPwd.trim().length < 6) {
      toast.error("Mật khẩu không hợp lệ", "Mật khẩu phải có tối thiểu 6 ký tự.");
      return;
    }

    try {
      await resetAdminUserPasswordApi(targetUser.id, newPwd.trim());
      toast.success("Đặt lại mật khẩu thành công", `Mật khẩu mới đã được cập nhật cho ${targetUser.email}.`);
    } catch (err: any) {
      toast.error("Lỗi đặt lại mật khẩu", err.message);
    }
  };

  // Delete User
  const handleDeleteUser = async (targetUser: AdminUserItem) => {
    const confirmed = await toast.confirm({
      title: "Xóa tài khoản nhân sự",
      message: `Hành động này KHÔNG THỂ HOÀN TÁC. Bạn có chắc chắn muốn xóa hoàn toàn tài khoản "${targetUser.full_name}" (${targetUser.email}) khỏi hệ thống ERP không?`,
      confirmText: "Xóa vĩnh viễn",
      isDanger: true,
    });
    if (!confirmed) return;

    try {
      await deleteAdminUserApi(targetUser.id);
      toast.success("Đã xóa tài khoản", `Tài khoản ${targetUser.email} đã được xóa thành công.`);
      loadUsers();
    } catch (err: any) {
      toast.error("Không thể xóa tài khoản", err.message);
    }
  };

  // Open Edit Modal
  const openEditModal = (targetUser: AdminUserItem) => {
    setSelectedUser(targetUser);
    setEditForm({
      full_name: targetUser.full_name,
      phone: targetUser.phone || "",
      department: targetUser.department || "",
      job_title: targetUser.job_title || "",
      role_ids: targetUser.roles.map((r) => r.id),
      is_active: targetUser.is_active,
    });
    setIsEditOpen(true);
  };

  // Submit Create User
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createForm.full_name || !createForm.email || !createForm.password) {
      toast.error("Thiếu thông tin bắt buộc", "Vui lòng nhập họ tên, email và mật khẩu khởi tạo.");
      return;
    }
    if (createForm.password.length < 6) {
      toast.error("Mật khẩu quá ngắn", "Mật khẩu phải có tối thiểu 6 ký tự.");
      return;
    }

    setActionSubmitting(true);
    try {
      await createAdminUserApi(createForm);
      toast.success("Tạo tài khoản thành công", `Đã tạo nhân viên ${createForm.full_name} (${createForm.email}).`);
      setIsCreateOpen(false);
      setCreateForm({
        full_name: "",
        email: "",
        password: "",
        phone: "",
        department: "",
        job_title: "",
        role_ids: [],
        is_active: true,
      });
      loadUsers();
    } catch (err: any) {
      toast.error("Lỗi tạo nhân viên", err.message);
    } finally {
      setActionSubmitting(false);
    }
  };

  // Submit Edit User
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUser) return;

    setActionSubmitting(true);
    try {
      await updateAdminUserApi(selectedUser.id, editForm);
      toast.success("Cập nhật thành công", `Thông tin của ${editForm.full_name} đã được lưu.`);
      setIsEditOpen(false);
      setSelectedUser(null);
      loadUsers();
    } catch (err: any) {
      toast.error("Lỗi cập nhật", err.message);
    } finally {
      setActionSubmitting(false);
    }
  };

  // Stats calculation
  const activeCount = users.filter((u) => u.is_active).length;
  const lockedCount = users.filter((u) => !u.is_active).length;
  const uniqueDepts = Array.from(new Set(users.map((u) => u.department).filter(Boolean)));

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#F8FAFC]">
      {/* 1. Header Bar */}
      <div className="p-6 border-b border-slate-200/90 bg-white shrink-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-200/60 flex items-center justify-center text-blue-600">
                <Users className="w-4 h-4" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Quản lý Nhân sự & Phân quyền
              </h1>
            </div>
            <p className="text-xs text-slate-500">
              Quản trị tài khoản nhân viên, thiết lập vai trò nghiệp vụ và kiểm soát an toàn bảo mật
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={loadUsers}
              className="p-2 border border-slate-200 hover:bg-slate-50 rounded-xl text-slate-600 transition-colors shadow-2xs"
              title="Tải lại danh sách"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-blue-600" : ""}`} />
            </button>
            <button
              type="button"
              onClick={() => setIsCreateOpen(true)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold flex items-center gap-2 shadow-sm shadow-blue-500/20 active:scale-95 transition-all cursor-pointer"
            >
              <UserPlus className="w-4 h-4" />
              <span>Thêm nhân viên mới</span>
            </button>
          </div>
        </div>

        {/* 2. KPI Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-100/60 text-blue-700 flex items-center justify-center shrink-0">
              <Users className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] font-medium text-slate-500">Tổng nhân sự</div>
              <div className="text-lg font-bold text-slate-900">{total}</div>
            </div>
          </div>

          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-100/60 text-emerald-700 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] font-medium text-slate-500">Đang hoạt động</div>
              <div className="text-lg font-bold text-emerald-700">{activeCount}</div>
            </div>
          </div>

          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-rose-100/60 text-rose-700 flex items-center justify-center shrink-0">
              <XCircle className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] font-medium text-slate-500">Đang bị khóa</div>
              <div className="text-lg font-bold text-rose-700">{lockedCount}</div>
            </div>
          </div>

          <div className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-purple-100/60 text-purple-700 flex items-center justify-center shrink-0">
              <Building className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[11px] font-medium text-slate-500">Phòng ban</div>
              <div className="text-lg font-bold text-purple-700">{uniqueDepts.length || 3}</div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Filter Bar */}
      <div className="px-6 py-3 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <form onSubmit={handleSearchSubmit} className="flex-1 min-w-[240px] max-w-md relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Tìm theo tên, email, SĐT, phòng ban..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white transition-all"
          />
        </form>

        <div className="flex flex-wrap items-center gap-2">
          {/* Role Filter */}
          <select
            value={roleFilter}
            onChange={(e) => {
              setRoleFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">Tất cả vai trò</option>
            {roles.map((r) => (
              <option key={r.id} value={r.code}>
                {r.name}
              </option>
            ))}
          </select>

          {/* Department Filter */}
          <select
            value={deptFilter}
            onChange={(e) => {
              setDeptFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">Tất cả phòng ban</option>
            {uniqueDepts.map((d) => (
              <option key={d} value={d!}>
                {d}
              </option>
            ))}
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="active">Đang hoạt động</option>
            <option value="inactive">Đang bị khóa</option>
          </select>
        </div>
      </div>

      {/* 4. Table Area */}
      <div className="flex-1 overflow-auto p-6">
        <div className="bg-white border border-slate-200/90 rounded-2xl shadow-2xs overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/75 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Nhân sự</th>
                <th className="py-3 px-4">Liên hệ</th>
                <th className="py-3 px-4">Phòng ban & Chức danh</th>
                <th className="py-3 px-4">Vai trò nghiệp vụ</th>
                <th className="py-3 px-4">Trạng thái</th>
                <th className="py-3 px-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
                    <span>Đang tải danh sách nhân sự...</span>
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-slate-400">
                    <Users className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <p className="font-semibold text-slate-600">Không tìm thấy nhân viên nào</p>
                    <p className="text-[11px] mt-0.5">Thử thay đổi bộ lọc hoặc thêm tài khoản nhân sự mới.</p>
                  </td>
                </tr>
              ) : (
                users.map((u) => {
                  const isSelf = currentUser?.id === u.id;
                  return (
                    <tr key={u.id} className="hover:bg-blue-50/30 transition-colors">
                      {/* Nhân sự: Avatar + Tên */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-2xs">
                            {u.full_name ? u.full_name.charAt(0).toUpperCase() : "U"}
                          </div>
                          <div>
                            <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                              <span>{u.full_name}</span>
                              {isSelf && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-blue-100 text-blue-700">
                                  Tôi
                                </span>
                              )}
                              {u.is_superuser && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-purple-100 text-purple-700 flex items-center gap-0.5">
                                  <Shield className="w-2.5 h-2.5" />
                                  Superuser
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-slate-400">{u.email}</div>
                          </div>
                        </div>
                      </td>

                      {/* Liên hệ */}
                      <td className="py-3.5 px-4">
                        <div className="space-y-0.5 text-[11px]">
                          <div className="flex items-center gap-1.5 text-slate-600">
                            <Phone className="w-3 h-3 text-slate-400" />
                            <span>{u.phone || "—"}</span>
                          </div>
                          <div className="flex items-center gap-1.5 text-slate-400">
                            <Mail className="w-3 h-3 text-slate-400" />
                            <span className="truncate max-w-[140px]">{u.email}</span>
                          </div>
                        </div>
                      </td>

                      {/* Phòng ban & Chức danh */}
                      <td className="py-3.5 px-4">
                        <div className="space-y-0.5 text-[11px]">
                          <div className="font-medium text-slate-800">{u.department || "Khối Nghiệp vụ"}</div>
                          <div className="text-slate-400">{u.job_title || "Chuyên viên"}</div>
                        </div>
                      </td>

                      {/* Vai trò nghiệp vụ */}
                      <td className="py-3.5 px-4">
                        <div className="flex flex-wrap gap-1">
                          {u.roles && u.roles.length > 0 ? (
                            u.roles.map((r) => (
                              <span
                                key={r.id}
                                className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${
                                  r.code === "admin"
                                    ? "bg-purple-50 text-purple-700 border-purple-200"
                                    : r.code === "director"
                                    ? "bg-amber-50 text-amber-700 border-amber-200"
                                    : r.code === "sales_manager"
                                    ? "bg-blue-50 text-blue-700 border-blue-200"
                                    : r.code === "warehouse_keeper"
                                    ? "bg-orange-50 text-orange-700 border-orange-200"
                                    : "bg-slate-50 text-slate-700 border-slate-200"
                                }`}
                              >
                                {r.name}
                              </span>
                            ))
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">Chưa phân vai trò</span>
                          )}
                        </div>
                      </td>

                      {/* Trạng thái */}
                      <td className="py-3.5 px-4">
                        {u.is_active ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                            <span>Hoạt động</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-600" />
                            <span>Đã khóa</span>
                          </span>
                        )}
                      </td>

                      {/* Thao tác */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="inline-flex items-center gap-1">
                          {/* Chỉnh sửa profile & roles */}
                          <button
                            type="button"
                            onClick={() => openEditModal(u)}
                            className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            title="Chỉnh sửa thông tin & vai trò"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>

                          {/* Reset mật khẩu */}
                          <button
                            type="button"
                            onClick={() => handleResetPassword(u)}
                            className="p-1.5 text-slate-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                            title="Đặt lại mật khẩu"
                          >
                            <Key className="w-4 h-4" />
                          </button>

                          {/* Khóa / Mở khóa (Không cho khóa chính mình) */}
                          <button
                            type="button"
                            onClick={() => handleToggleStatus(u)}
                            disabled={isSelf || u.is_superuser}
                            className={`p-1.5 rounded-lg transition-colors ${
                              isSelf || u.is_superuser
                                ? "text-slate-300 cursor-not-allowed"
                                : u.is_active
                                ? "text-slate-500 hover:text-rose-600 hover:bg-rose-50"
                                : "text-slate-500 hover:text-emerald-600 hover:bg-emerald-50"
                            }`}
                            title={
                              isSelf
                                ? "Không thể tự khóa tài khoản của chính mình"
                                : u.is_active
                                ? "Khóa tài khoản này"
                                : "Kích hoạt lại tài khoản"
                            }
                          >
                            {u.is_active ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                          </button>

                          {/* Xóa người dùng (Không xóa chính mình hoặc superuser) */}
                          <button
                            type="button"
                            onClick={() => handleDeleteUser(u)}
                            disabled={isSelf || u.is_superuser}
                            className={`p-1.5 rounded-lg transition-colors ${
                              isSelf || u.is_superuser
                                ? "text-slate-200 cursor-not-allowed"
                                : "text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                            }`}
                            title="Xóa tài khoản"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>

          {/* Pagination Footer */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-slate-200/80 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
              <div>
                Hiển thị trang <span className="font-semibold text-slate-800">{page}</span> /{" "}
                <span className="font-semibold text-slate-800">{totalPages}</span> (Tổng {total} nhân sự)
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="p-1.5 border border-slate-200 rounded-lg hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="p-1.5 border border-slate-200 rounded-lg hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ========================================================
          MODAL: THÊM NHÂN VIÊN MỚI
         ======================================================== */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden animate-in zoom-in-95 duration-150">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
                  <UserPlus className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">Thêm tài khoản nhân viên mới</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1 sm:col-span-2">
                  <label className="font-semibold text-slate-700">Họ và tên *</label>
                  <input
                    type="text"
                    required
                    placeholder="VD: Nguyễn Văn An"
                    value={createForm.full_name}
                    onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Địa chỉ Email *</label>
                  <input
                    type="email"
                    required
                    placeholder="an.nguyen@company.com"
                    value={createForm.email}
                    onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Mật khẩu khởi tạo *</label>
                  <input
                    type="password"
                    required
                    placeholder="Tối thiểu 6 ký tự"
                    value={createForm.password}
                    onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Số điện thoại</label>
                  <input
                    type="text"
                    placeholder="0912345678"
                    value={createForm.phone || ""}
                    onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Phòng ban</label>
                  <input
                    type="text"
                    placeholder="Phòng Kinh Doanh"
                    value={createForm.department || ""}
                    onChange={(e) => setCreateForm({ ...createForm, department: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1 sm:col-span-2">
                  <label className="font-semibold text-slate-700">Chức danh công việc</label>
                  <input
                    type="text"
                    placeholder="Chuyên viên kinh doanh B2B"
                    value={createForm.job_title || ""}
                    onChange={(e) => setCreateForm({ ...createForm, job_title: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>
              </div>

              {/* Roles Selection */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <label className="font-semibold text-slate-700 block">Gán vai trò nghiệp vụ (RBAC):</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {roles.map((r) => {
                    const isChecked = createForm.role_ids?.includes(r.id);
                    return (
                      <label
                        key={r.id}
                        className={`flex items-start gap-2.5 p-2.5 rounded-xl border cursor-pointer transition-all ${
                          isChecked
                            ? "bg-blue-50/70 border-blue-300 text-blue-900"
                            : "bg-slate-50 border-slate-200/80 text-slate-700 hover:bg-slate-100/60"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const newIds = e.target.checked
                              ? [...(createForm.role_ids || []), r.id]
                              : (createForm.role_ids || []).filter((id) => id !== r.id);
                            setCreateForm({ ...createForm, role_ids: newIds });
                          }}
                          className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                        />
                        <div className="text-[11px] leading-tight">
                          <div className="font-bold">{r.name}</div>
                          <div className="text-[10px] text-slate-500 line-clamp-1">{r.description || r.code}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl font-medium"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl flex items-center gap-2 shadow-sm disabled:opacity-50"
                >
                  {actionSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Tạo tài khoản</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================
          MODAL: CHỈNH SỬA THÔNG TIN & VAI TRÒ
         ======================================================== */}
      {isEditOpen && selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden animate-in zoom-in-95 duration-150">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">
                  <Edit3 className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Chỉnh sửa hồ sơ nhân sự</h3>
                  <p className="text-[11px] text-slate-400">{selectedUser.email}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsEditOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1 sm:col-span-2">
                  <label className="font-semibold text-slate-700">Họ và tên *</label>
                  <input
                    type="text"
                    required
                    value={editForm.full_name}
                    onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Số điện thoại</label>
                  <input
                    type="text"
                    value={editForm.phone || ""}
                    onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-semibold text-slate-700">Phòng ban</label>
                  <input
                    type="text"
                    value={editForm.department || ""}
                    onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>

                <div className="space-y-1 sm:col-span-2">
                  <label className="font-semibold text-slate-700">Chức danh</label>
                  <input
                    type="text"
                    value={editForm.job_title || ""}
                    onChange={(e) => setEditForm({ ...editForm, job_title: e.target.value })}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                  />
                </div>
              </div>

              {/* Roles Selection */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <label className="font-semibold text-slate-700 block">Cập nhật vai trò nghiệp vụ:</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {roles.map((r) => {
                    const isChecked = editForm.role_ids?.includes(r.id);
                    return (
                      <label
                        key={r.id}
                        className={`flex items-start gap-2.5 p-2.5 rounded-xl border cursor-pointer transition-all ${
                          isChecked
                            ? "bg-blue-50/70 border-blue-300 text-blue-900"
                            : "bg-slate-50 border-slate-200/80 text-slate-700 hover:bg-slate-100/60"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            const newIds = e.target.checked
                              ? [...(editForm.role_ids || []), r.id]
                              : (editForm.role_ids || []).filter((id) => id !== r.id);
                            setEditForm({ ...editForm, role_ids: newIds });
                          }}
                          className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                        />
                        <div className="text-[11px] leading-tight">
                          <div className="font-bold">{r.name}</div>
                          <div className="text-[10px] text-slate-500 line-clamp-1">{r.description || r.code}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsEditOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl font-medium"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={actionSubmitting}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl flex items-center gap-2 shadow-sm disabled:opacity-50"
                >
                  {actionSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Lưu thay đổi</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

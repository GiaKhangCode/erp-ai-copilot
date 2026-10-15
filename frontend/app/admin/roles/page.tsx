"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, 
  Shield, 
  Plus, 
  Save, 
  RotateCcw, 
  Check, 
  Lock, 
  AlertCircle, 
  Trash2, 
  Info,
  Loader2,
  Users,
  CheckSquare,
  Square,
  HelpCircle,
  X
} from "lucide-react";
import { 
  AdminRoleDetail, 
  AdminPermissionGroup, 
  fetchAdminRolesApi, 
  fetchAdminPermissionsApi, 
  updateAdminRolePermissionsApi, 
  createAdminRoleApi, 
  deleteAdminRoleApi 
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/toast-provider";

export default function AdminRolesPage() {
  const { isAdmin } = useAuth();
  const toast = useToast();

  const [roles, setRoles] = useState<AdminRoleDetail[]>([]);
  const [permissionGroups, setPermissionGroups] = useState<AdminPermissionGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Ma trận quyền hiện tại: roleId -> Set<permissionId>
  const [matrix, setMatrix] = useState<Record<string, Set<string>>>({});
  // Bản snapshot gốc để phát hiện thay đổi (dirty check)
  const [originalMatrix, setOriginalMatrix] = useState<Record<string, Set<string>>>({});

  // Modal tạo role mới
  const [isCreateRoleOpen, setIsCreateRoleOpen] = useState(false);
  const [newRoleCode, setNewRoleCode] = useState("");
  const [newRoleName, setNewRoleName] = useState("");
  const [newRoleDesc, setNewRoleDesc] = useState("");
  const [createRoleLoading, setCreateRoleLoading] = useState(false);

  // Load data
  const loadData = async () => {
    setLoading(true);
    try {
      const [rolesData, permsData] = await Promise.all([
        fetchAdminRolesApi(),
        fetchAdminPermissionsApi(),
      ]);
      setRoles(rolesData);
      setPermissionGroups(permsData);

      // Xây dựng ma trận
      const initialMap: Record<string, Set<string>> = {};
      rolesData.forEach((r) => {
        initialMap[r.id] = new Set(r.permissions.map((p) => p.id));
      });
      setMatrix(initialMap);

      // Clone snapshot
      const cloneSnapshot: Record<string, Set<string>> = {};
      Object.keys(initialMap).forEach((k) => {
        cloneSnapshot[k] = new Set(initialMap[k]);
      });
      setOriginalMatrix(cloneSnapshot);
    } catch (err: any) {
      toast.error("Lỗi nạp ma trận phân quyền", err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Kiểm tra có thay đổi chưa lưu không
  const hasDirtyChanges = () => {
    for (const roleId of Object.keys(matrix)) {
      const currentSet = matrix[roleId];
      const origSet = originalMatrix[roleId] || new Set();
      if (currentSet.size !== origSet.size) return true;
      for (const pId of Array.from(currentSet)) {
        if (!origSet.has(pId)) return true;
      }
    }
    return false;
  };

  // Toggle single permission checkbox
  const handleToggle = (roleId: string, permId: string, isSystemRole: boolean, roleCode: string) => {
    // Admin role luôn có toàn quyền, không cần chỉnh sửa
    if (roleCode === "admin") return;

    setMatrix((prev) => {
      const next = { ...prev };
      const rolePerms = new Set(next[roleId] || []);
      if (rolePerms.has(permId)) {
        rolePerms.delete(permId);
      } else {
        rolePerms.add(permId);
      }
      next[roleId] = rolePerms;
      return next;
    });
  };

  // Bulk toggle for a specific role and module
  const handleBulkModuleToggle = (roleId: string, roleCode: string, group: AdminPermissionGroup) => {
    if (roleCode === "admin") return;

    const groupPermIds = group.permissions.map((p) => p.id);
    const currentRolePerms = matrix[roleId] || new Set();
    const allChecked = groupPermIds.every((id) => currentRolePerms.has(id));

    setMatrix((prev) => {
      const next = { ...prev };
      const rolePerms = new Set(next[roleId] || []);
      if (allChecked) {
        groupPermIds.forEach((id) => rolePerms.delete(id));
      } else {
        groupPermIds.forEach((id) => rolePerms.add(id));
      }
      next[roleId] = rolePerms;
      return next;
    });
  };

  // Reset changes
  const handleReset = () => {
    const revert: Record<string, Set<string>> = {};
    Object.keys(originalMatrix).forEach((k) => {
      revert[k] = new Set(originalMatrix[k]);
    });
    setMatrix(revert);
    toast.info("Đã khôi phục", "Đã hủy các thay đổi chưa lưu trên ma trận phân quyền.");
  };

  // Save changes to backend
  const handleSaveChanges = async () => {
    setSaving(true);
    let successCount = 0;
    try {
      for (const r of roles) {
        if (r.code === "admin") continue; // admin giữ toàn quyền
        const currentSet = matrix[r.id] || new Set();
        const origSet = originalMatrix[r.id] || new Set();

        // Kiểm tra xem role này có thay đổi không
        let isRoleDirty = currentSet.size !== origSet.size;
        if (!isRoleDirty) {
          for (const pid of Array.from(currentSet)) {
            if (!origSet.has(pid)) {
              isRoleDirty = true;
              break;
            }
          }
        }

        if (isRoleDirty) {
          await updateAdminRolePermissionsApi(r.id, Array.from(currentSet));
          successCount++;
        }
      }

      toast.success(
        "Lưu ma trận thành công",
        `Đã cập nhật quyền hạn cho ${successCount} vai trò theo thời gian thực.`
      );
      loadData();
    } catch (err: any) {
      toast.error("Lỗi khi lưu phân quyền", err.message);
    } finally {
      setSaving(false);
    }
  };

  // Create custom role
  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoleName.trim() || !newRoleCode.trim()) {
      toast.error("Thiếu thông tin", "Vui lòng nhập tên và mã vai trò.");
      return;
    }

    setCreateRoleLoading(true);
    try {
      await createAdminRoleApi({
        code: newRoleCode.trim().toLowerCase(),
        name: newRoleName.trim(),
        description: newRoleDesc.trim() || undefined,
        permission_ids: [],
      });
      toast.success("Tạo vai trò thành công", `Vai trò "${newRoleName}" đã sẵn sàng trên ma trận.`);
      setIsCreateRoleOpen(false);
      setNewRoleCode("");
      setNewRoleName("");
      setNewRoleDesc("");
      loadData();
    } catch (err: any) {
      toast.error("Lỗi tạo vai trò", err.message);
    } finally {
      setCreateRoleLoading(false);
    }
  };

  // Delete custom role
  const handleDeleteRole = async (r: AdminRoleDetail) => {
    if (r.is_system) {
      toast.warning("Không thể xóa", "Vai trò hệ thống mặc định không được phép xóa.");
      return;
    }
    const confirmed = await toast.confirm({
      title: "Xóa vai trò tùy biến",
      message: `Bạn có chắc chắn muốn xóa vai trò "${r.name}" (${r.code}) không? Tất cả quyền hạn liên kết sẽ bị xóa.`,
      confirmText: "Xóa vai trò",
      isDanger: true,
    });
    if (!confirmed) return;

    try {
      await deleteAdminRoleApi(r.id);
      toast.success("Đã xóa vai trò", `Đã xóa vai trò "${r.name}" khỏi hệ thống.`);
      loadData();
    } catch (err: any) {
      toast.error("Lỗi xóa vai trò", err.message);
    }
  };

  const isDirty = hasDirtyChanges();

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#F8FAFC]">
      {/* 1. Header Bar */}
      <div className="p-6 border-b border-slate-200/90 bg-white shrink-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-200/60 flex items-center justify-center text-indigo-600">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                Ma trận Phân quyền & Vai trò (Permission Matrix)
              </h1>
            </div>
            <p className="text-xs text-slate-500">
              Kiểm soát phân quyền chi tiết cho 5 vai trò nghiệp vụ chính và các vai trò tùy biến theo thời gian thực
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => setIsCreateRoleOpen(true)}
              className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Tạo vai trò tùy biến</span>
            </button>

            {isDirty && (
              <button
                type="button"
                onClick={handleReset}
                disabled={saving}
                className="px-3.5 py-2 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded-xl text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Khôi phục</span>
              </button>
            )}

            <button
              type="button"
              onClick={handleSaveChanges}
              disabled={!isDirty || saving}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 shadow-sm transition-all cursor-pointer ${
                isDirty
                  ? "bg-blue-600 hover:bg-blue-700 text-white shadow-blue-500/20 active:scale-95 animate-pulse"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
              }`}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              <span>{isDirty ? "Lưu thay đổi ma trận" : "Đã đồng bộ"}</span>
            </button>
          </div>
        </div>

        {/* Thông báo chế độ Admin */}
        <div className="mt-4 p-3 rounded-xl bg-blue-50/70 border border-blue-200/60 flex items-center justify-between text-xs text-blue-900">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-600 shrink-0" />
            <span>
              <strong>Lưu ý:</strong> Vai trò <strong>Quản trị viên (Admin)</strong> sở hữu toàn bộ quyền hệ thống (*) theo mặc định. Các vai trò khác có thể linh hoạt bật/tắt quyền bằng cách tích vào ô tương ứng.
            </span>
          </div>
          {isDirty && (
            <span className="font-bold text-amber-700 bg-amber-100 px-2.5 py-0.5 rounded-full text-[11px] animate-bounce">
              Có thay đổi chưa lưu!
            </span>
          )}
        </div>
      </div>

      {/* 2. Permission Matrix Table Area */}
      <div className="flex-1 overflow-auto p-6">
        <div className="bg-white border border-slate-200/90 rounded-2xl shadow-2xs overflow-hidden min-w-[900px]">
          <table className="w-full text-left border-collapse">
            {/* Table Header: Roles Columns */}
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/90 text-[11px] font-bold text-slate-700 sticky top-0 z-10">
                <th className="py-4 px-5 w-[38%] border-r border-slate-200/80">
                  <div className="text-slate-900 font-bold uppercase tracking-wider">
                    Phân hệ nghiệp vụ & Danh mục quyền
                  </div>
                  <div className="text-[11px] font-normal text-slate-400 mt-0.5">
                    Gồm 21 quyền hạn nguyên tử
                  </div>
                </th>
                {roles.map((r) => {
                  const isAdminRole = r.code === "admin";
                  return (
                    <th key={r.id} className="py-4 px-3 text-center border-r border-slate-100 last:border-r-0 min-w-[130px]">
                      <div className="flex flex-col items-center gap-1">
                        <div className="flex items-center gap-1">
                          <span className="font-bold text-slate-900">{r.name}</span>
                          {!r.is_system && (
                            <button
                              type="button"
                              onClick={() => handleDeleteRole(r)}
                              className="text-slate-400 hover:text-rose-600 p-0.5 rounded"
                              title="Xóa vai trò tùy biến này"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                        <div className="flex items-center gap-1 text-[10px] text-slate-400 font-normal">
                          <Users className="w-3 h-3" />
                          <span>{r.user_count} nhân viên</span>
                        </div>
                        {isAdminRole && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 text-[9px] font-bold">
                            <Lock className="w-2.5 h-2.5" /> Full Root
                          </span>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>

            {/* Table Body: Grouped by Module */}
            <tbody className="divide-y divide-slate-100 text-xs">
              {loading ? (
                <tr>
                  <td colSpan={roles.length + 1} className="py-16 text-center text-slate-400">
                    <Loader2 className="w-7 h-7 animate-spin mx-auto mb-2 text-blue-600" />
                    <span>Đang tải ma trận phân quyền...</span>
                  </td>
                </tr>
              ) : (
                permissionGroups.map((group) => (
                  <React.Fragment key={group.module}>
                    {/* Module Section Header Row */}
                    <tr className="bg-slate-50/80 font-bold text-slate-800 border-t-2 border-slate-200/80">
                      <td className="py-2.5 px-5 flex items-center justify-between border-r border-slate-200/80">
                        <span className="text-[12px] uppercase tracking-wider text-blue-900 font-extrabold flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-blue-600" />
                          {group.module_name} ({group.permissions.length})
                        </span>
                      </td>
                      {roles.map((r) => {
                        const isAdminRole = r.code === "admin";
                        return (
                          <td key={r.id} className="py-2.5 px-3 text-center border-r border-slate-100 last:border-r-0">
                            {!isAdminRole && (
                              <button
                                type="button"
                                onClick={() => handleBulkModuleToggle(r.id, r.code, group)}
                                className="text-[10px] text-blue-600 hover:text-blue-800 font-semibold underline decoration-dotted cursor-pointer"
                                title="Bật/Tắt tất cả quyền trong phân hệ này"
                              >
                                Đảo chọn
                              </button>
                            )}
                          </td>
                        );
                      })}
                    </tr>

                    {/* Permissions rows within this module */}
                    {group.permissions.map((perm) => (
                      <tr key={perm.id} className="hover:bg-slate-50/50 transition-colors">
                        {/* Cột 1: Thông tin quyền */}
                        <td className="py-3 px-5 border-r border-slate-200/80">
                          <div className="font-semibold text-slate-900">{perm.name}</div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <code className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 font-mono">
                              {perm.code}
                            </code>
                            {perm.description && (
                              <span className="text-[11px] text-slate-400 line-clamp-1">{perm.description}</span>
                            )}
                          </div>
                        </td>

                        {/* Các cột Vai trò tương ứng */}
                        {roles.map((r) => {
                          const isAdminRole = r.code === "admin";
                          const isChecked = isAdminRole || Boolean(matrix[r.id]?.has(perm.id));

                          return (
                            <td
                              key={r.id}
                              onClick={() => handleToggle(r.id, perm.id, r.is_system, r.code)}
                              className={`py-3 px-3 text-center border-r border-slate-100 last:border-r-0 transition-colors ${
                                isAdminRole ? "bg-purple-50/20 cursor-not-allowed" : "cursor-pointer hover:bg-blue-50/40"
                              }`}
                            >
                              <div className="flex items-center justify-center">
                                {isAdminRole ? (
                                  <div className="w-5 h-5 rounded-md bg-purple-100 text-purple-700 flex items-center justify-center">
                                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                                  </div>
                                ) : (
                                  <div
                                    className={`w-5 h-5 rounded-md border flex items-center justify-center transition-all ${
                                      isChecked
                                        ? "bg-blue-600 border-blue-600 text-white shadow-2xs scale-105"
                                        : "bg-white border-slate-300 text-transparent hover:border-slate-400"
                                    }`}
                                  >
                                    <Check className="w-3.5 h-3.5 stroke-[3]" />
                                  </div>
                                )}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ========================================================
          MODAL: TẠO VAI TRÒ TÙY BIẾN
         ======================================================== */}
      {isCreateRoleOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden animate-in zoom-in-95 duration-150">
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center font-bold">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">Tạo vai trò tùy biến mới</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateRoleOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateRole} className="p-6 space-y-4 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Mã vai trò (Slug) *</label>
                <input
                  type="text"
                  required
                  placeholder="vd: internal_auditor, qc_lead"
                  value={newRoleCode}
                  onChange={(e) => setNewRoleCode(e.target.value.toLowerCase().replace(/\s+/g, "_"))}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white font-mono"
                />
                <p className="text-[10px] text-slate-400">Viết thường, không dấu, ngăn cách bằng dấu gạch dưới.</p>
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Tên hiển thị vai trò *</label>
                <input
                  type="text"
                  required
                  placeholder="vd: Kiểm toán viên Nội bộ"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white"
                />
              </div>

              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Mô tả trách nhiệm</label>
                <textarea
                  rows={3}
                  placeholder="Mô tả tóm tắt mục đích hoặc phân quyền của vai trò này..."
                  value={newRoleDesc}
                  onChange={(e) => setNewRoleDesc(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-500 focus:bg-white resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsCreateRoleOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-xl font-medium"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={createRoleLoading}
                  className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl flex items-center gap-2 shadow-sm disabled:opacity-50"
                >
                  {createRoleLoading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Tạo vai trò</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

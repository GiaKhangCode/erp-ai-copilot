"use client";

import React from "react";
import { useAuth } from "@/lib/auth-context";

interface PermissionGateProps {
  permission?: string | string[];
  role?: string | string[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Component kiểm soát hiển thị giao diện theo quyền hạn (RBAC / Permission Gate)
 * - Nếu không có quyền: Trả về fallback (mặc định là null - ẩn hoàn toàn)
 * - Hỗ trợ kiểm tra quyền nguyên tử (permission) hoặc vai trò (role)
 */
export function PermissionGate({
  permission,
  role,
  requireAll = false,
  fallback = null,
  children,
}: PermissionGateProps) {
  const { user, hasPermission, hasRole, isAdmin } = useAuth();

  if (!user) {
    return <>{fallback}</>;
  }

  // Quản trị cấp cao / Superuser luôn có quyền xem toàn bộ
  if (isAdmin) {
    return <>{children}</>;
  }

  // 1. Kiểm tra Permission
  if (permission) {
    const permList = Array.isArray(permission) ? permission : [permission];
    const permPassed = requireAll
      ? permList.every((p) => hasPermission(p))
      : permList.some((p) => hasPermission(p));

    if (!permPassed) {
      return <>{fallback}</>;
    }
  }

  // 2. Kiểm tra Role
  if (role) {
    const roleList = Array.isArray(role) ? role : [role];
    const rolePassed = roleList.some((r) => hasRole(r));

    if (!rolePassed) {
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}

import Link from "next/link";
import { ShieldAlert, ArrowLeft, Lock } from "lucide-react";

export function AccessDeniedView({
  permission,
  title = "Không có quyền truy cập",
  description,
}: {
  permission?: string;
  title?: string;
  description?: string;
}) {
  const { user } = useAuth();
  const roleName = user?.role || (user?.roles && user.roles.length > 0 ? user.roles[0] : "Người dùng");

  return (
    <div className="flex-1 h-full flex items-center justify-center p-6 bg-[#F8FAFC]">
      <div className="max-w-md w-full bg-white rounded-3xl border border-slate-200/90 shadow-sm p-8 text-center space-y-5">
        <div className="w-16 h-16 rounded-2xl bg-rose-50 border border-rose-100 text-rose-500 flex items-center justify-center mx-auto shadow-2xs">
          <ShieldAlert className="w-8 h-8" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-bold text-slate-900">{title}</h2>
          <p className="text-sm text-slate-500 leading-relaxed">
            {description || (
              <>
                Tài khoản của bạn với vai trò <span className="font-semibold text-slate-800">"{roleName}"</span> chưa được cấp quyền truy cập tính năng này.
              </>
            )}
          </p>
        </div>

        {permission && (
          <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 border border-slate-200 text-xs font-mono text-slate-600">
            <Lock className="w-3.5 h-3.5 text-slate-400" />
            <span>Quyền yêu cầu: {permission}</span>
          </div>
        )}

        <div className="pt-2 flex items-center justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold rounded-xl shadow-xs transition-all active:scale-95"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Quay lại Trang chủ</span>
          </Link>
        </div>
      </div>
    </div>
  );
}

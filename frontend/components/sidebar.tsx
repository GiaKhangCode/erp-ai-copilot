"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Home, 
  Sparkles, 
  Users, 
  Package, 
  ShoppingCart, 
  Warehouse, 
  BarChart2, 
  FileText, 
  CheckSquare, 
  ShoppingBag, 
  Calculator, 
  UserCheck, 
  Settings,
  ShieldCheck,
  Shield,
  History,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

interface NavItem {
  label: string;
  href: string;
  icon: any;
  badge?: number;
  permission?: string;
}

const mainNavItems: NavItem[] = [
  { label: "Trang chủ", href: "/", icon: Home },
  { label: "AI Copilot", href: "/copilot", icon: Sparkles },
  { label: "Khách hàng", href: "/customers", icon: Users, permission: "customers:read" },
  { label: "Sản phẩm", href: "/products", icon: Package, permission: "products:read" },
  { label: "Đơn hàng", href: "/orders", icon: ShoppingCart, permission: "orders:read" },
  { label: "Mua hàng (PO)", href: "/purchasing", icon: ShoppingBag, permission: "purchasing:read" },
  { label: "Tồn kho", href: "/inventory", icon: Warehouse, permission: "inventory:read" },
  { label: "Báo cáo", href: "/reports", icon: BarChart2, permission: "reports:revenue_view" },
  { label: "Tài liệu", href: "/documents", icon: FileText, permission: "documents:read" },
  { label: "Quy trình phê duyệt", href: "/approvals", icon: CheckSquare, permission: "orders:read" },
];

const adminNavItems: NavItem[] = [
  { label: "Quản lý nhân viên", href: "/admin/users", icon: Users, permission: "users:read" },
  { label: "Ma trận phân quyền", href: "/admin/roles", icon: ShieldCheck, permission: "roles:manage" },
  { label: "Nhật ký kiểm toán", href: "/admin/audit-logs", icon: History, permission: "audit:read" },
];

const secondaryNavItems: NavItem[] = [
  { label: "Kế toán", href: "/accounting", icon: Calculator },
  { label: "Nhân sự", href: "/hr", icon: UserCheck },
  { label: "Cài đặt", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { hasPermission, isAdmin } = useAuth();

  const filteredMainItems = mainNavItems.filter((item) => {
    if (!item.permission) return true;
    return isAdmin || hasPermission(item.permission);
  });

  const showAdminSection = isAdmin || hasPermission("users:read") || hasPermission("roles:manage") || hasPermission("audit:read");
  const filteredAdminItems = adminNavItems.filter((item) => {
    if (!item.permission) return true;
    return isAdmin || hasPermission(item.permission);
  });

  return (
    <aside className="w-60 bg-white border-r border-slate-200/90 flex flex-col justify-between shrink-0 h-full max-h-screen select-none overflow-hidden z-30">
      {/* 1. Brand Header cố định ở trên */}
      <div className="h-16 flex items-center px-5 gap-2.5 border-b border-slate-100 shrink-0 bg-white">
        <Link href="/" className="flex items-center gap-2">
          <img 
            src="/logo-mvp-brand.png" 
            alt="ERP AI Copilot MVP" 
            className="h-8 w-auto object-contain"
          />
        </Link>
      </div>

      {/* 2. Menu Điều hướng cuộn độc lập nếu màn hình thấp */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-4">
        {/* Main Navigation */}
        <nav className="space-y-0.5">
          {filteredMainItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
            const Icon = item.icon;

            return (
              <div key={item.href} className="space-y-0.5">
                <Link
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-xl text-[13px] font-medium transition-all duration-150",
                    isActive
                      ? "bg-blue-50/90 text-blue-600 font-semibold"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  )}
                >
                  <Icon className={cn("w-4 h-4 shrink-0", isActive ? "text-blue-600" : "text-slate-500")} />
                  <span>{item.label}</span>
                  {item.badge !== undefined && (
                    <span className="ml-auto bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full font-bold">
                      {item.badge}
                    </span>
                  )}
                </Link>

                {/* Submenu for Quy trình phê duyệt when active */}
                {item.href === "/approvals" && (pathname === "/approvals" || pathname?.startsWith("/approvals")) && (
                  <div className="pl-6 pr-2 py-1 space-y-0.5 text-[12px]">
                    <Link
                      href="/approvals?status=all"
                      className="flex items-center justify-between px-3 py-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-50"
                    >
                      <span className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                        Tất cả yêu cầu
                      </span>
                    </Link>
                    <Link
                      href="/approvals?status=pending"
                      className="flex items-center justify-between px-3 py-1.5 rounded-lg text-blue-600 font-medium bg-blue-50/60"
                    >
                      <span className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
                        Chờ phê duyệt
                      </span>
                    </Link>
                    <Link
                      href="/approvals?status=approved"
                      className="flex items-center justify-between px-3 py-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-50"
                    >
                      <span className="flex items-center gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                        Đã phê duyệt
                      </span>
                    </Link>
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Admin Navigation (chỉ hiển thị cho người có quyền quản trị) */}
        {showAdminSection && (
          <div className="pt-2 border-t border-slate-100 space-y-0.5">
            <div className="px-3 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Shield className="w-3 h-3 text-blue-600" />
              <span>Quản trị hệ thống</span>
            </div>
            {filteredAdminItems.map((item) => {
              const isActive = pathname === item.href || pathname?.startsWith(item.href);
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-xl text-[13px] font-medium transition-all duration-150",
                    isActive
                      ? "bg-blue-50/90 text-blue-600 font-semibold"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                  )}
                >
                  <Icon className={cn("w-4 h-4 shrink-0", isActive ? "text-blue-600" : "text-slate-500")} />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        )}

        {/* Secondary Navigation */}
        <div className="pt-2 border-t border-slate-100 space-y-0.5">
          <div className="px-3 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
            Phân hệ mở rộng
          </div>
          {secondaryNavItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-xl text-[13px] font-medium transition-all duration-150",
                  isActive
                    ? "bg-blue-50/90 text-blue-600 font-semibold"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                )}
              >
                <Icon className="w-4 h-4 shrink-0 text-slate-400" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </aside>
  );
}

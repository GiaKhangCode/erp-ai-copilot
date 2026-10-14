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
  Settings
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: any;
  badge?: number;
}

const mainNavItems: NavItem[] = [
  { label: "Trang chủ", href: "/", icon: Home },
  { label: "AI Copilot", href: "/copilot", icon: Sparkles },
  { label: "Khách hàng", href: "/customers", icon: Users },
  { label: "Sản phẩm", href: "/products", icon: Package },
  { label: "Đơn hàng", href: "/orders", icon: ShoppingCart },
  { label: "Tồn kho", href: "/inventory", icon: Warehouse },
  { label: "Báo cáo", href: "/reports", icon: BarChart2 },
  { label: "Tài liệu", href: "/documents", icon: FileText },
  { label: "Quy trình phê duyệt", href: "/approvals", icon: CheckSquare },
];

const secondaryNavItems: NavItem[] = [
  { label: "Mua hàng", href: "/purchasing", icon: ShoppingBag },
  { label: "Kế toán", href: "/accounting", icon: Calculator },
  { label: "Nhân sự", href: "/hr", icon: UserCheck },
  { label: "Cài đặt", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

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
          {mainNavItems.map((item) => {
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

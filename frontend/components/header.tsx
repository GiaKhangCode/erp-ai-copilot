"use client";

import { useState } from "react";
import { Search, Bell, ChevronDown, LogOut, User, Shield, Sparkles } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { OrderIngestModal } from "@/components/order-ingest-modal";
import { useToast } from "@/components/toast-provider";

export function Header() {
  const { user, logout, isAdmin, hasPermission } = useAuth();
  const toast = useToast();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [isIngestModalOpen, setIsIngestModalOpen] = useState(false);

  const getRoleDisplayName = (role?: string) => {
    switch (role) {
      case "admin":
        return "Quản trị viên";
      case "director":
        return "Ban Giám đốc";
      case "sales_manager":
        return "Quản lý kinh doanh";
      case "sales_rep":
        return "Chuyên viên kinh doanh";
      case "warehouse_keeper":
        return "Thủ kho";
      case "accountant":
        return "Kế toán viên";
      default:
        return "Thành viên";
    }
  };

  const displayName = user?.full_name || "Quản trị viên";
  const displayRole = getRoleDisplayName(user?.role);
  const showAdminLinks = isAdmin || hasPermission("users:read") || hasPermission("roles:manage");

  return (
    <header className="h-16 bg-white/95 backdrop-blur-sm border-b border-slate-200 px-6 lg:px-8 flex items-center justify-between sticky top-0 z-20 shrink-0">
      {/* Center Search Bar */}
      <div className="flex-1 max-w-xl lg:max-w-2xl mx-auto">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const input = (e.currentTarget.elements.namedItem("search") as HTMLInputElement)?.value;
            if (input?.trim()) {
              window.location.href = `/copilot?q=${encodeURIComponent(input.trim())}`;
            }
          }}
          className="relative"
        >
          <Search className="w-4 h-4 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            name="search"
            type="text"
            placeholder="Tìm kiếm trong ERP... (VD: đơn hàng, khách hàng, sản phẩm, doanh thu...)"
            className="w-full bg-slate-50 border border-slate-200/90 text-slate-900 text-[13px] rounded-full pl-11 pr-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-slate-400"
          />
        </form>
      </div>

      {/* Right Controls: Notifications & Profile */}
      <div className="flex items-center gap-3 ml-6 shrink-0 relative">
        {hasPermission("orders:create") && (
          <button
            type="button"
            onClick={() => setIsIngestModalOpen(true)}
            className="hidden md:flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-full text-xs font-semibold transition-all shadow-2xs cursor-pointer active:scale-95"
            title="Bóc tách đơn hàng tự động từ email hoặc tệp tin PDF/EML"
          >
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>Bóc tách đơn AI</span>
          </button>
        )}

        <a
          href="/approvals"
          className="relative p-2 rounded-full hover:bg-slate-100 text-slate-600 transition-colors"
          title="Thông báo phê duyệt"
        >
          <Bell className="w-5 h-5 text-slate-600" />
          <span className="w-2 h-2 bg-red-500 rounded-full absolute top-1.5 right-1.5 ring-2 ring-white" />
        </a>

        {/* User Profile Dropdown */}
        <div className="relative">
          <div
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center gap-2.5 pl-2 cursor-pointer group select-none"
          >
            <img
              src="/user-avatar.png"
              alt={displayName}
              className="w-9 h-9 rounded-full object-cover border border-slate-200/80 shadow-2xs"
            />
            <div className="hidden sm:block text-left">
              <div className="text-[13px] font-semibold text-slate-900 group-hover:text-blue-600 transition-colors leading-tight">
                {displayName}
              </div>
              <div className="text-[11px] text-slate-400">
                {displayRole}
              </div>
            </div>
            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600 transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
          </div>

          {dropdownOpen && (
            <div className="absolute right-0 mt-3 w-56 bg-white border border-slate-200 rounded-2xl shadow-xl py-2 z-50 animate-in fade-in-50 zoom-in-95 duration-100">
              <div className="px-4 py-2 border-b border-slate-100">
                <p className="text-xs font-semibold text-slate-900">{displayName}</p>
                <p className="text-[11px] text-slate-500 truncate">{user?.email || "admin@erpcopilot.vn"}</p>
                <div className="mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[10px] font-medium">
                  <Shield className="w-3 h-3" />
                  <span>{displayRole}</span>
                </div>
              </div>

              {showAdminLinks && (
                <div className="py-1 border-b border-slate-100">
                  <a
                    href="/admin/users"
                    className="block px-4 py-1.5 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                    onClick={() => setDropdownOpen(false)}
                  >
                    Quản lý nhân viên
                  </a>
                  <a
                    href="/admin/roles"
                    className="block px-4 py-1.5 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                    onClick={() => setDropdownOpen(false)}
                  >
                    Ma trận phân quyền
                  </a>
                </div>
              )}

              <div className="py-1">
                <button
                  type="button"
                  onClick={async () => {
                    setDropdownOpen(false);
                    const confirmed = await toast.confirm({
                      title: "Xác nhận đăng xuất",
                      message: "Bạn có chắc chắn muốn đăng xuất khỏi phiên làm việc hiện tại không?",
                      confirmText: "Đăng xuất",
                      isDanger: true,
                    });
                    if (!confirmed) return;
                    logout();
                    window.location.href = "/login";
                  }}
                  className="w-full text-left px-4 py-2 text-xs text-rose-600 hover:bg-rose-50 flex items-center gap-2 font-medium transition-colors cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Đăng xuất phiên làm việc</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal Bóc tách đơn hàng AI */}
      <OrderIngestModal
        isOpen={isIngestModalOpen}
        onClose={() => setIsIngestModalOpen(false)}
      />
    </header>
  );
}

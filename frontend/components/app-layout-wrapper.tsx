"use client";

import React, { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";
import { useAuth } from "@/lib/auth-context";
import { Loader2 } from "lucide-react";

export function AppLayoutWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { token, isLoading } = useAuth();
  const isLoginPage = pathname === "/login";

  useEffect(() => {
    if (isLoading) return;

    if (!token && !isLoginPage) {
      router.replace("/login");
    } else if (token && isLoginPage) {
      router.replace("/");
    }
  }, [isLoading, token, isLoginPage, router]);

  // Đang kiểm tra phiên đăng nhập từ localStorage / API
  if (isLoading) {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center bg-[#F0F6FF] gap-3 select-none">
        <div className="w-10 h-10 rounded-2xl bg-blue-600/10 flex items-center justify-center text-blue-600">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
        <p className="text-xs font-semibold text-slate-500">Đang khởi tạo phiên làm việc...</p>
      </div>
    );
  }

  // Chưa đăng nhập và đang chuyển hướng sang trang /login
  if (!token && !isLoginPage) {
    return (
      <div className="h-screen w-full flex flex-col items-center justify-center bg-[#F0F6FF] gap-3 select-none">
        <div className="w-10 h-10 rounded-2xl bg-blue-600/10 flex items-center justify-center text-blue-600">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
        <p className="text-xs font-semibold text-slate-500">Đang chuyển đến trang đăng nhập...</p>
      </div>
    );
  }

  // Đang ở trang login (chưa đăng nhập)
  if (isLoginPage) {
    return <main className="h-screen w-full overflow-hidden">{children}</main>;
  }

  // Đã đăng nhập hợp lệ -> Hiển thị toàn bộ giao diện hệ thống ERP
  return (
    <div className="flex h-screen max-h-screen w-full overflow-hidden bg-slate-50">
      {/* Cố định Sidebar bên trái */}
      <Sidebar />

      {/* Cột chính bên phải: Header cố định trên cùng, Main nội dung chiếm trọn phần còn lại */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <Header />
        <main className="flex-1 flex flex-col min-w-0 h-[calc(100vh-4rem)] overflow-hidden relative">
          {children}
        </main>
      </div>
    </div>
  );
}

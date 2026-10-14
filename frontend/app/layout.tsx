import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { Header } from "@/components/header";

export const metadata: Metadata = {
  title: "ERP AI Copilot - Trợ lý thông minh doanh nghiệp",
  description: "Hệ thống ERP Demo tích hợp Trợ lý AI hội thoại, tra cứu tồn kho, báo cáo doanh thu, RAG và bóc tách đơn hàng.",
};

import { AuthProvider } from "@/lib/auth-context";
import { AppLayoutWrapper } from "@/components/app-layout-wrapper";
import { ToastProvider } from "@/components/toast-provider";
import { ErrorBoundary } from "@/components/error-boundary";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <ErrorBoundary>
          <AuthProvider>
            <ToastProvider>
              <AppLayoutWrapper>{children}</AppLayoutWrapper>
            </ToastProvider>
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}

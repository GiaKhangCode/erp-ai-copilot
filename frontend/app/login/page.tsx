"use client";

import React, { useState } from "react";
import { 
  User, 
  Lock, 
  Eye, 
  EyeOff, 
  LogIn, 
  MessageSquare, 
  FileText, 
  Settings, 
  Globe, 
  ChevronDown, 
  BarChart2, 
  ShieldCheck, 
  Zap, 
  Home, 
  Store, 
  LayoutGrid, 
  Package, 
  Send,
  Loader2,
  AlertCircle,
  Shield
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const { login } = useAuth();

  const [email, setEmail] = useState("admin@erpcopilot.vn");
  const [password, setPassword] = useState("admin123");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const demoAccounts = [
    { role: "admin", label: "Admin", name: "Quản trị viên", email: "admin@erpcopilot.vn", pass: "admin123" },
    { role: "director", label: "Giám đốc", name: "Ban Giám đốc", email: "director@erpcopilot.vn", pass: "director123" },
    { role: "sales_manager", label: "Quản lý", name: "Quản lý kinh doanh", email: "manager@erpcopilot.vn", pass: "manager123" },
    { role: "sales_rep", label: "Kinh doanh", name: "Nhân viên kinh doanh", email: "sales@erpcopilot.vn", pass: "sales123" },
    { role: "warehouse_keeper", label: "Thủ kho", name: "Quản lý kho hàng", email: "warehouse@erpcopilot.vn", pass: "warehouse123" },
  ];

  const handleSelectDemo = (dEmail: string, dPass: string) => {
    setEmail(dEmail);
    setPassword(dPass);
    setErrorMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setErrorMessage("Vui lòng nhập đầy đủ email và mật khẩu.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      await login(email.trim(), password.trim());
      const searchParams = new URLSearchParams(window.location.search);
      const returnUrl = searchParams.get("returnUrl") || "/";
      window.location.href = returnUrl;
    } catch (err: any) {
      setErrorMessage(err.message || "Email hoặc mật khẩu không chính xác.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-screen max-h-screen w-full flex flex-col lg:flex-row bg-[#F0F6FF] text-slate-900 overflow-y-auto lg:overflow-hidden select-none">
      {/* ========================================================
          CỘT TRÁI (58%): Giới thiệu & Mockup Cửa sổ ERP Copilot
         ======================================================== */}
      <section className="w-full lg:w-[58%] bg-gradient-to-br from-[#F6F9FF] via-[#EEF5FF] to-[#DFEEFD] p-6 lg:px-10 lg:py-7 xl:px-12 xl:py-8 flex flex-col justify-between relative overflow-hidden border-r border-blue-100/80 shrink-0">
        {/* Quầng sáng trang trí nền */}
        <div className="absolute -top-32 -left-32 w-80 h-80 bg-blue-400/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 -right-32 w-80 h-80 bg-sky-300/15 rounded-full blur-3xl pointer-events-none" />

        {/* 1. Header Brand cột trái */}
        <div className="flex items-center gap-2 z-10 shrink-0">
          <img
            src="/login-logo.png"
            alt="ERP AI Copilot Logo"
            className="w-7 h-7 rounded-lg shadow-sm shadow-blue-500/20 object-contain"
          />
          <span className="font-extrabold text-base text-slate-900 tracking-tight">
            ERP AI <span className="text-[#0066FF]">Copilot</span>
          </span>
        </div>

        {/* 2. Tiêu đề lớn & Mockup preview */}
        <div className="my-auto py-2 xl:py-3 space-y-4 xl:space-y-5 z-10 max-w-xl">
          <div className="space-y-1.5">
            <h1 className="text-2xl sm:text-3xl xl:text-[34px] font-extrabold tracking-tight text-slate-900 leading-[1.18]">
              Trợ lý AI thông minh <br />
              cho hệ thống ERP của bạn
            </h1>
            <p className="text-slate-500 text-[11.5px] xl:text-[12.5px] leading-relaxed max-w-lg">
              Tự động hóa quy trình, tìm kiếm thông tin, phân tích dữ liệu và hỗ trợ ra quyết định nhanh chóng, chính xác.
            </p>
          </div>

          {/* 3 Khối tính năng nhỏ */}
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <div className="w-7 h-7 rounded-full bg-blue-100/80 text-blue-600 flex items-center justify-center">
                <MessageSquare className="w-3.5 h-3.5" />
              </div>
              <h3 className="text-[11.5px] font-bold text-slate-900">
                Hỏi đáp thông minh
              </h3>
              <p className="text-[10px] text-slate-500 leading-snug">
                Về khách hàng, sản phẩm, đơn hàng, tồn kho...
              </p>
            </div>

            <div className="space-y-1">
              <div className="w-7 h-7 rounded-full bg-blue-100/80 text-blue-600 flex items-center justify-center">
                <FileText className="w-3.5 h-3.5" />
              </div>
              <h3 className="text-[11.5px] font-bold text-slate-900">
                Xử lý tài liệu
              </h3>
              <p className="text-[10px] text-slate-500 leading-snug">
                Đọc email, báo cáo, phản hồi khách hàng...
              </p>
            </div>

            <div className="space-y-1">
              <div className="w-7 h-7 rounded-full bg-blue-100/80 text-blue-600 flex items-center justify-center">
                <Settings className="w-3.5 h-3.5" />
              </div>
              <h3 className="text-[11.5px] font-bold text-slate-900">
                Tự động hóa
              </h3>
              <p className="text-[10px] text-slate-500 leading-snug">
                Tạo đơn hàng, cập nhật dữ liệu, kiểm tra tồn kho...
              </p>
            </div>
          </div>

          {/* 3. Mockup Cửa sổ ERP Copilot Preview (Theo đúng ảnh gốc 100%) */}
          <div className="relative pt-1 max-w-[500px]">
            <div className="bg-white rounded-2xl border border-blue-100 shadow-xl shadow-blue-500/10 flex overflow-hidden">
              {/* Menu dọc màu xanh đậm bên trái */}
              <div className="w-9 bg-[#0066FF] flex flex-col items-center py-3 space-y-3 shrink-0 text-white/80">
                <Home className="w-3 h-3 text-white" />
                <Store className="w-3 h-3" />
                <LayoutGrid className="w-3 h-3" />
                <FileText className="w-3 h-3" />
                <Package className="w-3 h-3" />
                <Settings className="w-3 h-3 mt-auto" />
              </div>

              {/* Nội dung Chat bên trong Mockup */}
              <div className="flex-1 p-3 space-y-2 bg-white overflow-hidden">
                {/* Câu hỏi của người dùng */}
                <div className="flex justify-end">
                  <div className="bg-[#EBF3FF] text-[#1D39C4] px-3 py-1 rounded-2xl rounded-br-none text-[10.5px] font-medium shadow-2xs max-w-[260px]">
                    Cho tôi biết tồn kho sản phẩm SKU-001 hiện có bao nhiêu?
                  </div>
                </div>

                {/* Trả lời của AI Assistant kèm bảng tồn kho */}
                <div className="flex items-start gap-2">
                  <img
                    src="/login-logo.png"
                    alt="AI"
                    className="w-5 h-5 rounded-md shrink-0 mt-0.5 object-contain"
                  />
                  <div className="space-y-1.5 flex-1 text-[10.5px] text-slate-700 min-w-0">
                    <p className="leading-snug">
                      Sản phẩm <span className="font-semibold text-slate-900">SKU-001 (Laptop Dell Inspiron 15)</span> hiện có <span className="font-bold text-emerald-600">120 đơn vị khả dụng</span> tại kho Hà Nội.
                    </p>
                    <div className="text-[9.5px] text-slate-500 font-medium">
                      Chi tiết tồn kho:
                    </div>

                    {/* Bảng chi tiết tồn kho 3 miền */}
                    <div className="border border-slate-100 rounded-lg overflow-hidden text-[9.5px] w-full">
                      <table className="w-full text-left">
                        <thead className="bg-[#F8FAFC] text-slate-400 font-medium border-b border-slate-100">
                          <tr>
                            <th className="py-0.5 px-2">Kho hàng</th>
                            <th className="py-0.5 px-1.5 text-center">Tồn kho</th>
                            <th className="py-0.5 px-1.5 text-center">Đang giữ</th>
                            <th className="py-0.5 px-1.5 text-center font-bold text-emerald-600">Khả dụng</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 text-slate-700">
                          <tr>
                            <td className="py-0.5 px-2 font-medium">Hà Nội</td>
                            <td className="py-0.5 px-1.5 text-center">150</td>
                            <td className="py-0.5 px-1.5 text-center">30</td>
                            <td className="py-0.5 px-1.5 text-center font-bold text-emerald-600">120</td>
                          </tr>
                          <tr>
                            <td className="py-0.5 px-2 font-medium">Đà Nẵng</td>
                            <td className="py-0.5 px-1.5 text-center">80</td>
                            <td className="py-0.5 px-1.5 text-center">10</td>
                            <td className="py-0.5 px-1.5 text-center font-bold text-emerald-600">70</td>
                          </tr>
                          <tr>
                            <td className="py-0.5 px-2 font-medium">Hồ Chí Minh</td>
                            <td className="py-0.5 px-1.5 text-center">60</td>
                            <td className="py-0.5 px-1.5 text-center">5</td>
                            <td className="py-0.5 px-1.5 text-center font-bold text-emerald-600">55</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div className="flex items-center justify-between text-[9px] text-slate-400 pt-0.5">
                      <span className="flex items-center gap-1">
                        📄 Nguồn: Báo cáo tồn kho tháng 9/2025.pdf
                      </span>
                      <span>Trang 3</span>
                    </div>
                  </div>
                </div>

                {/* Thanh nhập liệu chat mini */}
                <div>
                  <div className="bg-[#F8FAFC] border border-slate-200/90 rounded-full px-2.5 py-1 flex items-center justify-between">
                    <span className="text-[10px] text-slate-400">Hỏi ERP AI Copilot...</span>
                    <div className="w-3.5 h-3.5 rounded-full bg-[#0066FF] flex items-center justify-center text-white">
                      <Send className="w-2 h-2" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 3 Thẻ tính năng nổi bên phải cửa sổ */}
            <div className="absolute -right-8 top-1 space-y-1.5 z-20 hidden 2xl:block">
              <div className="bg-white/95 backdrop-blur border border-blue-100 rounded-xl px-2.5 py-1 shadow-md flex items-center gap-1.5 text-[10px] font-semibold text-slate-800">
                <BarChart2 className="w-3 h-3 text-blue-600" />
                <span>Tăng hiệu suất làm việc</span>
              </div>
              <div className="bg-white/95 backdrop-blur border border-blue-100 rounded-xl px-2.5 py-1 shadow-md flex items-center gap-1.5 text-[10px] font-semibold text-slate-800">
                <ShieldCheck className="w-3 h-3 text-blue-600" />
                <span>Bảo mật & kiểm soát</span>
              </div>
              <div className="bg-white/95 backdrop-blur border border-blue-100 rounded-xl px-2.5 py-1 shadow-md flex items-center gap-1.5 text-[10px] font-semibold text-slate-800">
                <Zap className="w-3 h-3 text-blue-600" />
                <span>Dễ dàng sử dụng</span>
              </div>
            </div>

            {/* Linh vật Mascot Robot AI */}
            <div className="absolute -bottom-6 -right-6 w-24 h-24 z-30 pointer-events-none hidden 2xl:block">
              <img
                src="/login-robot.png"
                alt="AI Robot Mascot"
                className="w-full h-full object-contain drop-shadow-xl"
              />
            </div>
          </div>
        </div>

        {/* 4. Testimonial trích dẫn */}
        <div className="pt-2 space-y-0.5 z-10 border-t border-blue-100/60 shrink-0">
          <p className="text-[11px] text-slate-600 italic">
            “ERP AI Copilot giúp chúng tôi tiết kiệm thời gian, giảm lỗi nhập liệu và nâng cao trải nghiệm khách hàng.”
          </p>
          <p className="text-[10px] text-slate-400 font-medium">
            — Bộ phận Kinh doanh
          </p>
        </div>
      </section>

      {/* ========================================================
          CỘT PHẢI (42%): Màn hình Form Đăng nhập
         ======================================================== */}
      <section className="w-full lg:w-[42%] bg-white p-6 lg:px-10 lg:py-6 xl:px-12 xl:py-7 flex flex-col justify-between shadow-2xl shadow-slate-900/5 shrink-0 overflow-y-auto">
        {/* Nút chọn ngôn ngữ góc trên phải */}
        <div className="flex justify-end shrink-0">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl border border-slate-200 text-[11px] text-slate-700 bg-white hover:bg-slate-50 cursor-pointer shadow-2xs transition-colors">
            <Globe className="w-3 h-3 text-slate-500" />
            <span>Tiếng Việt</span>
            <ChevronDown className="w-2.5 h-2.5 text-slate-400" />
          </div>
        </div>

        {/* Trung tâm: Form đăng nhập */}
        <div className="max-w-sm w-full mx-auto my-auto py-2 space-y-4">
          {/* Logo & Tiêu đề */}
          <div className="text-center space-y-1">
            <div className="inline-block p-1 bg-white rounded-xl shadow-md shadow-blue-500/10">
              <img
                src="/login-logo.png"
                alt="ERP AI Copilot"
                className="w-11 h-11 object-contain rounded-lg"
              />
            </div>
            <h2 className="text-xl font-extrabold text-slate-900 tracking-tight">
              ERP AI <span className="text-[#0066FF]">Copilot</span>
            </h2>
            <p className="text-[11.5px] text-slate-400">
              Đăng nhập để bắt đầu hành trình thông minh
            </p>
          </div>

          {/* Alert thông báo lỗi nếu có */}
          {errorMessage && (
            <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-[11px] flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 text-rose-600" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Form nhập tài khoản */}
          <form onSubmit={handleSubmit} className="space-y-3">
            {/* Trường Email hoặc Username */}
            <div className="space-y-1">
              <label className="text-[11.5px] font-semibold text-slate-800">
                Email hoặc tên đăng nhập
              </label>
              <div className="relative">
                <User className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Nhập email hoặc tên đăng nhập"
                  required
                  className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                />
              </div>
            </div>

            {/* Trường Mật khẩu */}
            <div className="space-y-1">
              <label className="text-[11.5px] font-semibold text-slate-800">
                Mật khẩu
              </label>
              <div className="relative">
                <Lock className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Nhập mật khẩu"
                  required
                  className="w-full bg-white border border-slate-200 rounded-xl pl-9 pr-9 py-2 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Checkbox Ghi nhớ & Quên mật khẩu */}
            <div className="flex items-center justify-between text-[11px] pt-0.5">
              <label className="flex items-center gap-1.5 text-slate-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3 h-3 cursor-pointer"
                />
                <span>Ghi nhớ đăng nhập</span>
              </label>
              <a href="#" className="text-blue-600 hover:text-blue-700 font-medium">
                Quên mật khẩu?
              </a>
            </div>

            {/* Nút Đăng nhập chính */}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#0066FF] hover:bg-blue-700 text-white font-semibold text-xs py-2.5 rounded-xl transition-all shadow-md shadow-blue-600/20 flex items-center justify-center gap-2 active:scale-98 cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <LogIn className="w-3.5 h-3.5" />
              )}
              <span>Đăng nhập</span>
            </button>
          </form>

          {/* Divider "Hoặc" */}
          <div className="relative flex items-center justify-center my-2">
            <div className="border-t border-slate-200 w-full" />
            <span className="bg-white px-2.5 text-slate-400 text-[11px]">Hoặc</span>
          </div>

          {/* Đăng nhập với Microsoft */}
          <button
            type="button"
            onClick={() => handleSelectDemo("admin@erpcopilot.vn", "admin123")}
            className="w-full bg-white hover:bg-slate-50 border border-slate-200 rounded-xl py-2 px-3 text-[11.5px] font-semibold text-slate-700 flex items-center justify-center gap-2 shadow-2xs transition-colors cursor-pointer"
          >
            <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 21 21">
              <rect x="1" y="1" width="9" height="9" fill="#f25022" />
              <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
              <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
              <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
            </svg>
            <span>Đăng nhập với Microsoft</span>
          </button>

          {/* Chọn nhanh tài khoản Demo (Pills dạng tab gọn nhẹ không chiếm chỗ) */}
          <div className="pt-1 space-y-1.5">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center">
              Chọn nhanh tài khoản Demo để kiểm thử
            </div>
            <div className="grid grid-cols-4 gap-1.5">
              {demoAccounts.map((d, i) => {
                const isSelected = email === d.email;
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSelectDemo(d.email, d.pass)}
                    title={`${d.name} (${d.email})`}
                    className={`py-1 px-1.5 rounded-lg border text-center transition-all cursor-pointer ${
                      isSelected
                        ? "border-blue-500 bg-blue-50 text-blue-700 font-bold shadow-2xs"
                        : "border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-600 font-medium"
                    }`}
                  >
                    <div className="text-[10px] truncate">{d.label}</div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-[11px] text-slate-500 pt-2 shrink-0">
          Chưa có tài khoản?{" "}
          <a href="mailto:admin@erpcopilot.vn" className="text-blue-600 hover:text-blue-700 font-semibold">
            Liên hệ quản trị viên
          </a>
        </div>
      </section>
    </div>
  );
}

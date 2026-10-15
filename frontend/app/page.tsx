"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Sparkles,
  Send,
  Mic,
  BarChart2,
  FileText,
  Cog,
  Lightbulb,
  DollarSign,
  Package,
  ShoppingCart,
  TrendingUp,
  ArrowRight,
  Users,
  Loader2,
} from "lucide-react";
import { formatVND, formatNumber } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import {
  fetchRevenueReport,
  fetchInventory,
  fetchOrders,
  fetchCustomers,
  RevenueReportData,
  InventoryItem,
  SalesOrderItem,
  CustomerItem,
} from "@/lib/api";

const promptChips = [
  "Doanh thu tháng này là bao nhiêu?",
  "Tồn kho sản phẩm SKU-001 còn bao nhiêu?",
  "Tạo đơn hàng nháp cho Công ty TNHH ABC",
  "Báo cáo phân tích doanh thu cả năm 2026",
];

const featureCards = [
  {
    title: "Tóm tắt báo cáo",
    description:
      "Nhận bản tóm tắt nhanh chóng về hiệu suất kinh doanh, tài chính, tồn kho...",
    icon: BarChart2,
    iconColor: "text-blue-500",
    bgColor: "bg-blue-50",
    href: "/reports",
  },
  {
    title: "Truy vấn dữ liệu",
    description:
      "Hỏi đáp trực tiếp về dữ liệu ERP và chính sách tài liệu qua ngôn ngữ tự nhiên.",
    icon: FileText,
    iconColor: "text-emerald-500",
    bgColor: "bg-emerald-50",
    href: "/copilot",
  },
  {
    title: "Tự động hóa tác vụ",
    description:
      "Bóc tách đơn hàng từ email, trích xuất dữ liệu và phê duyệt đơn nháp.",
    icon: Cog,
    iconColor: "text-purple-500",
    bgColor: "bg-purple-50",
    href: "/approvals",
  },
  {
    title: "Kiểm soát tồn kho",
    description:
      "Tra cứu tồn kho thời gian thực, số lượng khả dụng và cảnh báo thiếu hàng.",
    icon: Lightbulb,
    iconColor: "text-amber-500",
    bgColor: "bg-amber-50",
    href: "/inventory",
  },
];

export default function HomePage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  // Real KPI metrics state
  const [revenueData, setRevenueData] = useState<RevenueReportData | null>(
    null,
  );
  const [totalInventory, setTotalInventory] = useState<{
    onHand: number;
    available: number;
  }>({ onHand: 0, available: 0 });
  const [orderCount, setOrderCount] = useState<number>(0);
  const [customerCount, setCustomerCount] = useState<number>(0);

  useEffect(() => {
    async function loadDashboardKpis() {
      setLoading(true);
      try {
        const [revRes, invRes, ordersRes, custRes] = await Promise.allSettled([
          fetchRevenueReport(),
          fetchInventory(),
          fetchOrders({ limit: 100 }),
          fetchCustomers({ limit: 100 }),
        ]);

        if (revRes.status === "fulfilled") {
          setRevenueData(revRes.value);
        }
        if (invRes.status === "fulfilled") {
          const invList = invRes.value;
          const onHand = invList.reduce(
            (acc, it) => acc + (it.quantity_on_hand || 0),
            0,
          );
          const available = invList.reduce(
            (acc, it) => acc + (it.quantity_available || 0),
            0,
          );
          setTotalInventory({ onHand, available });
        }
        if (ordersRes.status === "fulfilled") {
          setOrderCount(ordersRes.value.length);
        }
        if (custRes.status === "fulfilled") {
          setCustomerCount(custRes.value.length);
        }
      } catch (err) {
        console.error("Lỗi nạp KPI dashboard:", err);
      } finally {
        setLoading(false);
      }
    }

    loadDashboardKpis();
  }, []);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Tự động co giãn chiều cao của ô nhập prompt theo nội dung
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      if (query) {
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
      }
    }
  }, [query]);

  const handleChipClick = (prompt: string) => {
    setQuery(prompt);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const handleSendMessage = () => {
    if (!query.trim()) return;
    window.location.href = `/copilot?q=${encodeURIComponent(query.trim())}`;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter") {
      if (!e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      } else {
        requestAnimationFrame(() => {
          if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
          }
        });
      }
    }
  };

  // Lấy tên hiển thị chào mừng
  const firstName = user?.full_name ? user.full_name.split(" ").pop() : "bạn";

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-[#F8FAFC]">
      <div className="max-w-6xl mx-auto space-y-10 py-4">
        {/* 1. Hero Welcome Section */}
        <div className="text-center space-y-3 pt-4">
          <h1 className="text-4xl font-extrabold tracking-tight text-slate-900">
            Chào bạn, {firstName}!
          </h1>
          <p className="text-slate-600 max-w-xl mx-auto text-base">
            Tôi là ERP AI Copilot – trợ lý thông minh giúp bạn tra cứu, phân
            tích dữ liệu và thực hiện các tác vụ ERP nhanh chóng, dễ dàng hơn.
          </p>
        </div>

        {/* 2. Hero AI Chat Input Box */}
        <div className="max-w-3xl mx-auto space-y-4">
          <form
            onSubmit={handleSubmit}
            className="relative bg-white border border-slate-200/90 rounded-2xl md:rounded-3xl shadow-lg shadow-blue-500/5 hover:border-slate-300 focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-500/10 transition-all p-3 sm:p-3.5 pl-4 sm:pl-5 flex flex-col gap-2.5"
          >
            {/* Top Textarea Row */}
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-blue-500 shrink-0 mt-1" />
              <textarea
                ref={textareaRef}
                rows={1}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Hỏi tôi bất cứ điều gì về ERP (VD: doanh thu tháng, tồn kho SKU, tạo đơn hàng...)"
                className="w-full bg-transparent text-slate-900 placeholder:text-slate-400 text-sm sm:text-base focus:outline-none resize-none leading-relaxed min-h-[28px] max-h-44 py-0.5 overflow-y-auto"
              />
            </div>

            {/* Bottom Actions Row */}
            <div className="flex items-center justify-end pt-2 border-t border-slate-100/90">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors cursor-pointer"
                  title="Nhập giọng nói"
                >
                  <Mic className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>
                <button
                  type="submit"
                  disabled={!query.trim()}
                  title="Gửi"
                  className={`w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shadow-md transition-all shrink-0 active:scale-95 cursor-pointer ${
                    query.trim()
                      ? "bg-blue-600 hover:bg-blue-700 text-white shadow-blue-600/20"
                      : "bg-slate-100 text-slate-400 cursor-not-allowed shadow-none"
                  }`}
                >
                  <Send className="w-4 h-4 sm:w-4.5 sm:h-4.5" />
                </button>
              </div>
            </div>
          </form>

          {/* Prompt Chips */}
          <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
            {promptChips.map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleChipClick(chip)}
                className="bg-sky-50/70 hover:bg-sky-100/70 text-sky-800 text-xs px-3.5 py-1.5 rounded-full border border-sky-100 transition-colors font-medium cursor-pointer"
              >
                {chip}
              </button>
            ))}
          </div>
        </div>

        {/* 3. Four Feature Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {featureCards.map((card, idx) => {
            const Icon = card.icon;
            return (
              <Link
                key={idx}
                href={card.href}
                className="bg-white border border-slate-200/90 rounded-2xl p-5 hover:border-blue-400 hover:shadow-md transition-all duration-200 group flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div
                    className={`w-10 h-10 rounded-xl ${card.bgColor} flex items-center justify-center`}
                  >
                    <Icon className={`w-5 h-5 ${card.iconColor}`} />
                  </div>
                  <h3 className="font-bold text-slate-900 text-base group-hover:text-blue-600 transition-colors">
                    {card.title}
                  </h3>
                  <p className="text-slate-500 text-xs leading-relaxed">
                    {card.description}
                  </p>
                </div>
                <div className="pt-4 flex items-center text-blue-600 text-xs font-semibold group-hover:translate-x-1 transition-transform">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </Link>
            );
          })}
        </div>

        {/* 4. KPI Metrics Cards (100% Real Database Data) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                Tổng quan ERP thời gian thực
              </h2>
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Đồng bộ trực tiếp
              </span>
            </div>
            <Link
              href="/reports"
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
            >
              <span>Xem báo cáo chi tiết</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* KPI 1: Doanh thu */}
            <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-blue-50 flex items-center justify-center">
                  <DollarSign className="w-4.5 h-4.5 text-blue-600" />
                </div>
                <span className="text-xs font-medium text-slate-500">
                  Doanh thu ghi nhận
                </span>
              </div>
              <div className="space-y-1">
                {loading ? (
                  <div className="h-7 w-32 bg-slate-100 rounded animate-pulse" />
                ) : (
                  <div className="text-xl font-extrabold text-slate-900">
                    {revenueData?.total_revenue
                      ? formatVND(Number(revenueData.total_revenue))
                      : "0 đ"}
                  </div>
                )}
                <div className="text-xs font-medium text-emerald-600">
                  {revenueData?.total_orders
                    ? `${revenueData.total_orders} đơn đã đối chiếu`
                    : "Chưa có đơn hoàn tất"}
                </div>
              </div>
            </div>

            {/* KPI 2: Tồn kho khả dụng */}
            <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 flex items-center justify-center">
                  <Package className="w-4.5 h-4.5 text-emerald-600" />
                </div>
                <span className="text-xs font-medium text-slate-500">
                  Tồn kho khả dụng
                </span>
              </div>
              <div className="space-y-1">
                {loading ? (
                  <div className="h-7 w-32 bg-slate-100 rounded animate-pulse" />
                ) : (
                  <div className="text-xl font-extrabold text-slate-900">
                    {formatNumber(totalInventory.available)} SP
                  </div>
                )}
                <div className="text-xs font-medium text-slate-500">
                  Tổng tồn: {formatNumber(totalInventory.onHand)} sản phẩm
                </div>
              </div>
            </div>

            {/* KPI 3: Đơn hàng */}
            <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-purple-50 flex items-center justify-center">
                  <ShoppingCart className="w-4.5 h-4.5 text-purple-600" />
                </div>
                <span className="text-xs font-medium text-slate-500">
                  Đơn hàng hệ thống
                </span>
              </div>
              <div className="space-y-1">
                {loading ? (
                  <div className="h-7 w-32 bg-slate-100 rounded animate-pulse" />
                ) : (
                  <div className="text-xl font-extrabold text-slate-900">
                    {formatNumber(orderCount)} đơn
                  </div>
                )}
                <div className="text-xs font-medium text-blue-600">
                  Quản lý & phê duyệt tức thì
                </div>
              </div>
            </div>

            {/* KPI 4: Khách hàng */}
            <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-amber-50 flex items-center justify-center">
                  <Users className="w-4.5 h-4.5 text-amber-600" />
                </div>
                <span className="text-xs font-medium text-slate-500">
                  Khách hàng đối tác
                </span>
              </div>
              <div className="space-y-1">
                {loading ? (
                  <div className="h-7 w-32 bg-slate-100 rounded animate-pulse" />
                ) : (
                  <div className="text-xl font-extrabold text-slate-900">
                    {formatNumber(customerCount)} đối tác
                  </div>
                )}
                <div className="text-xs font-medium text-emerald-600">
                  Đang hoạt động trong ERP
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 5. Bottom Hero Banner */}
        <div className="relative w-full overflow-hidden rounded-2xl shadow-md hover:shadow-xl hover:shadow-blue-500/15 cursor-pointer transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0">
          <Link href="/copilot" className="block relative w-full">
            <img
              src="/hero-banner.png"
              alt="ERP AI Copilot - Thông minh hơn. Nhanh hơn. Hiệu quả hơn."
              className="w-full h-auto object-cover rounded-2xl select-none"
            />
          </Link>
        </div>
      </div>
    </div>
  );
}

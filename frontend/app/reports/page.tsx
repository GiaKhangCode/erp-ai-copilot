"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { 
  BarChart2, 
  TrendingUp, 
  Calendar, 
  RefreshCw, 
  Sparkles, 
  DollarSign, 
  ShoppingBag, 
  Award,
  Layers,
  ArrowUpRight,
  Trophy,
  CreditCard,
  PieChart,
  Users,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ArrowDownRight,
  ShieldAlert
} from "lucide-react";
import { 
  fetchRevenueReport, 
  fetchSalesLeaderboardApi,
  fetchFinancialProfitabilityApi,
  fetchDebtAgingApi,
  RevenueReportData,
  SalesLeaderboardResponse,
  FinancialProfitabilityResponse,
  DebtAgingReportResponse
} from "@/lib/api";
import { formatVND } from "@/lib/utils";
import { PermissionGate, AccessDeniedView } from "@/components/permission-gate";

export default function ReportsPage() {
  return (
    <PermissionGate
      permission="reports:revenue_view"
      fallback={
        <AccessDeniedView
          permission="reports:revenue_view"
          title="Báo cáo & Phân tích Doanh nghiệp"
          description="Tài khoản của bạn không được phân quyền xem báo cáo tài chính, lợi nhuận và xếp hạng kinh doanh."
        />
      }
    >
      <ReportsContent />
    </PermissionGate>
  );
}

type TabType = "revenue_profit" | "sales_leaderboard" | "debt_aging";

function ReportsContent() {
  const [activeTab, setActiveTab] = useState<TabType>("revenue_profit");
  const [selectedYear, setSelectedYear] = useState<number>(2026);
  const [selectedMonth, setSelectedMonth] = useState<string>("all");
  
  // Data states
  const [revenueData, setRevenueData] = useState<RevenueReportData | null>(null);
  const [profitData, setProfitData] = useState<FinancialProfitabilityResponse | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<SalesLeaderboardResponse | null>(null);
  const [debtData, setDebtData] = useState<DebtAgingReportResponse | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadAllReports = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const monthVal = selectedMonth === "all" ? undefined : parseInt(selectedMonth, 10);
      
      const [revRes, profitRes, leadRes, debtRes] = await Promise.allSettled([
        fetchRevenueReport(selectedYear, monthVal),
        fetchFinancialProfitabilityApi(selectedYear, monthVal),
        fetchSalesLeaderboardApi(selectedYear, monthVal),
        fetchDebtAgingApi(),
      ]);

      if (revRes.status === "fulfilled") setRevenueData(revRes.value);
      if (profitRes.status === "fulfilled") setProfitData(profitRes.value);
      if (leadRes.status === "fulfilled") setLeaderboardData(leadRes.value);
      if (debtRes.status === "fulfilled") setDebtData(debtRes.value);
    } catch (err: any) {
      if (err.message?.includes("403")) {
        setErrorMsg("Tài khoản của bạn không có quyền xem báo cáo doanh thu (403 Forbidden).");
      } else {
        setErrorMsg("Lỗi khi tải báo cáo: " + err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllReports();
  }, [selectedYear, selectedMonth]);

  // AOV
  const aov = useMemo(() => {
    if (!revenueData || !revenueData.total_orders) return 0;
    return Math.round(revenueData.total_revenue / revenueData.total_orders);
  }, [revenueData]);

  // Tìm tháng có doanh thu cao nhất để tính biểu đồ
  const maxRevenue = useMemo(() => {
    if (!revenueData?.breakdown || revenueData.breakdown.length === 0) return 1;
    return Math.max(...revenueData.breakdown.map((b) => b.total_revenue || 0), 1);
  }, [revenueData]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Header phân hệ & Tabs Navigation */}
      <div className="px-6 py-3.5 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-xs border border-emerald-100">
            <BarChart2 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Báo cáo Quản trị & Hiệu suất (Executive Analytics)
            </h1>
            <p className="text-xs text-slate-500">
              Tổng hợp Doanh thu, Lợi nhuận gộp, Bảng xếp hạng Sales và Quản trị tuổi nợ (Phase 3)
            </p>
          </div>
        </div>

        {/* Action Controls & AI Prompt */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadAllReports}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <Link
            href={
              activeTab === "sales_leaderboard"
                ? `/copilot?q=Ai là nhân viên bán hàng xuất sắc nhất trong năm ${selectedYear}? Đánh giá hiệu suất đội ngũ kinh doanh.`
                : activeTab === "debt_aging"
                ? `/copilot?q=Báo cáo phân tích rủi ro tuổi nợ khách hàng và danh sách nợ quá hạn`
                : `/copilot?q=Phân tích biến động doanh thu và biên lợi nhuận gộp năm ${selectedYear}`
            }
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>
              {activeTab === "sales_leaderboard" 
                ? "AI Đánh giá Sales" 
                : activeTab === "debt_aging" 
                ? "AI Nhận định Công nợ" 
                : "AI Nhận định Doanh thu"}
            </span>
          </Link>
        </div>
      </div>

      {/* 2. Subheader: Tab Switcher & Bộ lọc thời gian */}
      <div className="px-6 py-2.5 bg-white border-b border-slate-200/80 flex flex-wrap items-center justify-between gap-3 shrink-0">
        {/* Tab Buttons */}
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl">
          <button
            type="button"
            onClick={() => setActiveTab("revenue_profit")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "revenue_profit"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-emerald-600" />
            <span>Doanh thu & Lợi nhuận gộp</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("sales_leaderboard")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "sales_leaderboard"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Trophy className="w-3.5 h-3.5 text-amber-500" />
            <span>Bảng xếp hạng Sales Rep</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("debt_aging")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "debt_aging"
                ? "bg-white text-slate-900 shadow-xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <CreditCard className="w-3.5 h-3.5 text-blue-600" />
            <span>Quản trị Công nợ & Tuổi nợ</span>
          </button>
        </div>

        {/* Date Filter (Chỉ áp dụng cho Doanh thu & Leaderboard) */}
        {activeTab !== "debt_aging" && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              <span>Kỳ:</span>
            </div>

            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value, 10))}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 cursor-pointer"
            >
              <option value={2026}>Năm 2026</option>
              <option value={2025}>Năm 2025</option>
              <option value={2024}>Năm 2024</option>
            </select>

            <select
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              className="px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 cursor-pointer"
            >
              <option value="all">Cả năm</option>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m.toString()}>
                  Tháng {m}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* 3. Nội dung chính theo từng Tab */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        
        {/* =========================================================
            TAB 1: DOANH THU & LỢI NHUẬN GỘP (REVENUE & PROFIT)
           ========================================================= */}
        {activeTab === "revenue_profit" && (
          <>
            {/* 4 Thẻ KPI Tài chính Cấp cao */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Doanh thu thuần */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Tổng Doanh Thu</span>
                  <DollarSign className="w-4 h-4 text-emerald-600" />
                </div>
                <div className="text-xl font-extrabold text-emerald-600 truncate">
                  {loading ? "..." : formatVND(revenueData?.total_revenue || 0)}
                </div>
                <div className="text-[11px] text-slate-400">
                  {revenueData?.total_orders || 0} đơn hàng đã hoàn thành
                </div>
              </div>

              {/* Card 2: Giá vốn hàng bán (COGS) */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Giá Vốn Hàng Bán (COGS)</span>
                  <Layers className="w-4 h-4 text-slate-500" />
                </div>
                <div className="text-xl font-extrabold text-slate-700 truncate">
                  {loading ? "..." : formatVND(profitData?.total_cogs || 0)}
                </div>
                <div className="text-[11px] text-slate-400">
                  Chi phí vốn sản phẩm xuất kho
                </div>
              </div>

              {/* Card 3: Lợi nhuận gộp (Gross Profit) */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Lợi Nhuận Gộp (Gross Profit)</span>
                  <TrendingUp className="w-4 h-4 text-blue-600" />
                </div>
                <div className="text-xl font-extrabold text-blue-600 truncate">
                  {loading ? "..." : formatVND(profitData?.gross_profit || 0)}
                </div>
                <div className="text-[11px] text-slate-400">
                  Doanh thu thuần trừ giá vốn
                </div>
              </div>

              {/* Card 4: Biên lợi nhuận gộp % */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Biên Lợi Nhuận Gộp (Margin)</span>
                  <Award className="w-4 h-4 text-amber-500" />
                </div>
                <div className="text-xl font-extrabold text-amber-600 truncate">
                  {loading ? "..." : `${profitData?.gross_margin_percent || 0}%`}
                </div>
                <div className="text-[11px] text-slate-400">
                  AOV trung bình: {formatVND(aov)}
                </div>
              </div>
            </div>

            {/* Biểu đồ cột & Bảng chi tiết */}
            <div className="flex flex-col lg:flex-row gap-5">
              {/* Biểu đồ Cột */}
              <div className="flex-1 bg-white p-5 rounded-2xl border border-slate-200/90 shadow-2xs flex flex-col min-h-[340px]">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-600" />
                    <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                      Biểu đồ Doanh thu theo chu kỳ
                    </h3>
                  </div>
                  <span className="text-[11px] text-slate-400">Đơn vị: VNĐ</span>
                </div>

                <div className="flex-1 flex items-end gap-3 pt-6 pb-2 px-2 border-b border-slate-100 overflow-x-auto min-h-[180px]">
                  {loading ? (
                    <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">
                      Đang tải dữ liệu biểu đồ...
                    </div>
                  ) : !revenueData?.breakdown || revenueData.breakdown.length === 0 ? (
                    <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">
                      Chưa có dữ liệu cho chu kỳ đã chọn
                    </div>
                  ) : (
                    revenueData.breakdown.map((item, idx) => {
                      const heightPercent = maxRevenue > 0 
                        ? Math.max(12, Math.round((item.total_revenue / maxRevenue) * 100))
                        : 12;

                      return (
                        <div
                          key={item.period || idx}
                          className="flex-1 flex flex-col items-center gap-2 h-full justify-end group min-w-[50px]"
                        >
                          {/* Tooltip khi rê chuột */}
                          <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 text-white text-[10px] px-2.5 py-1.5 rounded-lg shadow-md pointer-events-none text-center whitespace-nowrap mb-1">
                            <div className="font-bold">{formatVND(item.total_revenue)}</div>
                            <div className="text-slate-300">{item.order_count} đơn hàng</div>
                          </div>

                          {/* Thanh cột */}
                          <div
                            style={{ height: `${heightPercent}%` }}
                            className="w-full max-w-[48px] bg-emerald-500 group-hover:bg-emerald-600 rounded-t-lg transition-all duration-300 relative shadow-2xs flex items-center justify-center"
                          >
                            <div className="absolute top-1 w-2 h-0.5 bg-white/60 rounded-full" />
                          </div>

                          {/* Nhãn chu kỳ */}
                          <div className="text-[11px] font-semibold text-slate-600 group-hover:text-emerald-700 truncate w-full text-center">
                            {item.period}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="pt-3 flex items-center justify-between text-xs text-slate-400">
                  <span>Doanh thu cao nhất: <strong className="text-slate-700">{formatVND(maxRevenue)}</strong></span>
                  <span>Cập nhật thời gian thực từ CSDL ERP</span>
                </div>
              </div>

              {/* Bảng Breakdown chi tiết */}
              <div className="w-full lg:w-96 bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
                <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
                  <span className="font-bold text-xs text-slate-800 uppercase tracking-wider">
                    Chi tiết theo kỳ
                  </span>
                  <span className="text-[11px] text-slate-500 font-medium">
                    {revenueData?.breakdown?.length || 0} kỳ
                  </span>
                </div>

                <div className="flex-1 overflow-y-auto max-h-[320px]">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200/60 text-[10.5px] font-bold uppercase text-slate-500">
                      <tr>
                        <th className="py-2.5 px-3">Kỳ</th>
                        <th className="py-2.5 px-2 text-center">Đơn</th>
                        <th className="py-2.5 px-3 text-right">Doanh thu</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {loading ? (
                        Array.from({ length: 4 }).map((_, i) => (
                          <tr key={i} className="animate-pulse">
                            <td className="py-3 px-3"><div className="h-4 bg-slate-200 rounded-md w-16" /></td>
                            <td className="py-3 px-2 text-center"><div className="h-4 bg-slate-100 rounded-md w-8 mx-auto" /></td>
                            <td className="py-3 px-3 text-right"><div className="h-4 bg-slate-200 rounded-md w-20 ml-auto" /></td>
                          </tr>
                        ))
                      ) : !revenueData?.breakdown || revenueData.breakdown.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="py-8 text-center text-slate-400">
                            Chưa có dữ liệu
                          </td>
                        </tr>
                      ) : (
                        revenueData.breakdown.map((item, idx) => (
                          <tr key={item.period || idx} className="hover:bg-slate-50/80 transition-colors">
                            <td className="py-2.5 px-3 font-semibold text-slate-800">
                              {item.period}
                            </td>
                            <td className="py-2.5 px-2 text-center font-bold text-slate-600">
                              {item.order_count}
                            </td>
                            <td className="py-2.5 px-3 text-right font-bold text-emerald-600">
                              {formatVND(item.total_revenue)}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="p-3 border-t border-slate-100 bg-slate-50">
                  <Link
                    href="/orders"
                    className="block w-full text-center py-2 bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-2xs"
                  >
                    Xem danh sách đơn hàng
                  </Link>
                </div>
              </div>
            </div>
          </>
        )}

        {/* =========================================================
            TAB 2: BẢNG XẾP HẠNG SALES REP (SALES LEADERBOARD)
           ========================================================= */}
        {activeTab === "sales_leaderboard" && (
          <div className="space-y-5">
            {/* Top 3 Vinh Danh (Podium) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Hạng 2 */}
              <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-2xs flex flex-col items-center text-center relative overflow-hidden order-2 md:order-1">
                <div className="w-10 h-10 rounded-full bg-slate-100 border-2 border-slate-300 flex items-center justify-center text-lg mb-2 shadow-2xs">
                  🥈
                </div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Hạng Nhì (Á quân)</div>
                <div className="text-sm font-bold text-slate-900 truncate max-w-full">
                  {leaderboardData?.items[1]?.sales_name || "Chưa có"}
                </div>
                <div className="text-xs text-slate-500 mb-2 truncate max-w-full">
                  {leaderboardData?.items[1]?.sales_email || "sales2@erpcopilot.vn"}
                </div>
                <div className="text-base font-extrabold text-blue-600">
                  {leaderboardData?.items[1] ? formatVND(leaderboardData.items[1].total_revenue) : "0 đ"}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  {leaderboardData?.items[1]?.total_orders || 0} đơn đã chốt
                </div>
              </div>

              {/* Hạng 1 - Quán quân */}
              <div className="bg-gradient-to-b from-amber-50/50 to-white p-6 rounded-2xl border-2 border-amber-300/80 shadow-md flex flex-col items-center text-center relative overflow-hidden order-1 md:order-2">
                <div className="absolute top-2 right-2 bg-amber-400/20 text-amber-700 text-[10px] font-extrabold px-2 py-0.5 rounded-full">
                  TOP 1
                </div>
                <div className="w-14 h-14 rounded-full bg-amber-100 border-2 border-amber-400 flex items-center justify-center text-2xl mb-2 shadow-xs">
                  🥇
                </div>
                <div className="text-xs font-extrabold text-amber-600 uppercase tracking-wider mb-1">Quán Quân Bán Hàng</div>
                <div className="text-base font-extrabold text-slate-900 truncate max-w-full">
                  {leaderboardData?.items[0]?.sales_name || "Chưa có"}
                </div>
                <div className="text-xs text-slate-500 mb-2 truncate max-w-full">
                  {leaderboardData?.items[0]?.sales_email || "sales@erpcopilot.vn"}
                </div>
                <div className="text-xl font-extrabold text-amber-600">
                  {leaderboardData?.items[0] ? formatVND(leaderboardData.items[0].total_revenue) : "0 đ"}
                </div>
                <div className="text-[11px] text-slate-500 mt-1 font-medium">
                  {leaderboardData?.items[0]?.total_orders || 0} đơn hàng | AOV: {formatVND(leaderboardData?.items[0]?.aov || 0)}
                </div>
              </div>

              {/* Hạng 3 */}
              <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-2xs flex flex-col items-center text-center relative overflow-hidden order-3 md:order-3">
                <div className="w-10 h-10 rounded-full bg-amber-50 border-2 border-amber-200 flex items-center justify-center text-lg mb-2 shadow-2xs">
                  🥉
                </div>
                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Hạng Ba</div>
                <div className="text-sm font-bold text-slate-900 truncate max-w-full">
                  {leaderboardData?.items[2]?.sales_name || "Chưa có"}
                </div>
                <div className="text-xs text-slate-500 mb-2 truncate max-w-full">
                  {leaderboardData?.items[2]?.sales_email || "sales3@erpcopilot.vn"}
                </div>
                <div className="text-base font-extrabold text-emerald-600">
                  {leaderboardData?.items[2] ? formatVND(leaderboardData.items[2].total_revenue) : "0 đ"}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  {leaderboardData?.items[2]?.total_orders || 0} đơn đã chốt
                </div>
              </div>
            </div>

            {/* Bảng Xếp Hạng Chi Tiết Toàn Bộ Nhân Sự */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-blue-600" />
                  <span className="font-bold text-xs text-slate-800 uppercase tracking-wider">
                    Danh sách Xếp hạng Hiệu suất Kinh doanh
                  </span>
                </div>
                <span className="text-xs text-slate-500 font-medium">
                  Tổng {leaderboardData?.total_sales_reps || 0} nhân sự
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200/60 text-[10.5px] font-bold uppercase text-slate-500">
                    <tr>
                      <th className="py-3 px-4 text-center w-16">Thứ hạng</th>
                      <th className="py-3 px-4">Nhân viên kinh doanh</th>
                      <th className="py-3 px-4 text-center">Số đơn chốt</th>
                      <th className="py-3 px-4 text-right">Đơn TB (AOV)</th>
                      <th className="py-3 px-4 text-right">Tổng Doanh thu</th>
                      <th className="py-3 px-4 text-center">Đánh giá</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      Array.from({ length: 3 }).map((_, i) => (
                        <tr key={i} className="animate-pulse">
                          <td className="py-3 px-4 text-center"><div className="h-4 bg-slate-200 rounded w-6 mx-auto" /></td>
                          <td className="py-3 px-4"><div className="h-4 bg-slate-200 rounded w-36" /></td>
                          <td className="py-3 px-4 text-center"><div className="h-4 bg-slate-100 rounded w-10 mx-auto" /></td>
                          <td className="py-3 px-4 text-right"><div className="h-4 bg-slate-100 rounded w-20 ml-auto" /></td>
                          <td className="py-3 px-4 text-right"><div className="h-4 bg-slate-200 rounded w-24 ml-auto" /></td>
                          <td className="py-3 px-4 text-center"><div className="h-4 bg-slate-100 rounded w-16 mx-auto" /></td>
                        </tr>
                      ))
                    ) : !leaderboardData?.items || leaderboardData.items.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400">
                          Chưa có đơn hàng nào được ghi nhận trong chu kỳ này
                        </td>
                      </tr>
                    ) : (
                      leaderboardData.items.map((rep) => (
                        <tr key={rep.sales_id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-3 px-4 text-center">
                            {rep.rank === 1 ? (
                              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-100 text-amber-700 font-extrabold text-xs">🥇</span>
                            ) : rep.rank === 2 ? (
                              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-slate-200 text-slate-700 font-extrabold text-xs">🥈</span>
                            ) : rep.rank === 3 ? (
                              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-amber-50 text-amber-800 font-extrabold text-xs">🥉</span>
                            ) : (
                              <span className="text-slate-500 font-bold">#{rep.rank}</span>
                            )}
                          </td>
                          <td className="py-3 px-4">
                            <div className="font-bold text-slate-900">{rep.sales_name}</div>
                            <div className="text-[11px] text-slate-400">{rep.sales_email}</div>
                          </td>
                          <td className="py-3 px-4 text-center font-bold text-slate-700">
                            {rep.total_orders} đơn
                          </td>
                          <td className="py-3 px-4 text-right font-medium text-slate-600">
                            {formatVND(rep.aov)}
                          </td>
                          <td className="py-3 px-4 text-right font-extrabold text-emerald-600">
                            {formatVND(rep.total_revenue)}
                          </td>
                          <td className="py-3 px-4 text-center">
                            {rep.total_revenue > 0 ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <CheckCircle2 className="w-3 h-3" /> Xuất sắc
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-50 text-slate-500 border border-slate-200">
                                Cần nỗ lực
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* =========================================================
            TAB 3: QUẢN TRỊ CÔNG NỢ & TUỔI NỢ (DEBT AGING ANALYSIS)
           ========================================================= */}
        {activeTab === "debt_aging" && (
          <div className="space-y-5">
            {/* 4 Thẻ Chỉ số Rủi ro Tín dụng */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Card 1: Tổng Dư Nợ Phải Thu */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Tổng Công Nợ Phải Thu</span>
                  <CreditCard className="w-4 h-4 text-blue-600" />
                </div>
                <div className="text-xl font-extrabold text-blue-600 truncate">
                  {loading ? "..." : formatVND(debtData?.total_debt || 0)}
                </div>
                <div className="text-[11px] text-slate-400">
                  Dư nợ khách hàng đang nợ công ty
                </div>
              </div>

              {/* Card 2: Tổng Hạn mức Tín dụng cấp */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Tổng Hạn Mức Tín Dụng</span>
                  <Layers className="w-4 h-4 text-slate-500" />
                </div>
                <div className="text-xl font-extrabold text-slate-700 truncate">
                  {loading ? "..." : formatVND(debtData?.total_credit_limit || 0)}
                </div>
                <div className="text-[11px] text-slate-400">
                  Hạn mức tối đa được duyệt
                </div>
              </div>

              {/* Card 3: Tỷ lệ sử dụng hạn mức toàn hệ thống */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Tỷ Lệ Dư Nợ / Hạn Mức</span>
                  <PieChart className="w-4 h-4 text-amber-500" />
                </div>
                <div className="text-xl font-extrabold text-amber-600 truncate">
                  {loading ? "..." : `${debtData?.overall_utilization_rate || 0}%`}
                </div>
                <div className="text-[11px] text-slate-400">
                  Mức độ an toàn vốn lưu động
                </div>
              </div>

              {/* Card 4: Số khách hàng vượt hạn mức */}
              <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>Khách Hàng Vượt Hạn Mức</span>
                  <ShieldAlert className="w-4 h-4 text-rose-500" />
                </div>
                <div className="text-xl font-extrabold text-rose-600 truncate">
                  {loading ? "..." : `${debtData?.over_limit_customers_count || 0} khách`}
                </div>
                <div className="text-[11px] text-rose-400">
                  Cần can thiệp thu hồi hoặc phê duyệt đặc biệt
                </div>
              </div>
            </div>

            {/* Phân loại Tuổi nợ (Aging Buckets) */}
            <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-slate-700" />
                  <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Phân bổ Tuổi nợ & Mức độ Rủi ro thu hồi nợ (Aging Report)
                  </h3>
                </div>
                <span className="text-xs text-slate-400">Đơn vị: VNĐ</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                {debtData?.buckets?.map((bucket, idx) => {
                  const isSafe = bucket.bucket === "current";
                  const isWarning = bucket.bucket === "1_30_days";
                  const isDanger = bucket.bucket === "31_60_days";
                  const isCritical = bucket.bucket === "over_60_days";

                  return (
                    <div
                      key={bucket.bucket || idx}
                      className={`p-4 rounded-xl border transition-all ${
                        isSafe
                          ? "bg-emerald-50/40 border-emerald-200 text-emerald-950"
                          : isWarning
                          ? "bg-amber-50/40 border-amber-200 text-amber-950"
                          : isDanger
                          ? "bg-orange-50/40 border-orange-200 text-orange-950"
                          : "bg-rose-50/40 border-rose-200 text-rose-950"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs font-bold mb-1.5">
                        <span>{bucket.label}</span>
                        <span className="text-[10.5px] px-2 py-0.5 rounded-full bg-white font-semibold shadow-2xs border border-slate-200/60">
                          {bucket.customer_count} khách
                        </span>
                      </div>
                      <div className="text-lg font-extrabold truncate">
                        {formatVND(bucket.amount)}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-1">
                        {isSafe && "Rủi ro thấp • Trong hạn mức 50%"}
                        {isWarning && "Cần nhắc nhở • Đạt 50-80% hạn mức"}
                        {isDanger && "Cảnh báo cao • Đạt 80-100% hạn mức"}
                        {isCritical && "Nguy cơ nợ xấu • Đã vượt hạn mức tín dụng"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Bảng Top Khách Hàng Dư Nợ Cao Nhất */}
            <div className="bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                  <span className="font-bold text-xs text-slate-800 uppercase tracking-wider">
                    Top Khách Hàng Dư Nợ Cần Chú Ý
                  </span>
                </div>
                <Link
                  href="/customers"
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1"
                >
                  <span>Xem tất cả khách hàng</span>
                  <ArrowUpRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200/60 text-[10.5px] font-bold uppercase text-slate-500">
                    <tr>
                      <th className="py-3 px-4">Mã KH</th>
                      <th className="py-3 px-4">Tên khách hàng</th>
                      <th className="py-3 px-4 text-right">Hạn mức được duyệt</th>
                      <th className="py-3 px-4 text-right">Dư nợ hiện tại</th>
                      <th className="py-3 px-4 text-center">Tỷ lệ sử dụng</th>
                      <th className="py-3 px-4 text-center">Trạng thái rủi ro</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      Array.from({ length: 3 }).map((_, i) => (
                        <tr key={i} className="animate-pulse">
                          <td className="py-3 px-4"><div className="h-4 bg-slate-200 rounded w-16" /></td>
                          <td className="py-3 px-4"><div className="h-4 bg-slate-200 rounded w-36" /></td>
                          <td className="py-3 px-4 text-right"><div className="h-4 bg-slate-100 rounded w-20 ml-auto" /></td>
                          <td className="py-3 px-4 text-right"><div className="h-4 bg-slate-200 rounded w-24 ml-auto" /></td>
                          <td className="py-3 px-4 text-center"><div className="h-4 bg-slate-100 rounded w-12 mx-auto" /></td>
                          <td className="py-3 px-4 text-center"><div className="h-4 bg-slate-100 rounded w-20 mx-auto" /></td>
                        </tr>
                      ))
                    ) : !debtData?.top_debtors || debtData.top_debtors.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-400">
                          Tất cả khách hàng đều có công nợ bằng 0. Dòng tiền an toàn tuyệt đối.
                        </td>
                      </tr>
                    ) : (
                      debtData.top_debtors.map((debtor) => (
                        <tr key={debtor.customer_id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="py-3 px-4 font-mono font-bold text-slate-700">
                            {debtor.customer_code}
                          </td>
                          <td className="py-3 px-4 font-bold text-slate-900">
                            {debtor.customer_name}
                          </td>
                          <td className="py-3 px-4 text-right text-slate-600 font-medium">
                            {formatVND(debtor.credit_limit)}
                          </td>
                          <td className="py-3 px-4 text-right font-extrabold text-blue-600">
                            {formatVND(debtor.current_debt)}
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`font-bold ${
                              debtor.is_over_limit 
                                ? "text-rose-600 font-extrabold" 
                                : debtor.credit_utilization_rate >= 80 
                                ? "text-amber-600" 
                                : "text-emerald-600"
                            }`}>
                              {debtor.credit_utilization_rate}%
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            {debtor.is_over_limit ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                                ⚠️ Vượt hạn mức
                              </span>
                            ) : debtor.credit_utilization_rate >= 80 ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                                Cảnh báo mức cao
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                An toàn
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

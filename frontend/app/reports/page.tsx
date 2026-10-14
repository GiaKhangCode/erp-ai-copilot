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
  ArrowUpRight
} from "lucide-react";
import { fetchRevenueReport, RevenueReportData } from "@/lib/api";
import { formatVND } from "@/lib/utils";

export default function ReportsPage() {
  const [selectedYear, setSelectedYear] = useState<number>(2026);
  const [selectedMonth, setSelectedMonth] = useState<string>("all");
  const [reportData, setReportData] = useState<RevenueReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadReport = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const monthVal = selectedMonth === "all" ? undefined : parseInt(selectedMonth, 10);
      const data = await fetchRevenueReport(selectedYear, monthVal);
      setReportData(data);
    } catch (err: any) {
      setErrorMsg("Lỗi khi tải báo cáo doanh thu: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, [selectedYear, selectedMonth]);

  // Tính giá trị trung bình đơn (AOV)
  const aov = useMemo(() => {
    if (!reportData || !reportData.total_orders) return 0;
    return Math.round(reportData.total_revenue / reportData.total_orders);
  }, [reportData]);

  // Tìm tháng có doanh thu cao nhất để tính tỷ lệ biểu đồ
  const maxRevenue = useMemo(() => {
    if (!reportData?.breakdown || reportData.breakdown.length === 0) return 1;
    return Math.max(...reportData.breakdown.map((b) => b.total_revenue || 0), 1);
  }, [reportData]);

  return (
    <div className="flex-1 h-full flex flex-col bg-[#F8FAFC] overflow-hidden select-none">
      {/* 1. Header phân hệ */}
      <div className="px-6 py-4 bg-white border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-xs border border-emerald-100">
            <BarChart2 className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-slate-900 leading-tight">
              Báo cáo Doanh thu & Phân tích (Revenue Analytics)
            </h1>
            <p className="text-xs text-slate-500">
              Tổng hợp số liệu doanh thu thực tế từ cơ sở dữ liệu ERP theo từng kỳ kế toán
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={loadReport}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold shadow-2xs transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-emerald-600" : "text-slate-500"}`} />
            <span>Làm mới</span>
          </button>

          <Link
            href={`/copilot?q=Phân tích biến động doanh thu năm ${selectedYear} và so sánh với cùng kỳ`}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-[#0066FF] hover:bg-blue-700 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer active:scale-95"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>AI Nhận định doanh thu</span>
          </Link>
        </div>
      </div>

      {/* 2. Bộ lọc năm & tháng */}
      <div className="px-6 py-3.5 bg-white border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold">
            <Calendar className="w-4 h-4 text-slate-400" />
            <span>Kỳ báo cáo:</span>
          </div>

          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(parseInt(e.target.value, 10))}
            className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 cursor-pointer"
          >
            <option value={2026}>Năm 2026</option>
            <option value={2025}>Năm 2025</option>
            <option value={2024}>Năm 2024</option>
          </select>

          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 cursor-pointer"
          >
            <option value="all">Toàn bộ các tháng (Cả năm)</option>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m.toString()}>
                Tháng {m}
              </option>
            ))}
          </select>
        </div>

        <div className="text-xs text-slate-400">
          Metric: <span className="font-mono text-slate-600">{reportData?.metric_id || "revenue.by_period"}</span>
        </div>
      </div>

      {/* 3. Thẻ chỉ số tổng quan */}
      <div className="px-6 py-4 grid grid-cols-1 sm:grid-cols-3 gap-4 shrink-0">
        <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Tổng Doanh Thu</span>
            <DollarSign className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-xl font-extrabold text-emerald-600 truncate">
            {loading ? "..." : formatVND(reportData?.total_revenue || 0)}
          </div>
          <div className="text-[11px] text-slate-400">
            Kỳ {selectedMonth === "all" ? `Năm ${selectedYear}` : `Tháng ${selectedMonth}/${selectedYear}`}
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Tổng Đơn Bán Hàng</span>
            <ShoppingBag className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-xl font-extrabold text-slate-900">
            {loading ? "..." : `${(reportData?.total_orders || 0).toLocaleString()} đơn`}
          </div>
          <div className="text-[11px] text-slate-400">
            Các đơn hàng trạng thái confirmed
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-2xs space-y-1">
          <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
            <span>Giá Trị Trung Bình Đơn (AOV)</span>
            <Award className="w-4 h-4 text-amber-500" />
          </div>
          <div className="text-xl font-extrabold text-slate-800 truncate">
            {loading ? "..." : formatVND(aov)}
          </div>
          <div className="text-[11px] text-slate-400">
            Doanh thu trung bình trên mỗi đơn
          </div>
        </div>
      </div>

      {/* 4. Nội dung chính: Biểu đồ & Bảng phân tích chi tiết */}
      <div className="flex-1 px-6 pb-6 overflow-hidden flex flex-col lg:flex-row gap-4">
        {/* Biểu đồ Cột Doanh Thu */}
        <div className="flex-1 bg-white p-5 rounded-2xl border border-slate-200/90 shadow-2xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-600" />
              <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                Biểu đồ Doanh thu theo chu kỳ
              </h3>
            </div>
            <span className="text-[11px] text-slate-400">Đơn vị: VNĐ</span>
          </div>

          <div className="flex-1 flex items-end gap-3 pt-6 pb-2 px-2 border-b border-slate-100 overflow-x-auto min-h-[160px]">
            {loading ? (
              <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">
                Đang tải dữ liệu biểu đồ...
              </div>
            ) : !reportData?.breakdown || reportData.breakdown.length === 0 ? (
              <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">
                Chưa có dữ liệu cho chu kỳ đã chọn
              </div>
            ) : (
              reportData.breakdown.map((item, idx) => {
                const heightPercent = maxRevenue > 0 
                  ? Math.max(12, Math.round((item.total_revenue / maxRevenue) * 100))
                  : 12;

                return (
                  <div
                    key={item.period || idx}
                    className="flex-1 flex flex-col items-center gap-2 h-full justify-end group min-w-[50px]"
                  >
                    {/* Tooltip khi rê chuột */}
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900 text-white text-[10px] px-2 py-1 rounded-md shadow-md pointer-events-none text-center whitespace-nowrap mb-1">
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
            <span>Doanh thu cao nhất chu kỳ: <strong className="text-slate-700">{formatVND(maxRevenue)}</strong></span>
            <span>Cập nhật thời gian thực</span>
          </div>
        </div>

        {/* Bảng Breakdown chi tiết */}
        <div className="w-full lg:w-96 bg-white rounded-2xl border border-slate-200/90 shadow-2xs overflow-hidden flex flex-col">
          <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
            <span className="font-bold text-xs text-slate-800 uppercase tracking-wider">
              Chi tiết theo từng kỳ
            </span>
            <span className="text-[11px] text-slate-500 font-medium">
              {reportData?.breakdown?.length || 0} kỳ
            </span>
          </div>

          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead className="bg-slate-50 border-b border-slate-200/60 text-[10.5px] font-bold uppercase text-slate-500">
                <tr>
                  <th className="py-2.5 px-3">Chu kỳ</th>
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
                ) : !reportData?.breakdown || reportData.breakdown.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400">
                      Chưa có dữ liệu
                    </td>
                  </tr>
                ) : (
                  reportData.breakdown.map((item, idx) => (
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

          <div className="p-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
            <Link
              href="/orders"
              className="w-full text-center py-2 bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shadow-2xs"
            >
              Xem danh sách đơn hàng
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

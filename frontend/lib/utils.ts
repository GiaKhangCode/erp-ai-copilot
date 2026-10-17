import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatVND(amount: number | string): string {
  const numeric = typeof amount === "string" ? parseFloat(amount) : amount;
  if (isNaN(numeric)) return "0 đ";
  return new Intl.NumberFormat("vi-VN").format(numeric) + " đ";
}

export function formatNumber(val: number | string): string {
  const numeric = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(numeric)) return "0";
  return new Intl.NumberFormat("vi-VN").format(numeric);
}

export function formatDate(dateStr?: string | Date | null): string {
  if (!dateStr) return "";
  try {
    const d = typeof dateStr === "string" ? new Date(dateStr) : dateStr;
    return d.toLocaleDateString("vi-VN");
  } catch {
    return String(dateStr);
  }
}

from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.erp.models import SalesOrder
from app.erp.schemas import RevenueReportResponse, RevenueReportItem


class ReportingService:
    @staticmethod
    async def get_revenue(
        session: AsyncSession,
        year: Optional[int] = None,
        month: Optional[int] = None,
        status: Optional[str] = None,
    ) -> RevenueReportResponse:
        """
        Tính toán doanh thu báo cáo từ cơ sở dữ liệu (Use case UC-02 & Tool get_revenue).
        Hỗ trợ đối chiếu chuẩn xác với SQL views.
        """
        stmt = select(SalesOrder)
        if status:
            stmt = stmt.where(SalesOrder.status == status)
        else:
            # Default include all non-cancelled orders for reporting
            stmt = stmt.where(SalesOrder.status != "cancelled")

        if year:
            stmt = stmt.where(func.extract("year", SalesOrder.created_at) == year)
        if month:
            stmt = stmt.where(func.extract("month", SalesOrder.created_at) == month)

        result = await session.execute(stmt)
        orders = result.scalars().all()

        total_rev = Decimal("0.00")
        month_buckets: dict[str, dict] = {}

        for o in orders:
            total_rev += o.total_amount
            p = o.created_at.strftime("%Y-%m")
            if p not in month_buckets:
                month_buckets[p] = {"count": 0, "rev": Decimal("0.00")}
            month_buckets[p]["count"] += 1
            month_buckets[p]["rev"] += o.total_amount

        breakdown = [
            RevenueReportItem(
                period=p,
                order_count=data["count"],
                total_revenue=data["rev"],
            )
            for p, data in sorted(month_buckets.items())
        ]

        period_label = (
            f"{year}-{month:02d}" if (year and month) else (str(year) if year else "all")
        )

        return RevenueReportResponse(
            metric_id="revenue_summary",
            period=period_label,
            total_revenue=total_rev,
            total_orders=len(orders),
            breakdown=breakdown,
        )

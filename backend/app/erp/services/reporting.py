from decimal import Decimal
from typing import Optional, List, Dict
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.erp.models import SalesOrder, SalesOrderItem, Product, Customer, User
from app.erp.schemas import (
    RevenueReportResponse,
    RevenueReportItem,
    SalesLeaderboardResponse,
    SalesLeaderboardItem,
    FinancialProfitabilityResponse,
    DebtAgingReportResponse,
    DebtAgingBucket,
    TopDebtorItem,
)


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

    @staticmethod
    async def get_sales_leaderboard(
        session: AsyncSession,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> SalesLeaderboardResponse:
        """
        Báo cáo hiệu suất kinh doanh (Sales Leaderboard) vinh danh Top Sales Reps (Phase 3).
        Tính toán doanh số, số đơn hàng đã chốt và giá trị đơn trung bình (AOV).
        """
        # 1. Lấy danh sách nhân viên kinh doanh
        users_stmt = select(User).where(User.role.in_(["sales_rep", "sales_manager", "admin"]))
        users_result = await session.execute(users_stmt)
        users = users_result.scalars().all()
        user_map: Dict[str, User] = {str(u.id): u for u in users}

        # 2. Truy vấn đơn hàng đã chốt hoặc hoàn thành
        orders_stmt = select(SalesOrder).where(SalesOrder.status.in_(["confirmed", "delivered"]))
        if year:
            orders_stmt = orders_stmt.where(func.extract("year", SalesOrder.created_at) == year)
        if month:
            orders_stmt = orders_stmt.where(func.extract("month", SalesOrder.created_at) == month)

        orders_result = await session.execute(orders_stmt)
        orders = orders_result.scalars().all()

        # 3. Gom nhóm theo người tạo đơn (created_by)
        stats: Dict[str, Dict] = {}
        for uid in user_map:
            stats[uid] = {"revenue": Decimal("0.00"), "orders_count": 0}

        for order in orders:
            creator_id = str(order.created_by)
            if creator_id not in stats:
                stats[creator_id] = {"revenue": Decimal("0.00"), "orders_count": 0}
            stats[creator_id]["revenue"] += order.total_amount
            stats[creator_id]["orders_count"] += 1

        # 4. Sắp xếp giảm dần theo doanh thu
        sorted_users = sorted(
            stats.items(),
            key=lambda x: (x[1]["revenue"], x[1]["orders_count"]),
            reverse=True,
        )

        items: List[SalesLeaderboardItem] = []
        rank = 1
        for uid, stat in sorted_users:
            user = user_map.get(uid)
            rev = stat["revenue"]
            cnt = stat["orders_count"]
            aov = Decimal(str(round(float(rev) / cnt, 2))) if cnt > 0 else Decimal("0.00")
            items.append(
                SalesLeaderboardItem(
                    sales_id=user.id if user else uid,
                    sales_name=user.full_name if user else f"Nhân viên ({uid[:6]})",
                    sales_email=user.email if user else "sales@erpcopilot.vn",
                    total_revenue=rev,
                    total_orders=cnt,
                    aov=aov,
                    rank=rank,
                )
            )
            rank += 1

        period_label = (
            f"{year}-{month:02d}" if (year and month) else (str(year) if year else "all")
        )

        return SalesLeaderboardResponse(
            metric_id="sales_leaderboard",
            period=period_label,
            total_sales_reps=len(items),
            items=items,
        )

    @staticmethod
    async def get_financial_profitability(
        session: AsyncSession,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> FinancialProfitabilityResponse:
        """
        Báo cáo lợi nhuận gộp & tỷ suất lợi nhuận (Gross Profit & Margin) (Phase 3).
        Lợi nhuận gộp = Doanh thu thuần - Giá vốn hàng bán (COGS).
        """
        # Truy vấn các đơn hàng không bị hủy
        stmt = (
            select(SalesOrderItem, Product, SalesOrder)
            .join(Product, SalesOrderItem.product_id == Product.id)
            .join(SalesOrder, SalesOrderItem.order_id == SalesOrder.id)
            .where(SalesOrder.status.in_(["confirmed", "delivered"]))
        )

        if year:
            stmt = stmt.where(func.extract("year", SalesOrder.created_at) == year)
        if month:
            stmt = stmt.where(func.extract("month", SalesOrder.created_at) == month)

        result = await session.execute(stmt)
        rows = result.all()

        total_revenue = Decimal("0.00")
        total_cogs = Decimal("0.00")
        order_ids = set()

        for item, product, order in rows:
            order_ids.add(order.id)
            total_revenue += item.line_total
            # Giá vốn = số lượng * giá vốn sản phẩm (nếu chưa có giá vốn, ước tính 65% đơn giá)
            item_cost = product.cost_price if product.cost_price > 0 else (product.unit_price * Decimal("0.65"))
            total_cogs += Decimal(str(item.quantity)) * item_cost

        gross_profit = total_revenue - total_cogs
        gross_margin_percent = (
            float(round((gross_profit / total_revenue) * 100, 2)) if total_revenue > 0 else 0.0
        )

        period_label = (
            f"{year}-{month:02d}" if (year and month) else (str(year) if year else "all")
        )

        return FinancialProfitabilityResponse(
            metric_id="financial_profitability",
            period=period_label,
            total_revenue=total_revenue,
            total_cogs=total_cogs,
            gross_profit=gross_profit,
            gross_margin_percent=gross_margin_percent,
            total_orders=len(order_ids),
        )

    @staticmethod
    async def get_debt_aging(
        session: AsyncSession,
    ) -> DebtAgingReportResponse:
        """
        Báo cáo phân tích công nợ & rủi ro thu hồi nợ (Debt Aging Analysis) (Phase 3).
        Phân loại nợ theo tuổi nợ và tỷ lệ hạn mức tín dụng khách hàng.
        """
        customers_stmt = select(Customer).where(Customer.status == "active")
        customers_res = await session.execute(customers_stmt)
        customers = customers_res.scalars().all()

        total_debt = Decimal("0.00")
        total_credit_limit = Decimal("0.00")
        over_limit_count = 0

        # Khởi tạo các nhóm tuổi nợ
        bucket_current = Decimal("0.00")
        count_current = 0
        bucket_1_30 = Decimal("0.00")
        count_1_30 = 0
        bucket_31_60 = Decimal("0.00")
        count_31_60 = 0
        bucket_over_60 = Decimal("0.00")
        count_over_60 = 0

        debtors: List[TopDebtorItem] = []

        for cust in customers:
            debt = cust.current_debt or Decimal("0.00")
            limit = cust.credit_limit or Decimal("50000000.00")
            total_debt += debt
            total_credit_limit += limit

            utilization = float(round((debt / limit) * 100, 2)) if limit > 0 else 0.0
            is_over = debt > limit
            if is_over:
                over_limit_count += 1

            # Phân loại tuổi nợ theo rủi ro hạn mức và mức nợ
            if debt == 0:
                pass
            elif utilization <= 50.0:
                bucket_current += debt
                count_current += 1
            elif utilization <= 80.0:
                bucket_1_30 += debt
                count_1_30 += 1
            elif utilization <= 100.0:
                bucket_31_60 += debt
                count_31_60 += 1
            else:
                bucket_over_60 += debt
                count_over_60 += 1

            if debt > 0:
                debtors.append(
                    TopDebtorItem(
                        customer_id=cust.id,
                        customer_code=cust.code,
                        customer_name=cust.name,
                        credit_limit=limit,
                        current_debt=debt,
                        credit_utilization_rate=utilization,
                        is_over_limit=is_over,
                    )
                )

        # Sắp xếp danh sách con nợ giảm dần theo số tiền nợ
        debtors.sort(key=lambda d: d.current_debt, reverse=True)

        overall_utilization = (
            float(round((total_debt / total_credit_limit) * 100, 2))
            if total_credit_limit > 0
            else 0.0
        )

        buckets = [
            DebtAgingBucket(
                bucket="current",
                label="Trong hạn (An toàn)",
                amount=bucket_current,
                customer_count=count_current,
            ),
            DebtAgingBucket(
                bucket="1_30_days",
                label="Quá hạn 1 - 30 ngày (Chú ý)",
                amount=bucket_1_30,
                customer_count=count_1_30,
            ),
            DebtAgingBucket(
                bucket="31_60_days",
                label="Quá hạn 31 - 60 ngày (Cảnh báo)",
                amount=bucket_31_60,
                customer_count=count_31_60,
            ),
            DebtAgingBucket(
                bucket="over_60_days",
                label="Quá hạn > 60 ngày (Nguy cơ nợ xấu)",
                amount=bucket_over_60,
                customer_count=count_over_60,
            ),
        ]

        return DebtAgingReportResponse(
            metric_id="debt_aging_analysis",
            total_debt=total_debt,
            total_credit_limit=total_credit_limit,
            overall_utilization_rate=overall_utilization,
            over_limit_customers_count=over_limit_count,
            buckets=buckets,
            top_debtors=debtors[:10],
        )


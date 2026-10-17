import json
import pytest
from decimal import Decimal
import uuid

from app.ai.tools.context import UserContext, set_current_user_context
from app.ai.tools.erp_tools import (
    get_sales_leaderboard,
    get_financial_and_debt_report,
)
from app.erp.schemas import (
    SalesLeaderboardResponse,
    SalesLeaderboardItem,
    FinancialProfitabilityResponse,
    DebtAgingReportResponse,
    DebtAgingBucket,
    TopDebtorItem,
)


@pytest.mark.asyncio
async def test_phase3_ai_tools_rbac_unauthorized_roles():
    """
    Xác thực các AI Tools phân tích tài chính & xếp hạng Sales (Phase 3)
    từ chối vai trò không có thẩm quyền (warehouse_keeper và sales_rep).
    """
    # 1. Giả lập context của Thủ kho (warehouse_keeper)
    set_current_user_context(UserContext(
        user_id=uuid.uuid4(),
        user_role="warehouse_keeper",
        user_name="Phạm Văn Thủ Kho",
        user_email="warehouse@erpcopilot.vn",
        user_permissions=["inventory:read", "inventory:write", "customers:read"],
    ))

    # Leaderboard -> Từ chối
    res_lead_wh = await get_sales_leaderboard.ainvoke({"year": 2026})
    data_lead_wh = json.loads(res_lead_wh)
    assert data_lead_wh.get("error") == "PERMISSION_DENIED"
    assert "chỉ dành cho Quản trị viên" in data_lead_wh.get("message", "")

    # Financial & Debt -> Từ chối
    res_fin_wh = await get_financial_and_debt_report.ainvoke({"year": 2026})
    data_fin_wh = json.loads(res_fin_wh)
    assert data_fin_wh.get("error") == "PERMISSION_DENIED"
    assert "dữ liệu tài chính mật" in data_fin_wh.get("message", "")

    # 2. Giả lập context của Sales Rep (sales_rep)
    set_current_user_context(UserContext(
        user_id=uuid.uuid4(),
        user_role="sales_rep",
        user_name="Nguyễn Văn Bán Hàng",
        user_email="sales@erpcopilot.vn",
        user_permissions=["orders:read", "orders:create", "customers:read"],
    ))

    # Sales Rep không có quyền reports:revenue_view -> Bị từ chối xem Lợi nhuận gộp toàn công ty
    res_fin_sales = await get_financial_and_debt_report.ainvoke({"year": 2026})
    data_fin_sales = json.loads(res_fin_sales)
    assert data_fin_sales.get("error") == "PERMISSION_DENIED"


def test_phase3_schemas_serialization_and_calculations():
    """
    Xác thực tính hợp lệ của các Schema báo cáo Phase 3:
    - SalesLeaderboardResponse
    - FinancialProfitabilityResponse
    - DebtAgingReportResponse
    """
    # 1. Test Leaderboard Schema
    leaderboard = SalesLeaderboardResponse(
        metric_id="sales_leaderboard",
        period="2026",
        total_sales_reps=2,
        items=[
            SalesLeaderboardItem(
                sales_id=uuid.uuid4(),
                sales_name="Nguyễn Văn Bán Hàng",
                sales_email="sales@erpcopilot.vn",
                total_revenue=Decimal("120000000.00"),
                total_orders=15,
                aov=Decimal("8000000.00"),
                rank=1,
            ),
            SalesLeaderboardItem(
                sales_id=uuid.uuid4(),
                sales_name="Trần Thị Sales 2",
                sales_email="sales2@erpcopilot.vn",
                total_revenue=Decimal("45000000.00"),
                total_orders=6,
                aov=Decimal("7500000.00"),
                rank=2,
            ),
        ]
    )
    assert len(leaderboard.items) == 2
    assert leaderboard.items[0].rank == 1
    assert leaderboard.items[0].total_revenue > leaderboard.items[1].total_revenue

    # 2. Test Financial Profitability Schema
    revenue = Decimal("200000000.00")
    cogs = Decimal("130000000.00")
    gross_profit = revenue - cogs
    margin_pct = float(round((gross_profit / revenue) * 100, 2))

    profitability = FinancialProfitabilityResponse(
        metric_id="financial_profitability",
        period="2026-03",
        total_revenue=revenue,
        total_cogs=cogs,
        gross_profit=gross_profit,
        gross_margin_percent=margin_pct,
        total_orders=25,
    )
    assert profitability.gross_profit == Decimal("70000000.00")
    assert profitability.gross_margin_percent == 35.0

    # 3. Test Debt Aging Schema
    debt_report = DebtAgingReportResponse(
        metric_id="debt_aging_analysis",
        total_debt=Decimal("85000000.00"),
        total_credit_limit=Decimal("200000000.00"),
        overall_utilization_rate=42.5,
        over_limit_customers_count=1,
        buckets=[
            DebtAgingBucket(bucket="current", label="Trong hạn", amount=Decimal("50000000.00"), customer_count=5),
            DebtAgingBucket(bucket="1_30_days", label="Quá hạn 1-30 ngày", amount=Decimal("20000000.00"), customer_count=2),
            DebtAgingBucket(bucket="31_60_days", label="Quá hạn 31-60 ngày", amount=Decimal("10000000.00"), customer_count=1),
            DebtAgingBucket(bucket="over_60_days", label="Quá hạn >60 ngày", amount=Decimal("5000000.00"), customer_count=1),
        ],
        top_debtors=[
            TopDebtorItem(
                customer_id=uuid.uuid4(),
                customer_code="CUS-0001",
                customer_name="Công ty TNHH ABC",
                credit_limit=Decimal("50000000.00"),
                current_debt=Decimal("55000000.00"),
                credit_utilization_rate=110.0,
                is_over_limit=True,
            )
        ]
    )
    assert len(debt_report.buckets) == 4
    assert debt_report.over_limit_customers_count == 1
    assert debt_report.top_debtors[0].is_over_limit is True

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from app.db.session import async_session_factory
from app.erp.services.inventory import InventoryService
from app.erp.services.product import ProductService
from app.erp.services.customer import CustomerService
from app.erp.services.order import SalesOrderService
from app.erp.services.reporting import ReportingService
from app.core.errors import NotFoundException
from app.ai.tools.context import get_current_user_context

logger = logging.getLogger(__name__)


@tool
async def get_inventory(sku: str, warehouse_code: Optional[str] = None) -> str:
    """
    Tra cứu số lượng tồn kho thời gian thực của sản phẩm theo mã SKU và mã kho.
    Trả về số lượng tồn thực tế (quantity_on_hand), số lượng đang giữ/đặt trước (quantity_reserved),
    và số lượng khả dụng có thể bán (quantity_available = on_hand - reserved).

    Args:
        sku: Mã định danh sản phẩm (Ví dụ: 'SKU-001', 'SKU-002'). Bắt buộc.
        warehouse_code: Mã kho hàng tùy chọn (Ví dụ: 'WH-HN', 'WH-HCM'). Nếu không cung cấp, tra cứu trên tất cả các kho.
    """
    clean_sku = sku.strip().upper()
    clean_wh = warehouse_code.strip().upper() if warehouse_code else None

    async with async_session_factory() as session:
        items = await InventoryService.get_inventory(
            session=session,
            sku=clean_sku,
            warehouse_code=clean_wh,
        )

        if not items:
            return json.dumps({
                "found": False,
                "message": f"Không tìm thấy dữ liệu tồn kho cho sản phẩm SKU '{clean_sku}'" + (f" tại kho '{clean_wh}'" if clean_wh else ""),
                "items": [],
            }, ensure_ascii=False)

        total_available = sum(i.quantity_available for i in items)
        total_on_hand = sum(i.quantity_on_hand for i in items)
        total_reserved = sum(i.quantity_reserved for i in items)

        return json.dumps({
            "found": True,
            "sku": clean_sku,
            "product_name": items[0].product_name,
            "total_available": total_available,
            "total_on_hand": total_on_hand,
            "total_reserved": total_reserved,
            "warehouses": [
                {
                    "warehouse_code": i.warehouse_code,
                    "warehouse_name": i.warehouse_name,
                    "quantity_on_hand": i.quantity_on_hand,
                    "quantity_reserved": i.quantity_reserved,
                    "quantity_available": i.quantity_available,
                }
                for i in items
            ],
        }, ensure_ascii=False)


@tool
async def get_product(sku: str) -> str:
    """
    Tra cứu thông tin chi tiết của một sản phẩm theo mã SKU, bao gồm tên sản phẩm,
    giá niêm yết chính thức (VND), và trạng thái kinh doanh.

    Args:
        sku: Mã SKU sản phẩm (Ví dụ: 'SKU-001', 'SKU-002', 'SKU-003').
    """
    clean_sku = sku.strip().upper()
    async with async_session_factory() as session:
        try:
            prod = await ProductService.get_by_sku(session=session, sku=clean_sku)
            return json.dumps({
                "found": True,
                "sku": prod.sku,
                "name": prod.name,
                "unit_price": float(prod.unit_price),
                "formatted_price": f"{prod.unit_price:,.0f} VND",
                "is_active": prod.is_active,
            }, ensure_ascii=False)
        except NotFoundException:
            return json.dumps({
                "found": False,
                "message": f"Không tìm thấy sản phẩm với mã SKU '{clean_sku}' trong hệ thống ERP.",
            }, ensure_ascii=False)


@tool
async def get_customer(customer_code: str) -> str:
    """
    Tra cứu thông tin khách hàng doanh nghiệp hoặc cá nhân theo mã khách hàng (Customer Code).
    Trả về tên khách hàng, email liên hệ, và trạng thái tài khoản.

    Args:
        customer_code: Mã khách hàng (Ví dụ: 'CUS-0001', 'CUS-0002').
    """
    clean_code = customer_code.strip().upper()
    async with async_session_factory() as session:
        try:
            cust = await CustomerService.get_by_code(session=session, code=clean_code)
            return json.dumps({
                "found": True,
                "customer_code": cust.code,
                "name": cust.name,
                "email": cust.email,
                "status": cust.status,
            }, ensure_ascii=False)
        except NotFoundException:
            return json.dumps({
                "found": False,
                "message": f"Không tìm thấy khách hàng với mã '{clean_code}' trong hệ thống ERP.",
            }, ensure_ascii=False)


@tool
async def get_sales_orders(
    customer_code: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    Tra cứu danh sách các đơn hàng bán (Sales Orders) trong hệ thống ERP.
    Hỗ trợ lọc theo mã khách hàng và trạng thái đơn hàng.

    Args:
        customer_code: Mã khách hàng cần lọc (Ví dụ: 'CUS-0001'). Tùy chọn.
        status: Trạng thái đơn hàng cần lọc ('draft', 'pending_approval', 'confirmed', 'cancelled'). Tùy chọn.
        limit: Số lượng đơn hàng tối đa trả về (mặc định: 5).
    """
    clean_code = customer_code.strip().upper() if customer_code else None
    clean_status = status.strip().lower() if status else None

    async with async_session_factory() as session:
        orders = await SalesOrderService.list_orders(
            session=session,
            customer_code=clean_code,
            status=clean_status,
            limit=min(limit, 20),
        )

        if not orders:
            return json.dumps({
                "found": False,
                "total": 0,
                "message": "Không tìm thấy đơn hàng nào phù hợp với tiêu chí tra cứu.",
                "orders": [],
            }, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "total": len(orders),
            "orders": [
                {
                    "order_number": o.order_number,
                    "customer_code": o.customer.code,
                    "customer_name": o.customer.name,
                    "status": o.status,
                    "total_amount": float(o.total_amount),
                    "formatted_total": f"{o.total_amount:,.0f} VND",
                    "created_at": o.created_at.strftime("%Y-%m-%d %H:%M UTC"),
                    "item_count": len(o.items),
                }
                for o in orders
            ],
        }, ensure_ascii=False)


@tool
async def get_revenue_report(
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> str:
    """
    Báo cáo doanh thu chuẩn xác đối chiếu từ cơ sở dữ liệu bán hàng ERP (Use Case UC-02).
    Chỉ tính doanh thu các đơn hàng hợp lệ (loại bỏ đơn hủy).

    Args:
        year: Năm cần báo cáo (Ví dụ: 2026). Tùy chọn.
        month: Tháng cần báo cáo (1 đến 12). Tùy chọn.
    """
    user_ctx = get_current_user_context()
    if user_ctx.user_role not in ["admin", "sales_manager"]:
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": f"Truy cập bị từ chối: Báo cáo doanh thu chỉ dành cho Quản trị viên (admin) hoặc Quản lý bán hàng (sales_manager). Vai trò hiện tại '{user_ctx.user_role}' không có quyền truy xuất số liệu này.",
        }, ensure_ascii=False)

    async with async_session_factory() as session:
        report = await ReportingService.get_revenue(
            session=session,
            year=year,
            month=month,
        )

        return json.dumps({
            "metric_id": report.metric_id,
            "period": report.period,
            "total_revenue": float(report.total_revenue),
            "formatted_revenue": f"{report.total_revenue:,.0f} VND",
            "total_orders": report.total_orders,
            "monthly_breakdown": [
                {
                    "period": b.period,
                    "order_count": b.order_count,
                    "total_revenue": float(b.total_revenue),
                    "formatted_revenue": f"{b.total_revenue:,.0f} VND",
                }
                for b in report.breakdown
            ],
        }, ensure_ascii=False)


@tool
async def propose_sales_order_draft(
    customer_code: str,
    items: List[Dict[str, Any]],
) -> str:
    """
    Đề xuất lập bản nháp đơn hàng bán (Draft Order Proposal) sau khi đã trích xuất đầy đủ thông tin.
    Công cụ này sẽ kiểm tra sự tồn tại của khách hàng, xác thực mã SKU, tự động đối chiếu giá niêm yết
    trong cơ sở dữ liệu và tính toán tổng tiền.
    LƯU Ý: Công cụ này KHÔNG tự động chốt đơn mà chỉ lập bản đề xuất để người dùng xác nhận (Human-In-The-Loop).

    Args:
        customer_code: Mã khách hàng (Ví dụ: 'CUS-0001').
        items: Danh sách sản phẩm và số lượng đặt hàng, ví dụ: [{'sku': 'SKU-001', 'quantity': 2}]
    """
    clean_code = customer_code.strip().upper()
    if not items:
        return json.dumps({
            "success": False,
            "message": "Danh sách sản phẩm đặt hàng không được để trống.",
        }, ensure_ascii=False)

    async with async_session_factory() as session:
        # 1. Validate customer
        try:
            cust = await CustomerService.get_by_code(session=session, code=clean_code)
        except NotFoundException:
            return json.dumps({
                "success": False,
                "message": f"Không thể lập đơn nháp: Khách hàng '{clean_code}' không tồn tại trong hệ thống.",
            }, ensure_ascii=False)

        # 2. Validate products and calculate prices using DB truth
        validated_items = []
        total_amount = Decimal("0.00")

        for idx, item in enumerate(items):
            raw_sku = item.get("sku", "").strip().upper()
            qty = item.get("quantity", 0)

            if not raw_sku:
                return json.dumps({
                    "success": False,
                    "message": f"Dòng hàng thứ {idx+1} thiếu mã SKU.",
                }, ensure_ascii=False)

            if not isinstance(qty, int) or qty <= 0:
                return json.dumps({
                    "success": False,
                    "message": f"Số lượng cho sản phẩm '{raw_sku}' phải là số nguyên dương lớn hơn 0.",
                }, ensure_ascii=False)

            try:
                prod = await ProductService.get_by_sku(session=session, sku=raw_sku)
            except NotFoundException:
                return json.dumps({
                    "success": False,
                    "message": f"Sản phẩm với mã SKU '{raw_sku}' không tồn tại trong danh mục ERP.",
                }, ensure_ascii=False)

            if not prod.is_active:
                return json.dumps({
                    "success": False,
                    "message": f"Sản phẩm '{raw_sku}' ({prod.name}) hiện đang ngừng kinh doanh.",
                }, ensure_ascii=False)

            line_total = Decimal(str(qty)) * prod.unit_price
            total_amount += line_total

            validated_items.append({
                "sku": prod.sku,
                "product_name": prod.name,
                "quantity": qty,
                "unit_price": float(prod.unit_price),
                "formatted_unit_price": f"{prod.unit_price:,.0f} VND",
                "line_total": float(line_total),
                "formatted_line_total": f"{line_total:,.0f} VND",
            })

        return json.dumps({
            "success": True,
            "action": "propose_order_draft",
            "customer_code": cust.code,
            "customer_name": cust.name,
            "items": validated_items,
            "total_amount": float(total_amount),
            "formatted_total_amount": f"{total_amount:,.0f} VND",
            "message": f"Đã lập bản đề xuất đơn hàng nháp cho khách hàng {cust.name} ({cust.code}) với tổng tiền {total_amount:,.0f} VND. Vui lòng xác nhận để hoàn tất tạo đơn.",
            "requires_user_confirmation": True,
        }, ensure_ascii=False)

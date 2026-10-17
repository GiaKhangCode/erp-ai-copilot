import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from sqlalchemy import select

from app.db.session import async_session_factory
from app.erp.models import Customer, Product, SalesOrder
from app.erp.services.inventory import InventoryService
from app.erp.services.product import ProductService
from app.erp.services.customer import CustomerService
from app.erp.services.order import SalesOrderService
from app.erp.services.reporting import ReportingService
from app.core.errors import NotFoundException
from app.ai.tools.context import get_current_user_context

logger = logging.getLogger(__name__)


@tool
async def get_inventory(sku: Optional[str] = None, warehouse_code: Optional[str] = None) -> str:
    """
    Tra cứu số lượng tồn kho thời gian thực trong hệ thống ERP.
    Trả về số lượng tồn thực tế (quantity_on_hand), số lượng đang giữ/đặt trước (quantity_reserved),
    và số lượng khả dụng có thể bán (quantity_available = on_hand - reserved).

    Args:
        sku: Mã SKU sản phẩm (Ví dụ: 'SKU-001', 'SKU-002') HOẶC tên sản phẩm (Ví dụ: 'Chuột Ergonomic', 'Laptop Pro'). Nếu không truyền (None), tra cứu trên tất cả sản phẩm.
        warehouse_code: Mã kho hàng tùy chọn (Ví dụ: 'WH-HN', 'WH-HCM'). Nếu không cung cấp, tra cứu trên tất cả các kho.
    """
    clean_sku = sku.strip() if sku else None
    clean_wh = warehouse_code.strip().upper() if warehouse_code else None

    async with async_session_factory() as session:
        # Nếu clean_sku không bắt đầu bằng 'SKU-', thử tìm mã SKU theo tên sản phẩm
        resolved_sku = clean_sku
        if clean_sku and not clean_sku.upper().startswith("SKU-"):
            stmt = select(Product).where(Product.name.ilike(f"%{clean_sku}%")).limit(1)
            res = await session.execute(stmt)
            matched_prod = res.scalar_one_or_none()
            if matched_prod:
                resolved_sku = matched_prod.sku
            else:
                resolved_sku = clean_sku.upper()
        elif clean_sku:
            resolved_sku = clean_sku.upper()

        items = await InventoryService.get_inventory(
            session=session,
            sku=resolved_sku,
            warehouse_code=clean_wh,
        )

        if not items:
            msg = f"Không tìm thấy dữ liệu tồn kho"
            if clean_sku:
                msg += f" cho sản phẩm '{clean_sku}'"
            if clean_wh:
                msg += f" tại kho '{clean_wh}'"
            return json.dumps({
                "found": False,
                "message": msg,
                "items": [],
            }, ensure_ascii=False)

        total_available = sum(i.quantity_available for i in items)
        total_on_hand = sum(i.quantity_on_hand for i in items)
        total_reserved = sum(i.quantity_reserved for i in items)

        return json.dumps({
            "found": True,
            "sku_filter": resolved_sku,
            "warehouse_filter": clean_wh,
            "total_items": len(items),
            "total_available": total_available,
            "total_on_hand": total_on_hand,
            "total_reserved": total_reserved,
            "items": [
                {
                    "sku": i.product_sku,
                    "product_name": i.product_name,
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
async def list_products(search: Optional[str] = None, is_active: Optional[bool] = None, limit: int = 50) -> str:
    """
    Tra cứu danh sách tất cả các mặt hàng / sản phẩm đang kinh doanh trong hệ thống ERP.
    Hỗ trợ tìm kiếm theo từ khóa (tên sản phẩm hoặc mã SKU).
    Trả về danh sách sản phẩm gồm mã SKU, tên sản phẩm, đơn giá niêm yết (VND), và trạng thái hoạt động.

    Args:
        search: Từ khóa tìm kiếm theo tên hoặc mã SKU (Ví dụ: 'chuột', 'laptop', 'SKU-001'). Tùy chọn.
        is_active: Lọc sản phẩm đang hoạt động (True/False). Mặc định None (lấy tất cả).
        limit: Số lượng sản phẩm tối đa (mặc định: 50).
    """
    clean_search = search.strip() if search else None
    async with async_session_factory() as session:
        prods = await ProductService.list_products(
            session=session,
            limit=min(limit, 100),
            is_active=is_active,
            search=clean_search,
        )
        if not prods:
            msg = "Không tìm thấy sản phẩm nào trong hệ thống ERP."
            if clean_search:
                msg = f"Không tìm thấy sản phẩm nào phù hợp với từ khóa '{clean_search}' trong hệ thống ERP."
            return json.dumps({
                "found": False,
                "total": 0,
                "message": msg,
                "products": [],
            }, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "total": len(prods),
            "products": [
                {
                    "sku": p.sku,
                    "name": p.name,
                    "unit_price": float(p.unit_price),
                    "formatted_price": f"{p.unit_price:,.0f} VND",
                    "is_active": p.is_active,
                }
                for p in prods
            ],
        }, ensure_ascii=False)


@tool
async def get_product(sku: str) -> str:
    """
    Tra cứu thông tin chi tiết của một sản phẩm theo mã SKU hoặc tên sản phẩm,
    bao gồm mã SKU, tên sản phẩm, giá niêm yết chính thức (VND), và trạng thái kinh doanh.

    Args:
        sku: Mã SKU sản phẩm (Ví dụ: 'SKU-001') HOẶC tên sản phẩm (Ví dụ: 'Chuột Ergonomic', 'Laptop Pro').
    """
    clean_term = sku.strip()
    async with async_session_factory() as session:
        prod = None
        try:
            prod = await ProductService.get_by_sku(session=session, sku=clean_term.upper())
        except NotFoundException:
            stmt = select(Product).where(Product.name.ilike(f"%{clean_term}%")).limit(1)
            res = await session.execute(stmt)
            prod = res.scalar_one_or_none()

        if not prod:
            return json.dumps({
                "found": False,
                "message": f"Không tìm thấy sản phẩm với thông tin '{clean_term}' trong hệ thống ERP.",
            }, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "sku": prod.sku,
            "name": prod.name,
            "unit_price": float(prod.unit_price),
            "formatted_price": f"{prod.unit_price:,.0f} VND",
            "is_active": prod.is_active,
        }, ensure_ascii=False)


@tool
async def get_customer(customer_code: str) -> str:
    """
    Tra cứu thông tin khách hàng doanh nghiệp hoặc cá nhân theo mã khách hàng (Customer Code) hoặc tên công ty/khách hàng.
    Trả về mã code, tên khách hàng, email liên hệ, và trạng thái tài khoản.

    Args:
        customer_code: Mã khách hàng (Ví dụ: 'CUS-0001') HOẶC tên công ty/khách hàng (Ví dụ: 'Công ty Á Châu', 'Toàn Cầu').
    """
    clean_term = customer_code.strip()
    async with async_session_factory() as session:
        cust = None
        try:
            cust = await CustomerService.get_by_code(session=session, code=clean_term.upper())
        except NotFoundException:
            stmt = select(Customer).where(Customer.name.ilike(f"%{clean_term}%")).limit(1)
            res = await session.execute(stmt)
            cust = res.scalar_one_or_none()

        if not cust:
            return json.dumps({
                "found": False,
                "message": f"Không tìm thấy khách hàng với thông tin '{clean_term}' trong hệ thống ERP.",
            }, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "customer_code": cust.code,
            "name": cust.name,
            "email": cust.email,
            "status": cust.status,
        }, ensure_ascii=False)


@tool
async def list_customers(search: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> str:
    """
    Tra cứu danh sách khách hàng doanh nghiệp hoặc cá nhân trong hệ thống ERP.
    Hỗ trợ tìm kiếm theo từ khóa (tên khách hàng hoặc mã code).
    Trả về danh sách khách hàng gồm mã code, tên khách hàng, email và trạng thái tài khoản.

    Args:
        search: Từ khóa tìm kiếm theo tên hoặc mã khách hàng (Ví dụ: 'Á Châu', 'Toàn Cầu', 'CUS-0001'). Tùy chọn.
        status: Lọc theo trạng thái ('active', 'inactive'). Mặc định None (tất cả).
        limit: Số lượng khách hàng tối đa (mặc định: 50).
    """
    clean_search = search.strip() if search else None
    async with async_session_factory() as session:
        custs = await CustomerService.list_customers(
            session=session,
            limit=min(limit, 100),
            status=status,
            search=clean_search,
        )
        if not custs:
            msg = "Không tìm thấy khách hàng nào trong hệ thống ERP."
            if clean_search:
                msg = f"Không tìm thấy khách hàng nào phù hợp với từ khóa '{clean_search}' trong hệ thống ERP."
            return json.dumps({
                "found": False,
                "total": 0,
                "message": msg,
                "customers": [],
            }, ensure_ascii=False)

        return json.dumps({
            "found": True,
            "total": len(custs),
            "customers": [
                {
                    "customer_code": c.code,
                    "name": c.name,
                    "email": c.email,
                    "status": c.status,
                }
                for c in custs
            ],
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

    user_ctx = get_current_user_context()
    created_by_filter = None
    if user_ctx.user_role == "sales_rep" and user_ctx.user_id:
        try:
            import uuid as _uuid
            created_by_filter = _uuid.UUID(str(user_ctx.user_id))
        except Exception:
            pass

    async with async_session_factory() as session:
        orders = await SalesOrderService.list_orders(
            session=session,
            customer_code=clean_code,
            status=clean_status,
            limit=min(limit, 20),
            created_by=created_by_filter,
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
    can_view_revenue = False
    if user_ctx.user_permissions:
        can_view_revenue = "*" in user_ctx.user_permissions or "reports:revenue_view" in user_ctx.user_permissions
    elif user_ctx.user_role in ["admin", "sales_manager", "director"]:
        can_view_revenue = True

    if not can_view_revenue or user_ctx.user_role in ["warehouse_keeper", "sales_rep"]:
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": f"Truy cập bị từ chối: Báo cáo doanh thu chỉ dành cho Quản trị viên, Giám đốc hoặc Quản lý bán hàng. Vai trò hiện tại '{user_ctx.user_role}' không có quyền truy xuất số liệu này.",
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
    Công cụ này sẽ kiểm tra khách hàng, xác thực sản phẩm, tự động snapshot giá niêm yết trong CSDL ERP và tính tổng tiền.
    LƯU Ý: Công cụ này KHÔNG tự động chốt đơn mà lập bản đề xuất để người dùng xác nhận (Human-In-The-Loop).

    Args:
        customer_code: Mã khách hàng (Ví dụ: 'CUS-0001') HOẶC Tên công ty / Tên khách hàng (Ví dụ: 'Công ty Á Châu', 'Tập đoàn Bán lẻ Toàn Cầu').
        items: Danh sách sản phẩm và số lượng đặt hàng, ví dụ: [{'sku': 'SKU-001', 'quantity': 2}] hoặc [{'sku': 'Chuột Ergonomic', 'quantity': 2}].
    """
    user_ctx = get_current_user_context()
    is_denied = False
    if user_ctx.user_role == "warehouse_keeper":
        is_denied = True
    elif user_ctx.user_permissions is not None:
        is_denied = "*" not in user_ctx.user_permissions and "orders:create" not in user_ctx.user_permissions
    elif user_ctx.user_role is not None:
        is_denied = user_ctx.user_role not in ["admin", "sales_manager", "sales_rep"]

    if is_denied:
        return json.dumps({
            "success": False,
            "error": "PERMISSION_DENIED",
            "message": f"Truy cập bị từ chối: Tài khoản '{user_ctx.user_name or user_ctx.user_email or 'hiện tại'}' với vai trò '{user_ctx.user_role or 'thủ kho'}' không có quyền lập đơn hàng (yêu cầu quyền 'orders:create'). Vui lòng liên hệ bộ phận Kinh doanh hoặc Quản trị viên hệ thống.",
        }, ensure_ascii=False)

    clean_code = customer_code.strip()
    if not items:
        return json.dumps({
            "success": False,
            "message": "Danh sách sản phẩm đặt hàng không được để trống.",
        }, ensure_ascii=False)

    async with async_session_factory() as session:
        # 1. Validate customer (hỗ trợ cả Mã khách hàng lẫn Tên khách hàng)
        cust = None
        try:
            cust = await CustomerService.get_by_code(session=session, code=clean_code.upper())
        except NotFoundException:
            stmt = select(Customer).where(Customer.name.ilike(f"%{clean_code}%")).limit(1)
            res = await session.execute(stmt)
            cust = res.scalar_one_or_none()

        if not cust:
            return json.dumps({
                "success": False,
                "message": f"Không thể lập đơn nháp: Không tìm thấy khách hàng nào với thông tin '{clean_code}' trong hệ thống ERP.",
            }, ensure_ascii=False)

        # 2. Validate products and calculate prices using DB truth
        validated_items = []
        total_amount = Decimal("0.00")

        for idx, item in enumerate(items):
            raw_sku = str(item.get("sku") or item.get("product_name") or "").strip()
            qty = item.get("quantity", 0)

            if not raw_sku:
                return json.dumps({
                    "success": False,
                    "message": f"Dòng hàng thứ {idx+1} thiếu mã SKU hoặc tên sản phẩm.",
                }, ensure_ascii=False)

            if not isinstance(qty, int) or qty <= 0:
                try:
                    qty = int(qty)
                except Exception:
                    qty = 0
                if qty <= 0:
                    return json.dumps({
                        "success": False,
                        "message": f"Số lượng cho sản phẩm '{raw_sku}' phải là số nguyên dương lớn hơn 0.",
                    }, ensure_ascii=False)

            # Thử tìm theo mã SKU trước, nếu không thấy thì tìm theo tên sản phẩm
            prod = None
            try:
                prod = await ProductService.get_by_sku(session=session, sku=raw_sku.upper())
            except NotFoundException:
                stmt = select(Product).where(Product.name.ilike(f"%{raw_sku}%")).limit(1)
                res = await session.execute(stmt)
                prod = res.scalar_one_or_none()

            if not prod:
                return json.dumps({
                    "success": False,
                    "message": f"Sản phẩm với thông tin '{raw_sku}' không tồn tại trong danh mục ERP.",
                }, ensure_ascii=False)

            if not prod.is_active:
                return json.dumps({
                    "success": False,
                    "message": f"Sản phẩm '{prod.sku}' ({prod.name}) hiện đang ngừng kinh doanh.",
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

        # 3. Create Draft SalesOrder in database
        import uuid as _uuid
        import hashlib as _hashlib
        from app.erp.schemas import OrderDraftCreate, OrderItemDraft as ERPOrderItemDraft
        from app.erp.models import ApprovalRequest

        user_ctx = get_current_user_context()
        actor_uuid = None
        if user_ctx.user_id:
            try:
                actor_uuid = _uuid.UUID(user_ctx.user_id)
            except Exception:
                pass

        draft_payload = OrderDraftCreate(
            customer_code=cust.code,
            items=[
                ERPOrderItemDraft(sku=it["sku"], quantity=it["quantity"])
                for it in validated_items
            ],
        )

        order = await SalesOrderService.create_order_draft(
            session=session,
            payload=draft_payload,
            actor_id=actor_uuid,
        )

        # 4. Create ApprovalRequest for Human-in-the-Loop approval
        approval_payload = {
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_code": cust.code,
            "customer_name": cust.name,
            "total_amount": float(order.total_amount),
            "source_type": "copilot_chat",
            "items": validated_items,
        }
        payload_bytes = json.dumps(approval_payload, sort_keys=True).encode("utf-8")
        payload_hash = _hashlib.sha256(payload_bytes).hexdigest()

        approval_req = ApprovalRequest(
            id=_uuid.uuid4(),
            action_type="create_sales_order_draft",
            target_id=order.id,
            payload=approval_payload,
            payload_hash=payload_hash,
            status="pending",
            requested_by=actor_uuid or _uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        session.add(approval_req)
        await session.commit()

        return json.dumps({
            "success": True,
            "action": "create_sales_order_draft",
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_code": cust.code,
            "customer_name": cust.name,
            "items": validated_items,
            "total_amount": float(order.total_amount),
            "formatted_total_amount": f"{order.total_amount:,.0f} VND",
            "message": f"Đã khởi tạo đơn hàng nháp **{order.order_number}** cho khách hàng **{cust.name}** ({cust.code}) với tổng tiền **{order.total_amount:,.0f} VND**. Đơn hàng đã được lưu vào hệ thống ở trạng thái Bản nháp (draft) và đang chờ phê duyệt tại Hộp thư phê duyệt.",
            "requires_user_confirmation": True,
        }, ensure_ascii=False)


@tool
async def deliver_sales_order(order_number: str) -> str:
    """
    Xác nhận đóng gói và xuất kho cho đơn hàng bán đã được phê duyệt (CONFIRMED).
    Chỉ dành cho Thủ kho (warehouse_keeper) hoặc Quản trị viên (admin).
    Thao tác này sẽ tự động trừ tồn kho thực tế (on_hand) và giải phóng số lượng giữ đơn (reserved).

    Args:
        order_number: Mã số đơn hàng cần xuất kho (Ví dụ: 'SO-20261015-ABCD').
    """
    user_ctx = get_current_user_context()
    if user_ctx.user_role not in ["warehouse_keeper", "admin"]:
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": f"Truy cập bị từ chối: Chỉ Thủ kho (warehouse_keeper) hoặc Quản trị viên mới có quyền xuất kho đơn hàng. Vai trò hiện tại '{user_ctx.user_role}' không được phép.",
        }, ensure_ascii=False)

    clean_order_num = order_number.strip().upper()
    async with async_session_factory() as session:
        stmt = select(SalesOrder).where(SalesOrder.order_number == clean_order_num)
        res = await session.execute(stmt)
        order = res.scalar_one_or_none()
        if not order:
            return json.dumps({
                "found": False,
                "message": f"Không tìm thấy đơn hàng với mã '{clean_order_num}' trong hệ thống.",
            }, ensure_ascii=False)

        try:
            actor_id = user_ctx.user_id or order.created_by
            delivered_order = await SalesOrderService.deliver_order(
                session=session,
                order_id=order.id,
                actor_id=actor_id,
            )
            return json.dumps({
                "success": True,
                "order_number": delivered_order.order_number,
                "status": delivered_order.status,
                "message": f"Đã xuất kho thành công đơn hàng **{delivered_order.order_number}**. Tồn kho thực tế đã được cập nhật trừ đi tương ứng và đơn hàng chuyển sang trạng thái Hoàn tất giao hàng (delivered).",
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Lỗi khi xuất kho đơn hàng: {str(e)}",
            }, ensure_ascii=False)


@tool
async def adjust_inventory(
    sku: str,
    warehouse_code: str,
    delta_quantity: int,
    reason: str,
) -> str:
    """
    Lập phiếu kiểm kê và điều chỉnh tăng (+) hoặc giảm (-) tồn kho thực tế trong hệ thống ERP.
    Chỉ dành cho Thủ kho (warehouse_keeper) hoặc Quản trị viên (admin).

    Args:
        sku: Mã SKU sản phẩm cần điều chỉnh (Ví dụ: 'SKU-001').
        warehouse_code: Mã kho hàng (Ví dụ: 'WH-HN', 'WH-HCM').
        delta_quantity: Số lượng điều chỉnh (+20: tăng thêm 20, -5: hao hụt giảm 5). Không được bằng 0.
        reason: Lý do điều chỉnh (Ví dụ: 'Kiểm kê định kỳ tháng 10', 'Hàng vỡ hỏng do vận chuyển').
    """
    user_ctx = get_current_user_context()
    if user_ctx.user_role not in ["warehouse_keeper", "admin"]:
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": f"Truy cập bị từ chối: Chỉ Thủ kho (warehouse_keeper) hoặc Quản trị viên mới có quyền điều chỉnh tồn kho. Vai trò hiện tại '{user_ctx.user_role}' không được phép.",
        }, ensure_ascii=False)

    import uuid as _uuid
    actor_id = user_ctx.user_id or _uuid.UUID("00000000-0000-0000-0000-000000000001")
    async with async_session_factory() as session:
        try:
            adj = await InventoryService.adjust_inventory(
                session=session,
                sku=sku,
                warehouse_code=warehouse_code,
                delta_quantity=delta_quantity,
                reason=reason,
                user_id=actor_id,
            )
            return json.dumps({
                "success": True,
                "sku": adj.sku,
                "warehouse_code": adj.warehouse_code,
                "delta_quantity": adj.delta_quantity,
                "quantity_before": adj.quantity_before,
                "quantity_after": adj.quantity_after,
                "reason": adj.reason,
                "message": f"Đã lập phiếu điều chỉnh tồn kho thành công cho sản phẩm **{adj.sku}** tại kho **{adj.warehouse_code}**. Tồn kho trước: {adj.quantity_before} -> Tồn kho sau: **{adj.quantity_after}** (thay đổi {adj.delta_quantity:+d}). Lý do: {adj.reason}.",
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Không thể điều chỉnh tồn kho: {str(e)}",
            }, ensure_ascii=False)


@tool
async def generate_sales_quotation(order_identifier: str) -> str:
    """
    Xuất file PDF Báo giá kinh doanh (Sales Quotation / Proforma Invoice) chính thức cho đơn hàng.
    Tự động chuẩn bị file PDF và tạo thẻ tệp đính kèm để người dùng có thể xem trước hoặc tải về trực tiếp trong khung chat.

    Args:
        order_identifier: Mã số đơn hàng (Ví dụ: 'SO-2026-001', 'SO-20260315-A1B2') HOẶC ID (UUID) của đơn hàng cần xuất báo giá.
    """
    user_ctx = get_current_user_context()
    if user_ctx.user_role == "warehouse_keeper":
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": "Truy cập bị từ chối: Báo giá kinh doanh chỉ dành cho nhân viên kinh doanh hoặc ban giám đốc. Thủ kho không có thẩm quyền tạo hoặc xuất báo giá.",
        }, ensure_ascii=False)

    if user_ctx.user_permissions and "*" not in user_ctx.user_permissions and "orders:read" not in user_ctx.user_permissions:
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": "Bạn không có quyền xem đơn hàng và xuất báo giá (orders:read).",
        }, ensure_ascii=False)

    clean_id = order_identifier.strip()
    import uuid as _uuid
    async with async_session_factory() as session:
        # Resolve order
        order = None
        try:
            order_uuid = _uuid.UUID(clean_id)
            order = await SalesOrderService.get_order_by_id(session, order_uuid)
        except (ValueError, NotFoundException):
            pass

        if not order:
            stmt = select(SalesOrder).where(SalesOrder.order_number.ilike(f"%{clean_id}%")).limit(1)
            res = await session.execute(stmt)
            order_found = res.scalar_one_or_none()
            if order_found:
                order = await SalesOrderService.get_order_by_id(session, order_found.id)

        if not order:
            return json.dumps({
                "error": "ORDER_NOT_FOUND",
                "message": f"Không tìm thấy đơn hàng nào khớp với mã hoặc ID '{clean_id}'. Vui lòng kiểm tra lại.",
            }, ensure_ascii=False)

        pdf_url = f"/api/v1/orders/{order.id}/quotation/pdf"
        filename = f"Bao_Gia_{order.order_number}.pdf"
        total_vnd = f"{int(order.total_amount):,} đ".replace(",", ".")

        items_summary = [
            f"- {item.product.name if item.product else 'Sản phẩm'} ({item.product.sku if item.product else 'N/A'}): {item.quantity} chiếc x {int(item.unit_price):,} đ = {int(item.line_total):,} đ".replace(",", ".")
            for item in order.items
        ]

        # Special Markdown tag for Frontend to render File Attachment Card
        attachment_tag = f":::quotation[{order.id}|{order.order_number}|{order.customer.name if order.customer else 'Khách hàng'}|{float(order.total_amount)}|{pdf_url}|{filename}]:::"

        msg = (
            f"### 📄 Báo giá kinh doanh: {order.order_number}\n\n"
            f"- **Khách hàng:** {order.customer.name if order.customer else 'N/A'} ({order.customer.code if order.customer else 'N/A'})\n"
            f"- **Trạng thái đơn hàng:** `{order.status.upper()}`\n"
            f"- **Tổng giá trị báo giá:** **{total_vnd}**\n\n"
            f"**Chi tiết danh mục sản phẩm:**\n"
            + "\n".join(items_summary)
            + f"\n\n{attachment_tag}\n\n"
            f"*(Bạn có thể bấm nút **Xem trước** hoặc **Tải file** ở thẻ tệp tin phía trên để mở file PDF)*"
        )

        return json.dumps({
            "success": True,
            "order_id": str(order.id),
            "order_number": order.order_number,
            "customer_name": order.customer.name if order.customer else "N/A",
            "total_amount": float(order.total_amount),
            "pdf_url": pdf_url,
            "filename": filename,
            "formatted_message": msg,
        }, ensure_ascii=False)


@tool
async def check_customer_credit(
    customer_identifier: str,
    additional_amount: Optional[float] = 0.0,
) -> str:
    """
    Kiểm tra hạn mức công nợ (Credit Limit), dư nợ hiện tại và đánh giá rủi ro tín dụng của khách hàng.
    Tự động cảnh báo nếu giá trị đơn hàng vượt quá hạn mức cho phép.

    Args:
        customer_identifier: Mã khách hàng (Ví dụ: 'CUS-001', 'CUS-0001') HOẶC Tên công ty/khách hàng (Ví dụ: 'FPT', 'TNHH ABC').
        additional_amount: Số tiền dự kiến lên đơn thêm (VND) để tính toán khả năng tài chính sau đơn hàng mới. Mặc định là 0.
    """
    user_ctx = get_current_user_context()
    if user_ctx.user_role == "warehouse_keeper":
        return json.dumps({
            "error": "PERMISSION_DENIED",
            "message": "Truy cập bị từ chối: Thẩm định công nợ khách hàng chỉ dành cho bộ phận kinh doanh và ban quản lý. Thủ kho không có quyền truy xuất dữ liệu tín dụng này.",
        }, ensure_ascii=False)
    async with async_session_factory() as session:
        try:
            from decimal import Decimal
            res = await CustomerService.check_credit_limit(
                session=session,
                customer_id_or_code=customer_identifier.strip(),
                additional_amount=Decimal(str(additional_amount or 0)),
            )

            credit_limit_fmt = f"{int(res['credit_limit']):,} đ".replace(",", ".")
            current_debt_fmt = f"{int(res['current_debt']):,} đ".replace(",", ".")
            projected_debt_fmt = f"{int(res['projected_debt']):,} đ".replace(",", ".")
            available_fmt = f"{int(res['available_credit']):,} đ".replace(",", ".")
            rate = res["credit_utilization_rate"]
            is_exceeded = res["is_exceeded"]

            if is_exceeded:
                status_note = f"⚠️ **CẢNH BÁO NGUY CƠ: VƯỢT HẠN MỨC CÔNG NỢ!** Dư nợ dự kiến ({projected_debt_fmt}) đã vượt hạn mức cho phép ({credit_limit_fmt}) thêm {abs(int(res['available_credit'])):,} đ. Cần có sự phê duyệt đặc biệt từ Giám đốc (Director) hoặc thu hồi nợ cũ trước khi tiếp tục lên đơn.".replace(",", ".")
            elif rate >= 80.0:
                status_note = f"⚠️ **CẢNH BÁO MỨC ĐỘ RỦI RO CAO:** Tỷ lệ sử dụng hạn mức công nợ đã đạt **{rate}%** (còn khả dụng: {available_fmt}). Cần nhắc khách hàng thanh toán sớm."
            else:
                status_note = f"✅ **TÌNH TRẠNG TÍN DỤNG TỐT:** Tỷ lệ sử dụng công nợ ở mức an toàn **{rate}%** (còn khả dụng: {available_fmt}). Khách hàng đủ điều kiện tiếp tục lên đơn hàng."

            summary_msg = (
                f"### 💳 Báo cáo thẩm định công nợ: {res['customer_name']} ({res['customer_code']})\n\n"
                f"- **Hạn mức công nợ tối đa:** **{credit_limit_fmt}**\n"
                f"- **Dư nợ hiện tại chưa thanh toán:** **{current_debt_fmt}**\n"
                + (f"- **Giá trị đơn hàng dự kiến đặt thêm:** **{int(additional_amount):,} đ**\n".replace(",", ".") if additional_amount and additional_amount > 0 else "")
                + f"- **Dư nợ dự kiến sau đơn hàng:** **{projected_debt_fmt}**\n"
                f"- **Hạn mức còn khả dụng:** **{available_fmt}**\n"
                f"- **Tỷ lệ sử dụng hạn mức:** **{rate}%**\n\n"
                f"{status_note}"
            )

            return json.dumps({
                "success": True,
                "customer_code": res["customer_code"],
                "customer_name": res["customer_name"],
                "credit_limit": float(res["credit_limit"]),
                "current_debt": float(res["current_debt"]),
                "projected_debt": float(res["projected_debt"]),
                "available_credit": float(res["available_credit"]),
                "credit_utilization_rate": res["credit_utilization_rate"],
                "is_exceeded": is_exceeded,
                "message": summary_msg,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "message": f"Không thể tra cứu công nợ khách hàng: {str(e)}",
            }, ensure_ascii=False)


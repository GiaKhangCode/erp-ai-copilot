import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_phase1_inventory_adjustment_and_scoping():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as Sales Rep (has no inventory:write)
        sales_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        assert sales_login.status_code == 200
        sales_token = sales_login.json()["access_token"]

        # Sales Rep tries to adjust inventory -> 403
        adjust_res_forbidden = await client.post(
            "/api/v1/inventory/adjust",
            headers={"Authorization": f"Bearer {sales_token}"},
            json={
                "sku": "SKU-001",
                "warehouse_code": "WH-HN",
                "delta_quantity": 10,
                "reason": "Test adjust unauthorized",
            },
        )
        assert adjust_res_forbidden.status_code == 403

        # 2. Login as Warehouse Keeper (has inventory:write)
        wh_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "warehouse@erpcopilot.vn", "password": "warehouse123"},
        )
        assert wh_login.status_code == 200
        wh_token = wh_login.json()["access_token"]

        # Warehouse Keeper adjusts inventory +5 -> 201 Created
        adjust_res = await client.post(
            "/api/v1/inventory/adjust",
            headers={"Authorization": f"Bearer {wh_token}"},
            json={
                "sku": "SKU-001",
                "warehouse_code": "WH-HN",
                "delta_quantity": 5,
                "reason": "Kiểm kê định kỳ thêm 5 chiếc",
            },
        )
        assert adjust_res.status_code == 201
        data = adjust_res.json()
        assert data["sku"] == "SKU-001"
        assert data["delta_quantity"] == 5
        assert data["quantity_after"] == data["quantity_before"] + 5

        # 3. Warehouse Keeper fetches adjustment history -> 200
        hist_res = await client.get(
            "/api/v1/inventory/adjustments?sku=SKU-001",
            headers={"Authorization": f"Bearer {wh_token}"},
        )
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) > 0
        assert history[0]["sku"] == "SKU-001"


@pytest.mark.asyncio
async def test_phase1_order_delivery_fulfillment():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as Manager to get a confirmed order (or create & approve one)
        mgr_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "manager@erpcopilot.vn", "password": "manager123"},
        )
        assert mgr_login.status_code == 200
        mgr_token = mgr_login.json()["access_token"]

        # Find or list orders
        orders_res = await client.get(
            "/api/v1/sales-orders?status=confirmed",
            headers={"Authorization": f"Bearer {mgr_token}"},
        )
        assert orders_res.status_code == 200
        confirmed_orders = orders_res.json()

        # If there is a confirmed order, test delivering it
        if confirmed_orders:
            order_to_deliver = confirmed_orders[0]
            order_id = order_to_deliver["id"]

            # Sales rep tries to deliver -> 403 Forbidden
            sales_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "sales@erpcopilot.vn", "password": "sales123"},
            )
            sales_token = sales_login.json()["access_token"]
            deliv_forbidden = await client.post(
                f"/api/v1/orders/{order_id}/deliver",
                headers={"Authorization": f"Bearer {sales_token}"},
            )
            assert deliv_forbidden.status_code == 403

            # Warehouse keeper delivers -> 200 OK
            wh_login = await client.post(
                "/api/v1/auth/login",
                json={"email": "warehouse@erpcopilot.vn", "password": "warehouse123"},
            )
            wh_token = wh_login.json()["access_token"]

            deliv_res = await client.post(
                f"/api/v1/orders/{order_id}/deliver",
                headers={"Authorization": f"Bearer {wh_token}"},
            )
            assert deliv_res.status_code == 200
            delivered_order = deliv_res.json()
            assert delivered_order["status"] == "delivered"

            # Delivering already delivered order -> 422 ValidationException
            deliv_again = await client.post(
                f"/api/v1/orders/{order_id}/deliver",
                headers={"Authorization": f"Bearer {wh_token}"},
            )
            assert deliv_again.status_code in (400, 422)

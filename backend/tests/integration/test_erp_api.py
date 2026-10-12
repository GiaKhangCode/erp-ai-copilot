import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_get_customers_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/customers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(c["code"] == "CUS-0001" for c in data)


@pytest.mark.asyncio
async def test_get_customer_detail_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/customers/CUS-0001")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "CUS-0001"
        assert "Á Châu" in data["name"]


@pytest.mark.asyncio
async def test_get_customer_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/customers/CUS-NONEXISTENT")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "CUSTOMER_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_products_list_and_detail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/products/SKU-001")
        assert response.status_code == 200
        data = response.json()
        assert data["sku"] == "SKU-001"
        assert float(data["unit_price"]) == 28500000.0


@pytest.mark.asyncio
async def test_get_inventory_by_sku():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/inventory?sku=SKU-001")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        first = data[0]
        assert first["product_sku"] == "SKU-001"
        # available = on_hand - reserved
        assert first["quantity_available"] == first["quantity_on_hand"] - first["quantity_reserved"]


@pytest.mark.asyncio
async def test_create_sales_order_draft_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "customer_code": "CUS-0001",
            "items": [
                {"sku": "SKU-001", "quantity": 2},
                {"sku": "SKU-003", "quantity": 3},
            ],
        }
        response = await client.post("/api/v1/sales-orders/drafts", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "draft"
        assert data["order_number"].startswith("SO-")
        assert len(data["items"]) == 2

        # Invariant check: Server calculates total: 2 * 28500000 + 3 * 2450000 = 57000000 + 7350000 = 64350000
        expected_total = 2 * 28500000.0 + 3 * 2450000.0
        assert float(data["total_amount"]) == expected_total


@pytest.mark.asyncio
async def test_create_sales_order_draft_unknown_sku():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "customer_code": "CUS-0001",
            "items": [{"sku": "SKU-INVALID-999", "quantity": 1}],
        }
        response = await client.post("/api/v1/sales-orders/drafts", json=payload)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_sales_order_draft_zero_quantity():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "customer_code": "CUS-0001",
            "items": [{"sku": "SKU-001", "quantity": 0}],
        }
        response = await client.post("/api/v1/sales-orders/drafts", json=payload)
        # Pydantic validation failure (Field(gt=0))
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_auth_login_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": "sales@erpcopilot.vn", "password": "sales123"}
        response = await client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "sales@erpcopilot.vn"


@pytest.mark.asyncio
async def test_auth_login_invalid_password():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"email": "sales@erpcopilot.vn", "password": "wrongpassword"}
        response = await client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_auth_me_authenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@erpcopilot.vn", "password": "admin123"},
        )
        token = login_res.json()["access_token"]

        # Call /me with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["email"] == "admin@erpcopilot.vn"
        assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_reporting_revenue_summary():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/reporting/revenue")
        assert response.status_code == 200
        data = response.json()
        assert data["metric_id"] == "revenue_summary"
        assert data["total_orders"] >= 2
        assert float(data["total_revenue"]) >= 82800000.0  # 57m + 25.8m
        assert len(data["breakdown"]) >= 1


@pytest.mark.asyncio
async def test_create_order_draft_idempotency():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "customer_code": "CUS-0002",
            "items": [{"sku": "SKU-002", "quantity": 1}],
        }
        idemp_headers = {"Idempotency-Key": "test-key-unique-12345"}

        # First request
        res1 = await client.post(
            "/api/v1/sales-orders/drafts", json=payload, headers=idemp_headers
        )
        assert res1.status_code == 201
        order1 = res1.json()

        # Duplicate retry request with same Idempotency-Key
        res2 = await client.post(
            "/api/v1/sales-orders/drafts", json=payload, headers=idemp_headers
        )
        assert res2.status_code in [200, 201]
        order2 = res2.json()

        # Must return the SAME order, preventing duplicates
        assert order1["id"] == order2["id"]
        assert order1["order_number"] == order2["order_number"]

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

transport = ASGITransport(app=app)


@pytest.mark.asyncio
async def test_rbac_login_all_five_roles():
    """
    Kiểm tra đăng nhập thành công cả 5 vai trò chuẩn và đối chiếu danh sách quyền (permissions).
    1. admin: có superuser hoặc full quyền
    2. director: xem báo cáo doanh thu, duyệt đơn, tài liệu mật
    3. sales_manager: xem báo cáo, duyệt đơn, không xem tài liệu mật
    4. sales_rep: lập đơn, tra cứu sản phẩm/khách hàng, KHÔNG có reports:revenue_view
    5. warehouse_keeper: tra cứu tồn kho, KHÔNG có orders:approve, KHÔNG có reports
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin
        res_admin = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@erpcopilot.vn", "password": "admin123"},
        )
        assert res_admin.status_code == 200
        data_admin = res_admin.json()
        assert "access_token" in data_admin
        assert "refresh_token" in data_admin
        assert "admin" in data_admin["user"]["roles"]
        assert "*" in data_admin["user"]["permissions"]

        # 2. Director
        res_dir = await client.post(
            "/api/v1/auth/login",
            json={"email": "director@erpcopilot.vn", "password": "director123"},
        )
        assert res_dir.status_code == 200
        data_dir = res_dir.json()
        assert "director" in data_dir["user"]["roles"]
        assert "reports:revenue_view" in data_dir["user"]["permissions"]
        assert "documents:read_confidential" in data_dir["user"]["permissions"]
        assert "orders:approve" in data_dir["user"]["permissions"]

        # 3. Sales Manager
        res_mgr = await client.post(
            "/api/v1/auth/login",
            json={"email": "manager@erpcopilot.vn", "password": "manager123"},
        )
        assert res_mgr.status_code == 200
        data_mgr = res_mgr.json()
        assert "sales_manager" in data_mgr["user"]["roles"]
        assert "reports:revenue_view" in data_mgr["user"]["permissions"]
        assert "orders:approve" in data_mgr["user"]["permissions"]
        assert "documents:read_confidential" not in data_mgr["user"]["permissions"]

        # 4. Sales Rep
        res_sales = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        assert res_sales.status_code == 200
        data_sales = res_sales.json()
        assert "sales_rep" in data_sales["user"]["roles"]
        assert "orders:create" in data_sales["user"]["permissions"]
        assert "reports:revenue_view" not in data_sales["user"]["permissions"]
        assert "orders:approve" not in data_sales["user"]["permissions"]

        # 5. Warehouse Keeper
        res_wh = await client.post(
            "/api/v1/auth/login",
            json={"email": "warehouse@erpcopilot.vn", "password": "warehouse123"},
        )
        assert res_wh.status_code == 200
        data_wh = res_wh.json()
        assert "warehouse_keeper" in data_wh["user"]["roles"]
        assert "inventory:read" in data_wh["user"]["permissions"]
        assert "orders:approve" not in data_wh["user"]["permissions"]
        assert "reports:revenue_view" not in data_wh["user"]["permissions"]


@pytest.mark.asyncio
async def test_rbac_refresh_token_lifecycle():
    """
    Kiểm tra vòng đời của Refresh Token:
    1. Đăng nhập lấy access_token + refresh_token
    2. Gọi /api/v1/auth/refresh để lấy access_token mới
    3. Đăng xuất /api/v1/auth/logout -> Thu hồi refresh_token
    4. Cố tình refresh lại với token cũ -> Phải bị từ chối 401 SESSION_REVOKED
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        assert res_login.status_code == 200
        data = res_login.json()
        refresh_token = data["refresh_token"]
        old_access_token = data["access_token"]

        # 2. Refresh token
        res_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert res_refresh.status_code == 200
        new_data = res_refresh.json()
        assert "access_token" in new_data
        assert new_data["user"]["email"] == "sales@erpcopilot.vn"

        # 3. Logout
        logout_headers = {"Authorization": f"Bearer {old_access_token}"}
        res_logout = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers=logout_headers,
        )
        assert res_logout.status_code == 200

        # 4. Cố tình refresh lại sau khi đã logout -> Thất bại
        res_reuse = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert res_reuse.status_code == 401
        assert "SESSION_REVOKED" in res_reuse.json()["error"]["code"]


@pytest.mark.asyncio
async def test_rbac_auth_me_profile():
    """
    Kiểm tra endpoint /auth/me trả về đúng thông tin hồ sơ và danh mục quyền.
    """
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "manager@erpcopilot.vn", "password": "manager123"},
        )
        token = res_login.json()["access_token"]

        res_me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_me.status_code == 200
        me_data = res_me.json()
        assert me_data["email"] == "manager@erpcopilot.vn"
        assert me_data["full_name"] == "Lê Văn Quản Lý"
        assert "sales_manager" in me_data["roles"]
        assert "orders:approve" in me_data["permissions"]

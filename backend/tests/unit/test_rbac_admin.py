import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_admin_endpoints_require_permission():
    """Nhân viên không có quyền quản trị (sales_rep) bị chặn 403 Forbidden khi gọi các API /admin/*."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Đăng nhập bằng tài khoản sales_rep
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "sales@erpcopilot.vn", "password": "sales123"},
        )
        assert res_login.status_code == 200
        sales_token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {sales_token}"}

        # 1. Thử xem danh sách người dùng -> 403
        res_users = await client.get("/api/v1/admin/users", headers=headers)
        assert res_users.status_code == 403
        assert res_users.json()["error"]["code"] in ("PERMISSION_DENIED", "FORBIDDEN")

        # 2. Thử tạo người dùng mới -> 403
        res_create = await client.post(
            "/api/v1/admin/users",
            json={
                "email": "hacker@company.com",
                "password": "secretpassword",
                "full_name": "Hacker",
            },
            headers=headers,
        )
        assert res_create.status_code == 403

        # 3. Thử xem danh sách vai trò -> 403
        res_roles = await client.get("/api/v1/admin/roles", headers=headers)
        assert res_roles.status_code == 403

        # 4. Thử xem ma trận quyền hạn -> 403
        res_perms = await client.get("/api/v1/admin/permissions", headers=headers)
        assert res_perms.status_code == 403


@pytest.mark.asyncio
async def test_admin_user_crud_and_status_lifecycle():
    """Kiểm tra toàn bộ vòng đời quản trị nhân viên: tạo mới, gán vai trò, cập nhật, khóa tài khoản, reset password và xóa."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Đăng nhập Admin
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@erpcopilot.vn", "password": "admin123"},
        )
        assert res_login.status_code == 200
        admin_token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Lấy danh sách roles để lấy role_id của sales_rep
        res_roles = await client.get("/api/v1/admin/roles", headers=headers)
        assert res_roles.status_code == 200
        roles_list = res_roles.json()
        sales_rep_role = next(r for r in roles_list if r["code"] == "sales_rep")
        sales_role_id = sales_rep_role["id"]

        # 2. Tạo nhân viên mới
        unique_email = f"staff_{uuid.uuid4().hex[:8]}@company.com"
        create_payload = {
            "email": unique_email,
            "password": "InitialPassword123",
            "full_name": "Nguyễn Văn Test",
            "phone": "0987654321",
            "department": "Phòng Kinh Doanh 2",
            "job_title": "Chuyên viên bán hàng",
            "role_ids": [sales_role_id],
            "is_active": True,
        }
        res_create = await client.post("/api/v1/admin/users", json=create_payload, headers=headers)
        assert res_create.status_code == 201
        created_user = res_create.json()
        user_id = created_user["id"]
        assert created_user["email"] == unique_email
        assert created_user["full_name"] == "Nguyễn Văn Test"
        assert len(created_user["roles"]) == 1
        assert created_user["roles"][0]["code"] == "sales_rep"
        assert "orders:create" in created_user["permissions"]

        # 3. Lọc danh sách nhân viên theo từ khóa và phòng ban
        res_list = await client.get(
            f"/api/v1/admin/users?search=Nguyễn Văn Test&department=Phòng Kinh Doanh 2",
            headers=headers,
        )
        assert res_list.status_code == 200
        list_data = res_list.json()
        assert list_data["total"] >= 1
        found_in_list = any(u["id"] == user_id for u in list_data["items"])
        assert found_in_list is True

        # 4. Cập nhật thông tin profile
        update_payload = {
            "full_name": "Nguyễn Văn Test (Senior)",
            "phone": "0911223344",
            "job_title": "Chuyên viên tư vấn cấp cao",
        }
        res_update = await client.put(f"/api/v1/admin/users/{user_id}", json=update_payload, headers=headers)
        assert res_update.status_code == 200
        updated_user = res_update.json()
        assert updated_user["full_name"] == "Nguyễn Văn Test (Senior)"
        assert updated_user["phone"] == "0911223344"

        # 5. Khóa tài khoản nhân viên (toggle status)
        res_lock = await client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            json={"is_active": False},
            headers=headers,
        )
        assert res_lock.status_code == 200
        assert res_lock.json()["is_active"] is False

        # Thử đăng nhập bằng tài khoản bị khóa -> Bị từ chối 403
        res_login_locked = await client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "InitialPassword123"},
        )
        assert res_login_locked.status_code == 403
        assert "khóa" in res_login_locked.json()["error"]["message"]

        # 6. Mở khóa lại và Đặt lại mật khẩu
        res_unlock = await client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            json={"is_active": True},
            headers=headers,
        )
        assert res_unlock.status_code == 200

        res_reset_pwd = await client.post(
            f"/api/v1/admin/users/{user_id}/reset-password",
            json={"new_password": "NewSecretPassword2026!"},
            headers=headers,
        )
        assert res_reset_pwd.status_code == 200

        # Thử đăng nhập lại bằng mật khẩu mới -> Thành công 200
        res_login_new_pwd = await client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "NewSecretPassword2026!"},
        )
        assert res_login_new_pwd.status_code == 200

        # 7. Xóa người dùng dọn dẹp dữ liệu
        res_delete = await client.delete(f"/api/v1/admin/users/{user_id}", headers=headers)
        assert res_delete.status_code == 200

        # Kiểm tra lại chi tiết -> 404 Not Found
        res_get_deleted = await client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
        assert res_get_deleted.status_code == 404


@pytest.mark.asyncio
async def test_admin_role_and_permission_matrix():
    """Kiểm tra quản trị vai trò tùy biến và cập nhật ma trận phân quyền."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Đăng nhập Admin
        res_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@erpcopilot.vn", "password": "admin123"},
        )
        admin_token = res_login.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Lấy danh mục 21 quyền gom nhóm theo module
        res_perms = await client.get("/api/v1/admin/permissions", headers=headers)
        assert res_perms.status_code == 200
        perm_groups = res_perms.json()
        assert len(perm_groups) >= 5
        # Gom tất cả permissions ID
        all_perm_ids = [p["id"] for g in perm_groups for p in g["permissions"]]
        assert len(all_perm_ids) >= 20

        # 2. Tạo một vai trò tùy biến mới (Custom Role)
        custom_code = f"auditor_{uuid.uuid4().hex[:6]}"
        create_role_payload = {
            "code": custom_code,
            "name": "Kiểm toán viên Nội bộ",
            "description": "Chỉ có quyền đọc toàn bộ hệ thống để phục vụ thanh tra",
            "permission_ids": all_perm_ids[:3],
        }
        res_create_role = await client.post("/api/v1/admin/roles", json=create_role_payload, headers=headers)
        assert res_create_role.status_code == 201
        created_role = res_create_role.json()
        role_id = created_role["id"]
        assert created_role["code"] == custom_code
        assert created_role["is_system"] is False
        assert len(created_role["permissions"]) == 3

        # 3. Cập nhật ma trận quyền hạn cho vai trò tùy biến
        new_perm_set = all_perm_ids[:6]
        res_update_perms = await client.put(
            f"/api/v1/admin/roles/{role_id}/permissions",
            json={"permission_ids": new_perm_set},
            headers=headers,
        )
        assert res_update_perms.status_code == 200
        assert len(res_update_perms.json()["permissions"]) == 6

        # 4. Thử xóa vai trò hệ thống mặc định (ví dụ 'admin') -> BỊ CHẶN 400
        res_roles = await client.get("/api/v1/admin/roles", headers=headers)
        admin_role = next(r for r in res_roles.json() if r["code"] == "admin")
        res_del_system = await client.delete(f"/api/v1/admin/roles/{admin_role['id']}", headers=headers)
        assert res_del_system.status_code == 400
        assert "hệ thống" in res_del_system.json()["detail"]

        # 5. Xóa vai trò tùy biến vừa tạo -> Thành công
        res_del_custom = await client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
        assert res_del_custom.status_code == 200

        # Kiểm tra lại chi tiết vai trò -> 404 Not Found
        res_get_del = await client.get(f"/api/v1/admin/roles/{role_id}", headers=headers)
        assert res_get_del.status_code == 404

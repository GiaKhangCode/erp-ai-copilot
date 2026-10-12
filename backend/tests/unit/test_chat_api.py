import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


async def get_auth_token(client: AsyncClient, email: str, password: str) -> str:
    """Helper đăng nhập lấy Bearer token"""
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_openapi_schema_contains_chat_endpoints():
    """Kiểm tra OpenAPI schema đăng ký đầy đủ các endpoint Chat và Conversations"""
    openapi = app.openapi()
    paths = openapi["paths"]
    assert "/api/v1/chat" in paths
    assert "post" in paths["/api/v1/chat"]
    assert "/api/v1/conversations" in paths
    assert "get" in paths["/api/v1/conversations"]
    assert "/api/v1/conversations/{conversation_id}" in paths
    assert "get" in paths["/api/v1/conversations/{conversation_id}"]
    assert "delete" in paths["/api/v1/conversations/{conversation_id}"]


@pytest.mark.asyncio
async def test_chat_unauthenticated():
    """Kiểm tra chặn truy cập khi chưa xác thực (401 Unauthorized)"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/chat", json={"message": "Xin chào"})
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_chat_empty_message():
    """Kiểm tra từ chối tin nhắn rỗng (422 Unprocessable Entity)"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_auth_token(client, "sales@erpcopilot.vn", "sales123")
        headers = {"Authorization": f"Bearer {token}"}

        res = await client.post("/api/v1/chat", json={"message": ""}, headers=headers)
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_chat_and_conversation_persistence_lifecycle():
    """
    Kiểm thử vòng đời hoàn chỉnh:
    1. Gửi tin nhắn chat mới -> Tự động tạo conversation + lưu message vào DB.
    2. Liệt kê danh sách conversations.
    3. Xem chi tiết lịch sử tin nhắn.
    4. Xóa cuộc hội thoại.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_auth_token(client, "sales@erpcopilot.vn", "sales123")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Gửi tin nhắn đầu tiên
        chat_res = await client.post(
            "/api/v1/chat",
            json={"message": "Xin chào bạn là ai?"},
            headers=headers,
        )
        assert chat_res.status_code == 200
        data = chat_res.json()

        assert "conversation_id" in data
        conv_id = data["conversation_id"]
        assert "run_id" in data
        assert data["status"] == "completed"
        assert len(data["answer"]) > 0

        # 2. Lấy danh sách conversations
        list_res = await client.get("/api/v1/conversations", headers=headers)
        assert list_res.status_code == 200
        conversations = list_res.json()
        assert len(conversations) >= 1

        matched_conv = next((c for c in conversations if c["id"] == conv_id), None)
        assert matched_conv is not None
        assert matched_conv["message_count"] >= 2  # Gồm 1 user msg và 1 assistant msg

        # 3. Lấy chi tiết lịch sử hội thoại
        detail_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert detail_data["id"] == conv_id
        assert len(detail_data["messages"]) >= 2
        assert detail_data["messages"][0]["role"] == "user"
        assert detail_data["messages"][1]["role"] == "assistant"

        # 4. Xóa cuộc hội thoại
        del_res = await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert del_res.status_code == 200

        # 5. Xác nhận không còn tồn tại
        get_after_del = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_chat_multi_turn_continuation():
    """Kiểm thử hội thoại đa vòng (multi-turn) kế thừa ngữ cảnh qua cùng conversation_id"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await get_auth_token(client, "sales@erpcopilot.vn", "sales123")
        headers = {"Authorization": f"Bearer {token}"}

        # Vòng 1: Tạo hội thoại
        res1 = await client.post(
            "/api/v1/chat",
            json={"message": "Xin chào"},
            headers=headers,
        )
        assert res1.status_code == 200
        conv_id = res1.json()["conversation_id"]

        try:
            # Vòng 2: Tiếp tục trên conversation_id đã có
            res2 = await client.post(
                "/api/v1/chat",
                json={
                    "conversation_id": conv_id,
                    "message": "Bạn có thể làm gì?",
                },
                headers=headers,
            )
            assert res2.status_code == 200
            assert res2.json()["conversation_id"] == conv_id

            # Kiểm tra chi tiết DB: có đúng 4 tin nhắn (2 user + 2 assistant)
            detail_res = await client.get(f"/api/v1/conversations/{conv_id}", headers=headers)
            assert detail_res.status_code == 200
            msgs = detail_res.json()["messages"]
            assert len(msgs) == 4
            assert msgs[0]["role"] == "user"
            assert msgs[1]["role"] == "assistant"
            assert msgs[2]["role"] == "user"
            assert msgs[3]["role"] == "assistant"

        finally:
            # Dọn dẹp
            await client.delete(f"/api/v1/conversations/{conv_id}", headers=headers)


@pytest.mark.asyncio
async def test_conversation_isolation_between_users():
    """Kiểm tra ranh giới bảo mật: Người dùng khác không thể xem trộm hội thoại của nhau"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token = await get_auth_token(client, "sales@erpcopilot.vn", "sales123")
        admin_token = await get_auth_token(client, "admin@erpcopilot.vn", "admin123")

        sales_headers = {"Authorization": f"Bearer {sales_token}"}
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Sales rep tạo cuộc hội thoại
        create_res = await client.post(
            "/api/v1/chat",
            json={"message": "Cuộc trò chuyện riêng của Sales"},
            headers=sales_headers,
        )
        assert create_res.status_code == 200
        conv_id = create_res.json()["conversation_id"]

        try:
            # Admin cố gắng truy cập trái phép cuộc trò chuyện của Sales
            unauthorized_res = await client.get(
                f"/api/v1/conversations/{conv_id}",
                headers=admin_headers,
            )
            assert unauthorized_res.status_code == 404
        finally:
            await client.delete(f"/api/v1/conversations/{conv_id}", headers=sales_headers)

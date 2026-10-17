import pytest
from app.ai.prompts.agent_prompts import (
    get_role_aware_chitchat_prompt,
    get_role_aware_super_agent_prompt,
    get_role_display_name,
)


def test_get_role_display_name():
    assert get_role_display_name("warehouse_keeper") == "Thủ kho (Warehouse Keeper)"
    assert get_role_display_name("sales_rep") == "Chuyên viên kinh doanh (Sales Rep)"
    assert get_role_display_name("sales_manager") == "Quản lý kinh doanh (Sales Manager)"
    assert get_role_display_name("director") == "Ban Giám đốc"
    assert get_role_display_name("admin") == "Quản trị viên hệ thống"
    assert get_role_display_name("unknown") == "Thành viên"


def test_warehouse_keeper_role_aware_intro_prompt():
    prompt = get_role_aware_chitchat_prompt(
        user_role="warehouse_keeper",
        user_name="Phạm Văn Thủ Kho",
        user_permissions=["inventory:read", "inventory:write"],
    )
    # Xác thực xưng hô và vai trò
    assert "Phạm Văn Thủ Kho" in prompt
    assert "Thủ kho" in prompt

    # Xác thực các năng lực chuyên biệt cho Thủ kho
    assert "Kiểm tra tồn kho thời gian thực" in prompt
    assert "Xác nhận đóng gói & Xuất kho" in prompt
    assert "Kiểm kê & Điều chỉnh kho" in prompt

    # Xác thực lưu ý giới hạn phân quyền bảo mật
    assert "không cho phép tạo đơn bán hàng hoặc xem báo cáo doanh thu" in prompt


def test_sales_rep_role_aware_intro_prompt():
    prompt = get_role_aware_chitchat_prompt(
        user_role="sales_rep",
        user_name="Nguyễn Văn Bán Hàng",
        user_permissions=["orders:read", "orders:create"],
    )
    assert "Nguyễn Văn Bán Hàng" in prompt
    assert "Chuyên viên kinh doanh" in prompt

    # Khả năng cốt lõi cho Sales
    assert "Khởi tạo đơn hàng nháp" in prompt
    assert "Xuất file PDF Báo giá kinh doanh" in prompt
    assert "Thẩm định hạn mức công nợ" in prompt
    assert "Tra cứu tồn kho & đơn giá báo khách" in prompt


def test_director_role_aware_intro_prompt():
    prompt = get_role_aware_chitchat_prompt(
        user_role="director",
        user_name="Trần Văn Giám Đốc",
        user_permissions=["*"],
    )
    assert "Trần Văn Giám Đốc" in prompt
    assert "Ban Giám đốc" in prompt

    # Khả năng cốt lõi cho Ban Giám đốc
    assert "Lợi nhuận gộp & Biên lợi nhuận" in prompt
    assert "Báo cáo Tuổi nợ & Quản trị rủi ro tín dụng" in prompt
    assert "Sales Leaderboard" in prompt


def test_super_agent_prompt_includes_user_context():
    prompt = get_role_aware_super_agent_prompt(
        user_role="sales_rep",
        user_name="Nguyễn Văn Bán Hàng",
        user_permissions=["orders:create", "customers:read"],
    )
    assert "Nguyễn Văn Bán Hàng" in prompt
    assert "Chuyên viên kinh doanh" in prompt
    assert "orders:create" in prompt

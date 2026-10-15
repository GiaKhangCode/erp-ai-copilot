import uuid
from typing import Optional
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException
from app.db.session import get_db
from app.auth.security import decode_access_token
from app.erp.models import User

from sqlalchemy.orm import selectinload
from app.erp.models import User, Role, Permission, RolePermission, UserRole

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Yêu cầu xác thực tài khoản (Token bearer)",
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Token không hợp lệ hoặc đã hết hạn",
        )

    user_id_str = payload["sub"]
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Token định dạng sai",
        )

    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Người dùng không tồn tại",
        )

    if not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Tài khoản đã bị vô hiệu hóa",
        )

    return user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except AppException:
        return None


async def get_current_user_permissions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> set[str]:
    """
    Truy xuất tập hợp toàn bộ mã quyền (permission code) của người dùng hiện tại.
    Superuser tự động sở hữu toàn bộ quyền ("*").
    """
    if current_user.is_superuser or current_user.role == "admin":
        return {"*"}

    # Truy vấn permissions thông qua bảng liên kết user_roles -> roles -> role_permissions -> permissions
    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    permissions = set(result.scalars().all())

    # Fallback cho trường hợp người dùng cũ chỉ có chuỗi user.role mà chưa gán user_roles
    if not permissions and current_user.role:
        role_stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.code == current_user.role)
        )
        fallback_res = await db.execute(role_stmt)
        permissions = set(fallback_res.scalars().all())

    return permissions


def require_permission(permission_code: str):
    """Dependency kiểm tra quyền hành động nguyên tử (Dynamic Permission Checking)."""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
        user_permissions: set[str] = Depends(get_current_user_permissions),
    ) -> User:
        if "*" in user_permissions or permission_code in user_permissions:
            return current_user

        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message=f"Bạn không có quyền thực hiện hành động này. Yêu cầu quyền: '{permission_code}'.",
        )

    return permission_checker


def require_role(allowed_roles: list[str]):
    """Dependency kiểm tra vai trò (RBAC) - Hỗ trợ cả Role gán động và Role truyền thống."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_superuser:
            return current_user

        user_role_codes = {r.code for r in current_user.roles} if current_user.roles else set()
        user_role_codes.add(current_user.role)

        if not any(role in allowed_roles for role in user_role_codes):
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message=f"Chỉ người dùng có vai trò {allowed_roles} mới được phép thực hiện hành động này.",
            )
        return current_user

    return role_checker


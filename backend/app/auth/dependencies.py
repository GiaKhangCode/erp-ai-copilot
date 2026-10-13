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

    stmt = select(User).where(User.id == user_id)
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


def require_role(allowed_roles: list[str]):
    """Dependency kiểm tra quyền hạn (RBAC) của người dùng hiện tại."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message=f"Chỉ người dùng có vai trò {allowed_roles} mới được phép thực hiện hành động này.",
            )
        return current_user

    return role_checker

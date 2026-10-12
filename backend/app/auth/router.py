from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppException
from app.db.session import get_db
from app.auth.security import verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.erp.models import User
from app.erp.schemas import LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Đăng nhập hệ thống demo và lấy Access Token (JWT Bearer).
    """
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            message="Email hoặc mật khẩu không chính xác",
        )

    if not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            message="Tài khoản đang bị khóa",
        )

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Lấy thông tin người dùng hiện tại đang đăng nhập."""
    return UserResponse.model_validate(current_user)

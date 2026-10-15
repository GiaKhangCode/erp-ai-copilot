import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Request
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppException
from app.db.session import get_db
from app.auth.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    hash_token,
    decode_access_token,
)
from app.auth.dependencies import get_current_user, get_current_user_permissions
from app.erp.models import User, UserSession, Permission, RolePermission, Role, UserRole
from app.erp.schemas import LoginRequest, RefreshTokenRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _resolve_user_permissions(user: User, db: AsyncSession) -> set[str]:
    """Helper truy xuất toàn bộ permissions của người dùng."""
    if user.is_superuser or user.role == "admin":
        return {"*"}

    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
    )
    res = await db.execute(stmt)
    perms = set(res.scalars().all())

    if not perms and user.role:
        fallback_stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .where(Role.code == user.role)
        )
        fallback_res = await db.execute(fallback_stmt)
        perms = set(fallback_res.scalars().all())

    return perms


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Đăng nhập hệ thống, cấp Access Token và Refresh Token cho 5 vai trò.
    """
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.email == payload.email)
    )
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

    # 1. Trích xuất danh sách vai trò
    user_roles = [r.code for r in user.roles] if user.roles else []
    if not user_roles and user.role:
        user_roles = [user.role]

    # 2. Trích xuất quyền hạn (Permissions)
    permissions = sorted(list(await _resolve_user_permissions(user, db)))

    # 3. Tạo Access Token (JWT ngắn hạn)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "roles": user_roles,
            "is_superuser": user.is_superuser,
        }
    )

    # 4. Tạo Refresh Token & Lưu phiên làm việc UserSession
    raw_refresh_token, refresh_hash, refresh_expires_at = create_refresh_token(
        data={"sub": str(user.id), "email": user.email}
    )

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session_record = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        user_agent=user_agent,
        ip_address=client_ip,
        expires_at=refresh_expires_at,
        is_revoked=False,
    )
    db.add(session_record)

    # Cập nhật thời điểm đăng nhập gần nhất
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        phone=user.phone,
        department=user.department,
        job_title=user.job_title,
        is_superuser=user.is_superuser,
        roles=user_roles,
        permissions=permissions,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Sử dụng Refresh Token còn hiệu lực để cấp phát Access Token mới.
    """
    token_payload = decode_access_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh" or "sub" not in token_payload:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_REFRESH_TOKEN",
            message="Refresh token không hợp lệ hoặc đã hết hạn",
        )

    token_hash = hash_token(payload.refresh_token)
    session_stmt = select(UserSession).where(
        and_(
            UserSession.refresh_token_hash == token_hash,
            UserSession.is_revoked == False,
        )
    )
    session_res = await db.execute(session_stmt)
    session_record = session_res.scalar_one_or_none()

    if not session_record:
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="SESSION_REVOKED",
            message="Phiên làm việc đã bị thu hồi hoặc không tồn tại",
        )

    if session_record.expires_at < datetime.now(timezone.utc):
        raise AppException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="SESSION_EXPIRED",
            message="Phiên làm việc đã hết hạn. Vui lòng đăng nhập lại",
        )

    # Lấy thông tin user
    user_stmt = select(User).options(selectinload(User.roles)).where(User.id == session_record.user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user or not user.is_active:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCOUNT_LOCKED",
            message="Tài khoản đã bị khóa hoặc không tồn tại",
        )

    user_roles = [r.code for r in user.roles] if user.roles else [user.role]
    permissions = sorted(list(await _resolve_user_permissions(user, db)))

    new_access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "roles": user_roles,
            "is_superuser": user.is_superuser,
        }
    )

    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        phone=user.phone,
        department=user.department,
        job_title=user.job_title,
        is_superuser=user.is_superuser,
        roles=user_roles,
        permissions=permissions,
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=payload.refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_resp,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    payload: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Đăng xuất và thu hồi Refresh Token hiện tại.
    """
    token_hash = hash_token(payload.refresh_token)
    stmt = select(UserSession).where(
        and_(
            UserSession.refresh_token_hash == token_hash,
            UserSession.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    session_record = res.scalar_one_or_none()
    if session_record:
        session_record.is_revoked = True
        await db.commit()

    return {"message": "Đăng xuất thành công, phiên làm việc đã được thu hồi"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    user_permissions: set[str] = Depends(get_current_user_permissions),
):
    """Lấy thông tin người dùng hiện tại đang đăng nhập kèm toàn bộ vai trò và quyền hạn."""
    user_roles = [r.code for r in current_user.roles] if current_user.roles else [current_user.role]

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        phone=current_user.phone,
        department=current_user.department,
        job_title=current_user.job_title,
        is_superuser=current_user.is_superuser,
        roles=user_roles,
        permissions=sorted(list(user_permissions)),
    )


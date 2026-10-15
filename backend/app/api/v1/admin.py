import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.admin_schemas import (
    PermissionGroupResponse,
    PermissionResponse,
    RoleBriefResponse,
    RoleCreateRequest,
    RoleDetailResponse,
    RolePermissionsUpdate,
    RoleUpdateRequest,
    UserAdminCreate,
    UserAdminDetailResponse,
    UserAdminListResponse,
    UserAdminUpdate,
    UserResetPasswordRequest,
    UserStatusUpdate,
)
from app.auth.dependencies import get_current_user, require_permission
from app.auth.security import get_password_hash
from app.db.session import get_db
from app.erp.models import Permission, Role, RolePermission, User, UserRole, UserSession

router = APIRouter(prefix="/admin", tags=["Admin User & Role Management"])

MODULE_DISPLAY_NAMES = {
    "orders": "Đơn hàng & Bán hàng",
    "inventory": "Kho vận & Tồn kho",
    "customers": "Khách hàng & Đối tác",
    "reports": "Báo cáo & Tài chính",
    "documents": "Tài liệu & Tri thức RAG",
    "users": "Quản trị Người dùng",
    "roles": "Quản trị Vai trò & Phân quyền",
}


async def _resolve_user_permissions(session: AsyncSession, user: User) -> List[str]:
    """Lấy danh sách mã quyền tổng hợp của một người dùng từ tất cả các vai trò."""
    if user.is_superuser:
        all_perms_res = await session.execute(select(Permission.code))
        return list(all_perms_res.scalars().all())

    stmt = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id)
        .distinct()
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


# =========================================================================
# 1. User Management Endpoints
# =========================================================================

@router.get(
    "/users",
    response_model=UserAdminListResponse,
    summary="Danh sách người dùng có phân trang, tìm kiếm và lọc",
)
async def list_users(
    page: int = Query(1, ge=1, description="Số trang (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số bản ghi trên mỗi trang"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo họ tên, email, SĐT, phòng ban"),
    role: Optional[str] = Query(None, description="Lọc theo mã vai trò (vd: admin, sales_rep)"),
    department: Optional[str] = Query(None, description="Lọc theo phòng ban"),
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái hoạt động"),
    current_user: User = Depends(require_permission("users:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách người dùng trong hệ thống kèm vai trò và quyền hạn."""
    base_query = select(User).distinct()

    # Điều kiện tìm kiếm
    if search:
        search_term = f"%{search.strip()}%"
        base_query = base_query.where(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
                User.phone.ilike(search_term),
                User.department.ilike(search_term),
                User.job_title.ilike(search_term),
            )
        )

    if department:
        base_query = base_query.where(User.department == department)

    if is_active is not None:
        base_query = base_query.where(User.is_active == is_active)

    if role:
        base_query = base_query.join(UserRole, UserRole.user_id == User.id).join(
            Role, Role.id == UserRole.role_id
        ).where(Role.code == role)

    # Đếm tổng số bản ghi
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one()

    # Phân trang & Nạp quan hệ
    offset = (page - 1) * page_size
    stmt = (
        base_query.options(selectinload(User.roles))
        .order_by(desc(User.created_at))
        .offset(offset)
        .limit(page_size)
    )
    users_res = await db.execute(stmt)
    users = users_res.scalars().all()

    # Định dạng kết quả kèm quyền
    items = []
    for u in users:
        perms = await _resolve_user_permissions(db, u)
        brief_roles = [
            RoleBriefResponse(
                id=r.id,
                code=r.code,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                created_at=r.created_at,
            )
            for r in u.roles
        ]
        items.append(
            UserAdminDetailResponse(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                phone=u.phone,
                department=u.department,
                job_title=u.job_title,
                role=u.role,
                is_active=u.is_active,
                is_superuser=u.is_superuser,
                last_login_at=u.last_login_at,
                created_at=u.created_at,
                updated_at=u.updated_at,
                roles=brief_roles,
                permissions=perms,
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return UserAdminListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/users",
    response_model=UserAdminDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo tài khoản nhân viên mới và gán vai trò ban đầu",
)
async def create_user(
    payload: UserAdminCreate,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Tạo mới một tài khoản người dùng và thiết lập vai trò."""
    # 1. Kiểm tra email duy nhất
    email_clean = payload.email.lower().strip()
    existing_user = await db.execute(select(User).where(User.email == email_clean))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{email_clean}' đã được sử dụng trong hệ thống.",
        )

    # 2. Kiểm tra danh sách roles nếu có
    selected_roles = []
    if payload.role_ids:
        roles_stmt = select(Role).where(Role.id.in_(payload.role_ids))
        roles_res = await db.execute(roles_stmt)
        selected_roles = list(roles_res.scalars().all())
        if len(selected_roles) != len(payload.role_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Một hoặc nhiều vai trò được chọn không tồn tại.",
            )

    primary_role_code = selected_roles[0].code if selected_roles else "sales_rep"

    # 3. Tạo User record
    new_user = User(
        id=uuid.uuid4(),
        email=email_clean,
        password_hash=get_password_hash(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        department=payload.department.strip() if payload.department else None,
        job_title=payload.job_title.strip() if payload.job_title else None,
        role=primary_role_code,
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
    )
    db.add(new_user)
    await db.flush()

    # 4. Gán UserRole
    for role_item in selected_roles:
        user_role_link = UserRole(
            user_id=new_user.id,
            role_id=role_item.id,
            assigned_by=current_user.id,
        )
        db.add(user_role_link)

    await db.commit()

    # Nạp lại dữ liệu người dùng
    refetched = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == new_user.id)
    )
    user_record = refetched.scalar_one()
    perms = await _resolve_user_permissions(db, user_record)

    return UserAdminDetailResponse(
        id=user_record.id,
        email=user_record.email,
        full_name=user_record.full_name,
        phone=user_record.phone,
        department=user_record.department,
        job_title=user_record.job_title,
        role=user_record.role,
        is_active=user_record.is_active,
        is_superuser=user_record.is_superuser,
        last_login_at=user_record.last_login_at,
        created_at=user_record.created_at,
        updated_at=user_record.updated_at,
        roles=[
            RoleBriefResponse(
                id=r.id,
                code=r.code,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                created_at=r.created_at,
            )
            for r in user_record.roles
        ],
        permissions=perms,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserAdminDetailResponse,
    summary="Xem thông tin chi tiết một người dùng",
)
async def get_user_detail(
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("users:read")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy chi tiết hồ sơ người dùng kèm danh sách vai trò và quyền hạn."""
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    res = await db.execute(stmt)
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID '{user_id}'.",
        )

    perms = await _resolve_user_permissions(db, u)
    return UserAdminDetailResponse(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        phone=u.phone,
        department=u.department,
        job_title=u.job_title,
        role=u.role,
        is_active=u.is_active,
        is_superuser=u.is_superuser,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
        updated_at=u.updated_at,
        roles=[
            RoleBriefResponse(
                id=r.id,
                code=r.code,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                created_at=r.created_at,
            )
            for r in u.roles
        ],
        permissions=perms,
    )


@router.put(
    "/users/{user_id}",
    response_model=UserAdminDetailResponse,
    summary="Cập nhật thông tin và vai trò của người dùng",
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật thông tin profile và danh sách vai trò."""
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    res = await db.execute(stmt)
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID '{user_id}'.",
        )

    if payload.full_name is not None:
        u.full_name = payload.full_name.strip()
    if payload.phone is not None:
        u.phone = payload.phone.strip() if payload.phone else None
    if payload.department is not None:
        u.department = payload.department.strip() if payload.department else None
    if payload.job_title is not None:
        u.job_title = payload.job_title.strip() if payload.job_title else None

    # Cập nhật trạng thái và thu hồi session nếu khóa
    if payload.is_active is not None:
        if current_user.id == u.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bạn không thể tự khóa tài khoản của chính mình.",
            )
        u.is_active = payload.is_active
        if not payload.is_active:
            await db.execute(
                update(UserSession)
                .where(UserSession.user_id == u.id)
                .values(is_revoked=True)
            )

    # Cập nhật vai trò nếu truyền vào
    if payload.role_ids is not None:
        roles_stmt = select(Role).where(Role.id.in_(payload.role_ids))
        roles_res = await db.execute(roles_stmt)
        selected_roles = list(roles_res.scalars().all())

        if len(selected_roles) != len(payload.role_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Một hoặc nhiều vai trò được chọn không tồn tại.",
            )

        # Xóa các liên kết vai trò cũ
        await db.execute(delete(UserRole).where(UserRole.user_id == u.id))

        # Thêm mới
        for r in selected_roles:
            db.add(
                UserRole(
                    user_id=u.id,
                    role_id=r.id,
                    assigned_by=current_user.id,
                )
            )

        if selected_roles:
            u.role = selected_roles[0].code

    u.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # Nạp lại
    refetched = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id == u.id)
    )
    user_record = refetched.scalar_one()
    perms = await _resolve_user_permissions(db, user_record)

    return UserAdminDetailResponse(
        id=user_record.id,
        email=user_record.email,
        full_name=user_record.full_name,
        phone=user_record.phone,
        department=user_record.department,
        job_title=user_record.job_title,
        role=user_record.role,
        is_active=user_record.is_active,
        is_superuser=user_record.is_superuser,
        last_login_at=user_record.last_login_at,
        created_at=user_record.created_at,
        updated_at=user_record.updated_at,
        roles=[
            RoleBriefResponse(
                id=r.id,
                code=r.code,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                created_at=r.created_at,
            )
            for r in user_record.roles
        ],
        permissions=perms,
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=UserAdminDetailResponse,
    summary="Khóa hoặc mở khóa tài khoản người dùng",
)
async def toggle_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Bật/tắt trạng thái hoạt động của người dùng. Nếu khóa tài khoản, lập tức hủy tất cả các phiên đăng nhập."""
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    res = await db.execute(stmt)
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID '{user_id}'.",
        )

    if current_user.id == u.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự khóa tài khoản của chính mình.",
        )

    if u.is_superuser and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể khóa tài khoản Quản trị cấp cao (Superuser).",
        )

    u.is_active = payload.is_active
    u.updated_at = datetime.now(timezone.utc)

    # Thu hồi toàn bộ session đang active nếu khóa
    if not payload.is_active:
        await db.execute(
            update(UserSession)
            .where(UserSession.user_id == u.id)
            .values(is_revoked=True)
        )

    await db.commit()
    perms = await _resolve_user_permissions(db, u)

    return UserAdminDetailResponse(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        phone=u.phone,
        department=u.department,
        job_title=u.job_title,
        role=u.role,
        is_active=u.is_active,
        is_superuser=u.is_superuser,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
        updated_at=u.updated_at,
        roles=[
            RoleBriefResponse(
                id=r.id,
                code=r.code,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                created_at=r.created_at,
            )
            for r in u.roles
        ],
        permissions=perms,
    )


@router.post(
    "/users/{user_id}/reset-password",
    summary="Đặt lại mật khẩu cho người dùng",
)
async def reset_user_password(
    user_id: uuid.UUID,
    payload: UserResetPasswordRequest,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Đặt lại mật khẩu mới cho người dùng và thu hồi các phiên làm việc cũ."""
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID '{user_id}'.",
        )

    u.password_hash = get_password_hash(payload.new_password)
    u.updated_at = datetime.now(timezone.utc)

    # Đăng xuất mọi phiên cũ để bắt buộc đăng nhập bằng mật khẩu mới
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == u.id)
        .values(is_revoked=True)
    )

    await db.commit()
    return {"message": f"Đã đặt lại mật khẩu thành công cho tài khoản '{u.email}'."}


@router.delete(
    "/users/{user_id}",
    summary="Xóa tài khoản người dùng",
)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Xóa hoàn toàn tài khoản người dùng khỏi hệ thống."""
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    u = res.scalar_one_or_none()
    if not u:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng với ID '{user_id}'.",
        )

    if current_user.id == u.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bạn không thể tự xóa tài khoản của chính mình.",
        )

    if u.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể xóa tài khoản Quản trị cấp cao (Superuser).",
        )

    await db.delete(u)
    await db.commit()
    return {"message": f"Đã xóa tài khoản '{u.email}' thành công."}


# =========================================================================
# 2. Role & Permission Management Endpoints
# =========================================================================

@router.get(
    "/roles",
    response_model=List[RoleDetailResponse],
    summary="Danh sách vai trò và số lượng người dùng thuộc vai trò",
)
async def list_roles(
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh sách tất cả các vai trò, kèm số lượng user và danh sách quyền hạn."""
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .order_by(Role.created_at)
    )
    roles_res = await db.execute(stmt)
    roles = roles_res.scalars().all()

    # Đếm số lượng users cho mỗi role
    user_counts_stmt = (
        select(UserRole.role_id, func.count(UserRole.user_id))
        .group_by(UserRole.role_id)
    )
    user_counts_res = await db.execute(user_counts_stmt)
    counts_map = dict(user_counts_res.all())

    items = []
    for r in roles:
        perms = [
            PermissionResponse(
                id=p.id,
                code=p.code,
                module=p.module,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
            )
            for p in r.permissions
        ]
        items.append(
            RoleDetailResponse(
                id=r.id,
                code=r.code,
                name=r.name,
                description=r.description,
                is_system=r.is_system,
                user_count=counts_map.get(r.id, 0),
                permissions=perms,
                created_at=r.created_at,
            )
        )

    return items


@router.post(
    "/roles",
    response_model=RoleDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo vai trò tùy biến mới (Custom Role)",
)
async def create_role(
    payload: RoleCreateRequest,
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Tạo mới một vai trò nghiệp vụ tùy biến."""
    role_code = payload.code.lower().strip()
    existing_role = await db.execute(select(Role).where(Role.code == role_code))
    if existing_role.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mã vai trò '{role_code}' đã tồn tại.",
        )

    new_role = Role(
        id=uuid.uuid4(),
        code=role_code,
        name=payload.name.strip(),
        description=payload.description.strip() if payload.description else None,
        is_system=False,
    )
    db.add(new_role)
    await db.flush()

    # Gán quyền ban đầu
    if payload.permission_ids:
        for p_id in payload.permission_ids:
            db.add(
                RolePermission(
                    role_id=new_role.id,
                    permission_id=p_id,
                )
            )

    await db.commit()

    # Nạp lại vai trò kèm quyền
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == new_role.id)
    )
    res = await db.execute(stmt)
    role_record = res.scalar_one()

    return RoleDetailResponse(
        id=role_record.id,
        code=role_record.code,
        name=role_record.name,
        description=role_record.description,
        is_system=role_record.is_system,
        user_count=0,
        permissions=[
            PermissionResponse(
                id=p.id,
                code=p.code,
                module=p.module,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
            )
            for p in role_record.permissions
        ],
        created_at=role_record.created_at,
    )


@router.get(
    "/roles/{role_id}",
    response_model=RoleDetailResponse,
    summary="Xem chi tiết vai trò và danh sách quyền hạn",
)
async def get_role_detail(
    role_id: uuid.UUID,
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Tra cứu chi tiết một vai trò theo ID."""
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vai trò với ID '{role_id}'.",
        )

    # Đếm user count
    uc_stmt = select(func.count(UserRole.user_id)).where(UserRole.role_id == role_id)
    uc_res = await db.execute(uc_stmt)
    user_count = uc_res.scalar_one()

    return RoleDetailResponse(
        id=r.id,
        code=r.code,
        name=r.name,
        description=r.description,
        is_system=r.is_system,
        user_count=user_count,
        permissions=[
            PermissionResponse(
                id=p.id,
                code=p.code,
                module=p.module,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
            )
            for p in r.permissions
        ],
        created_at=r.created_at,
    )


@router.put(
    "/roles/{role_id}",
    response_model=RoleDetailResponse,
    summary="Cập nhật tên và mô tả vai trò",
)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật thông tin hiển thị của vai trò."""
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vai trò với ID '{role_id}'.",
        )

    if payload.name is not None:
        r.name = payload.name.strip()
    if payload.description is not None:
        r.description = payload.description.strip() if payload.description else None

    await db.commit()

    uc_stmt = select(func.count(UserRole.user_id)).where(UserRole.role_id == role_id)
    uc_res = await db.execute(uc_stmt)
    user_count = uc_res.scalar_one()

    return RoleDetailResponse(
        id=r.id,
        code=r.code,
        name=r.name,
        description=r.description,
        is_system=r.is_system,
        user_count=user_count,
        permissions=[
            PermissionResponse(
                id=p.id,
                code=p.code,
                module=p.module,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
            )
            for p in r.permissions
        ],
        created_at=r.created_at,
    )


@router.put(
    "/roles/{role_id}/permissions",
    response_model=RoleDetailResponse,
    summary="Cập nhật ma trận quyền hạn cho vai trò (Permission Matrix)",
)
async def update_role_permissions(
    role_id: uuid.UUID,
    payload: RolePermissionsUpdate,
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Cập nhật tập hợp các quyền được cấp cho một vai trò."""
    stmt = (
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vai trò với ID '{role_id}'.",
        )

    # 1. Xác thực các permission_ids tồn tại
    if payload.permission_ids:
        perm_check = await db.execute(
            select(Permission.id).where(Permission.id.in_(payload.permission_ids))
        )
        existing_perm_ids = set(perm_check.scalars().all())
        if len(existing_perm_ids) != len(payload.permission_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Một hoặc nhiều quyền được chỉ định không tồn tại.",
            )

    # 2. Xóa liên kết quyền cũ của vai trò
    await db.execute(
        delete(RolePermission).where(RolePermission.role_id == role_id)
    )

    # 3. Thêm mới danh sách quyền
    for p_id in payload.permission_ids:
        db.add(
            RolePermission(
                role_id=role_id,
                permission_id=p_id,
            )
        )

    await db.commit()
    db.expire_all()

    # Nạp lại dữ liệu
    refetched = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions))
        .where(Role.id == role_id)
    )
    role_record = refetched.scalar_one()

    uc_stmt = select(func.count(UserRole.user_id)).where(UserRole.role_id == role_id)
    uc_res = await db.execute(uc_stmt)
    user_count = uc_res.scalar_one()

    return RoleDetailResponse(
        id=role_record.id,
        code=role_record.code,
        name=role_record.name,
        description=role_record.description,
        is_system=role_record.is_system,
        user_count=user_count,
        permissions=[
            PermissionResponse(
                id=p.id,
                code=p.code,
                module=p.module,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
            )
            for p in role_record.permissions
        ],
        created_at=role_record.created_at,
    )


@router.delete(
    "/roles/{role_id}",
    summary="Xóa vai trò tùy biến",
)
async def delete_role(
    role_id: uuid.UUID,
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Xóa vai trò tùy biến (không cho phép xóa vai trò hệ thống hoặc vai trò đang có nhân viên sử dụng)."""
    stmt = select(Role).where(Role.id == role_id)
    res = await db.execute(stmt)
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy vai trò với ID '{role_id}'.",
        )

    if r.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vai trò '{r.name}' là vai trò hệ thống mặc định và không thể bị xóa.",
        )

    # Kiểm tra xem có người dùng nào đang giữ vai trò này không
    uc_stmt = select(func.count(UserRole.user_id)).where(UserRole.role_id == role_id)
    uc_res = await db.execute(uc_stmt)
    user_count = uc_res.scalar_one()
    if user_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vai trò '{r.name}' hiện đang được gán cho {user_count} nhân viên. Vui lòng chuyển vai trò của họ trước khi xóa.",
        )

    await db.delete(r)
    await db.commit()
    return {"message": f"Đã xóa vai trò '{r.name}' thành công."}


# =========================================================================
# 3. Permission Catalog Endpoints
# =========================================================================

@router.get(
    "/permissions",
    response_model=List[PermissionGroupResponse],
    summary="Danh mục tất cả quyền nguyên tử gom nhóm theo phân hệ",
)
async def list_permissions(
    current_user: User = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Lấy danh mục tất cả 21 quyền hạn chuẩn trong hệ thống để hiển thị ma trận phân quyền."""
    stmt = select(Permission).order_by(Permission.module, Permission.code)
    res = await db.execute(stmt)
    permissions = res.scalars().all()

    # Gom nhóm theo module
    groups: Dict[str, List[PermissionResponse]] = {}
    for p in permissions:
        if p.module not in groups:
            groups[p.module] = []
        groups[p.module].append(
            PermissionResponse(
                id=p.id,
                code=p.code,
                module=p.module,
                name=p.name,
                description=p.description,
                created_at=p.created_at,
            )
        )

    result = []
    for mod_key, perms_list in groups.items():
        result.append(
            PermissionGroupResponse(
                module=mod_key,
                module_name=MODULE_DISPLAY_NAMES.get(mod_key, mod_key.capitalize()),
                permissions=perms_list,
            )
        )

    return result

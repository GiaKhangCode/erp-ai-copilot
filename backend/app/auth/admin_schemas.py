from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    module: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PermissionGroupResponse(BaseModel):
    module: str
    module_name: str
    permissions: List[PermissionResponse]


class RoleBriefResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RoleDetailResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    is_system: bool = False
    user_count: int = 0
    permissions: List[PermissionResponse] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RoleCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=50, description="Mã vai trò (slug, ví dụ: 'auditor', 'qc_lead')")
    name: str = Field(..., min_length=2, max_length=100, description="Tên vai trò hiển thị")
    description: Optional[str] = Field(None, max_length=500)
    permission_ids: List[UUID] = Field(default_factory=list, description="Danh sách ID các quyền gán ban đầu")


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class RolePermissionsUpdate(BaseModel):
    permission_ids: List[UUID] = Field(..., description="Tập hợp ID quyền hạn mới cho vai trò")


class UserAdminCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, description="Địa chỉ email nhân viên")
    password: str = Field(..., min_length=6, description="Mật khẩu khởi tạo (tối thiểu 6 ký tự)")
    full_name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    department: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    role_ids: List[UUID] = Field(default_factory=list, description="Danh sách ID các vai trò gán cho nhân viên")
    is_active: bool = True
    is_superuser: bool = False


class UserAdminUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    department: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    role_ids: Optional[List[UUID]] = Field(None, description="Danh sách ID các vai trò mới")


class UserStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="True = Kích hoạt, False = Khóa tài khoản")


class UserResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, description="Mật khẩu mới (tối thiểu 6 ký tự)")


class UserAdminDetailResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool = False
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    roles: List[RoleBriefResponse] = []
    permissions: List[str] = []
    model_config = ConfigDict(from_attributes=True)


class UserAdminListResponse(BaseModel):
    items: List[UserAdminDetailResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogItemResponse(BaseModel):
    id: str
    actor_id: str
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    resource_type: str
    resource_id: str
    result: str
    ip_address: Optional[str] = None
    details: Optional[dict] = None
    created_at: Optional[str] = None


class AuditLogListResponse(BaseModel):
    items: List[AuditLogItemResponse]
    total: int
    page: int
    limit: int
    total_pages: int


class AuditLogStatsResponse(BaseModel):
    total_logs: int
    by_resource: List[dict]
    by_action: List[dict]
    top_users: List[dict]


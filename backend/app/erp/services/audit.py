import logging
import math
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.erp.models import AuditLog, User

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    async def log_activity(
        session: AsyncSession,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[Union[str, uuid.UUID]] = None,
        actor: Optional[Union[User, uuid.UUID]] = None,
        actor_id: Optional[Union[uuid.UUID, str]] = None,
        actor_email: Optional[str] = None,
        actor_role: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[Union[str, uuid.UUID]] = None,
        result: str = "success",
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """
        Ghi nhật ký kiểm toán cho một thao tác nghiệp vụ hoặc bảo mật.
        Hàm được thiết kế an toàn, không ném lỗi ra ngoài làm nghẽn luồng nghiệp vụ chính.
        Hỗ trợ linh hoạt cả actor/actor_id, resource_type/target_type, resource_id/target_id.
        """
        try:
            eff_resource_type = resource_type or target_type or "system"
            eff_resource_id = str(resource_id if resource_id is not None else (target_id or ""))

            final_actor_id = None
            if isinstance(actor, User):
                final_actor_id = actor.id
                if not actor_email:
                    actor_email = actor.email
                if not actor_role:
                    actor_role = actor.role.value if hasattr(actor.role, "value") else str(actor.role)
            elif isinstance(actor, uuid.UUID):
                final_actor_id = actor
            elif actor_id is not None:
                if isinstance(actor_id, uuid.UUID):
                    final_actor_id = actor_id
                else:
                    try:
                        final_actor_id = uuid.UUID(str(actor_id))
                    except Exception:
                        final_actor_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            elif actor is None:
                # Nếu không có actor (ví dụ đăng nhập thất bại tài khoản chưa tồn tại)
                final_actor_id = uuid.UUID("00000000-0000-0000-0000-000000000000")

            log_entry = AuditLog(
                actor_id=final_actor_id,
                actor_email=actor_email,
                actor_role=actor_role,
                action=action,
                resource_type=eff_resource_type,
                resource_id=eff_resource_id,
                result=result,
                ip_address=ip_address,
                details=details,
            )
            session.add(log_entry)
            # Không commit ở đây để tuân theo transaction chung của caller
            return log_entry
        except Exception as e:
            logger.error("Failed to record audit log: %s", e)
            return None

    @staticmethod
    async def get_logs(
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        actor_email: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Truy vấn danh sách nhật ký kiểm toán kèm phân trang và bộ lọc nâng cao."""
        stmt = select(AuditLog)

        if actor_email:
            stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor_email.strip()}%"))
        if action:
            stmt = stmt.where(AuditLog.action == action.strip())
        if resource_type:
            stmt = stmt.where(AuditLog.resource_type == resource_type.strip())
        if from_date:
            stmt = stmt.where(AuditLog.created_at >= from_date)
        if to_date:
            stmt = stmt.where(AuditLog.created_at <= to_date)

        # Đếm tổng số bản ghi
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_res = await session.execute(count_stmt)
        total = total_res.scalar() or 0

        # Phân trang & sắp xếp mới nhất lên đầu
        offset = (page - 1) * limit
        stmt = stmt.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
        res = await session.execute(stmt)
        logs = res.scalars().all()

        total_pages = math.ceil(total / limit) if limit > 0 else 1

        items = []
        for l in logs:
            items.append({
                "id": str(l.id),
                "actor_id": str(l.actor_id),
                "actor_email": l.actor_email or "Hệ thống",
                "actor_role": l.actor_role or "N/A",
                "action": l.action,
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "result": l.result,
                "ip_address": l.ip_address,
                "details": l.details,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
        }

    @staticmethod
    async def get_stats(session: AsyncSession) -> Dict[str, Any]:
        """Thống kê tổng quan hoạt động kiểm toán."""
        # 1. Tổng số logs
        total_logs = (await session.execute(select(func.count(AuditLog.id)))).scalar() or 0

        # 2. Phân loại theo resource_type
        res_stmt = (
            select(AuditLog.resource_type, func.count(AuditLog.id))
            .group_by(AuditLog.resource_type)
            .order_by(desc(func.count(AuditLog.id)))
            .limit(10)
        )
        res_types = (await session.execute(res_stmt)).all()
        by_resource = [{"resource_type": r[0], "count": r[1]} for r in res_types]

        # 3. Phân loại theo action
        act_stmt = (
            select(AuditLog.action, func.count(AuditLog.id))
            .group_by(AuditLog.action)
            .order_by(desc(func.count(AuditLog.id)))
            .limit(10)
        )
        actions = (await session.execute(act_stmt)).all()
        by_action = [{"action": a[0], "count": a[1]} for a in actions]

        # 4. Top active actors
        user_stmt = (
            select(AuditLog.actor_email, func.count(AuditLog.id))
            .where(AuditLog.actor_email.isnot(None))
            .group_by(AuditLog.actor_email)
            .order_by(desc(func.count(AuditLog.id)))
            .limit(5)
        )
        top_users = (await session.execute(user_stmt)).all()
        by_user = [{"email": u[0], "count": u[1]} for u in top_users]

        return {
            "total_logs": total_logs,
            "by_resource": by_resource,
            "by_action": by_action,
            "top_users": by_user,
        }

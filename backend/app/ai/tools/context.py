import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class UserContext:
    user_id: Optional[uuid.UUID] = None
    user_role: Optional[str] = None
    user_name: Optional[str] = None


# Thread-safe and async-safe context variable for holding current authenticated user info
current_user_context: ContextVar[UserContext] = ContextVar(
    "current_user_context",
    default=UserContext(),
)


def get_current_user_context() -> UserContext:
    return current_user_context.get()


def set_current_user_context(
    user_context_or_id: Optional[Any] = None,
    user_role: Optional[str] = None,
    user_name: Optional[str] = None,
    user_id: Optional[Any] = None,
):
    if isinstance(user_context_or_id, UserContext):
        current_user_context.set(user_context_or_id)
    else:
        uid = user_id if user_id is not None else user_context_or_id
        current_user_context.set(
            UserContext(user_id=uid, user_role=user_role, user_name=user_name)
        )

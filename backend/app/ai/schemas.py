import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Payload gửi lên endpoint POST /api/v1/chat"""
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="ID cuộc hội thoại. Nếu null, hệ thống sẽ tự động tạo cuộc hội thoại mới.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Nội dung câu hỏi hoặc yêu cầu nghiệp vụ của người dùng.",
    )
    attachments: Optional[List[Any]] = Field(
        default_factory=list,
        description="Danh sách tài liệu/file đính kèm (nếu có).",
    )
    response_mode: Optional[str] = Field(
        default="sync",
        description="Chế độ phản hồi: 'sync' (đồng bộ) hoặc 'stream' (SSE).",
    )


class ChatCitation(BaseModel):
    """Trích dẫn tài liệu tham chiếu từ RAG"""
    filename: str
    page_number: Optional[int] = None
    chunk_index: Optional[int] = None
    quote: str


class ThoughtStep(BaseModel):
    """Một bước suy nghĩ/truy vấn của AI Copilot"""
    step: str
    title: str
    detail: Optional[str] = None
    status: str = "completed"


class ChatResponse(BaseModel):
    """Phản hồi nghiệp vụ từ Agent Orchestrator theo chuẩn Blueprint Section 5.1"""
    conversation_id: uuid.UUID
    run_id: uuid.UUID
    status: str = "completed"
    answer: str
    intent: Optional[str] = None
    citations: List[ChatCitation] = Field(default_factory=list)
    proposed_action: Optional[Dict[str, Any]] = None
    requires_confirmation: bool = False
    thought_steps: List[ThoughtStep] = Field(default_factory=list)


class MessageItem(BaseModel):
    """Tin nhắn đơn lẻ trong lịch sử hội thoại"""
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ConversationItem(BaseModel):
    """Tóm tắt cuộc hội thoại trong danh sách"""
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    message_count: int


class ConversationDetail(BaseModel):
    """Chi tiết cuộc hội thoại kèm toàn bộ lịch sử tin nhắn"""
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    messages: List[MessageItem]

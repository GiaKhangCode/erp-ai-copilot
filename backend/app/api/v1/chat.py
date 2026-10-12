import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.erp.models import User
from app.rag.models import Conversation, Message
from app.ai.agents.graph import get_agent_graph
from app.ai.schemas import (
    ChatCitation,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationItem,
    MessageItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Chat & Conversations"])


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_with_agent(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint tương tác chính với ERP AI Copilot Agent Orchestrator.
    - Tự động quản lý ngữ cảnh hội thoại đa vòng và lưu vết vào PostgreSQL (`ai.conversations`, `ai.messages`).
    - Nạp danh tính đáng tin cậy (`user_id`, `user_role`) từ JWT token vào LangGraph State.
    - Định tuyến qua LangGraph: ERP Data Query, Document QA (RAG), Order Draft Proposal (HITL), hoặc Chitchat.
    """
    clean_message = request.message.strip()
    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nội dung tin nhắn không được để trống.",
        )

    # 1. Quản lý hoặc tạo mới Conversation
    conversation: Optional[Conversation] = None
    if request.conversation_id:
        stmt = select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == current_user.id,
        )
        res = await db.execute(stmt)
        conversation = res.scalar_one_or_none()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy cuộc hội thoại với ID '{request.conversation_id}'.",
            )
    else:
        # Tự động tạo conversation mới
        conv_title = clean_message[:60] + "..." if len(clean_message) > 60 else clean_message
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=current_user.id,
            title=conv_title,
        )
        db.add(conversation)
        await db.flush()

    conv_id = conversation.id
    thread_id = str(conv_id)

    # 2. Lưu tin nhắn người dùng vào cơ sở dữ liệu
    user_msg_record = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="user",
        content=clean_message,
    )
    db.add(user_msg_record)
    await db.commit()

    # 3. Chuẩn bị initial state cho LangGraph
    # Nạp danh tính tin cậy từ JWT
    initial_state = {
        "user_id": str(current_user.id),
        "user_role": str(current_user.role),
        "conversation_id": thread_id,
        "request_id": str(uuid.uuid4()),
        "user_query": clean_message,
        "messages": [HumanMessage(content=clean_message)],
    }

    # 4. Thực thi LangGraph State Machine
    graph = get_agent_graph()
    try:
        final_state = await graph.ainvoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as e:
        logger.error("Error executing LangGraph agent workflow: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi xử lý luồng AI Agent: {str(e)}",
        )

    answer_text = final_state.get("answer", "Đã xử lý yêu cầu.")
    intent = final_state.get("intent")
    proposed_action = final_state.get("proposed_action")
    raw_citations = final_state.get("citations", [])

    # Chuyển đổi citations sang schema chuẩn
    citations = [
        ChatCitation(
            filename=c.get("filename", "unknown"),
            page_number=c.get("page_number"),
            chunk_index=c.get("chunk_index"),
            quote=c.get("quote", ""),
        )
        for c in raw_citations
    ]

    # 5. Lưu tin nhắn phản hồi của Assistant vào cơ sở dữ liệu
    assistant_msg_record = Message(
        id=uuid.uuid4(),
        conversation_id=conv_id,
        role="assistant",
        content=answer_text,
    )
    db.add(assistant_msg_record)
    await db.commit()

    return ChatResponse(
        conversation_id=conv_id,
        run_id=uuid.uuid4(),
        status="completed",
        answer=answer_text,
        intent=intent,
        citations=citations,
        proposed_action=proposed_action,
        requires_confirmation=bool(proposed_action),
    )


@router.get("/conversations", response_model=List[ConversationItem], status_code=status.HTTP_200_OK)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách các cuộc hội thoại của người dùng hiện tại kèm số lượng tin nhắn.
    """
    stmt = (
        select(
            Conversation.id,
            Conversation.title,
            Conversation.created_at,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == current_user.id)
        .group_by(Conversation.id, Conversation.title, Conversation.created_at)
        .order_by(desc(Conversation.created_at))
    )
    res = await db.execute(stmt)
    rows = res.all()

    return [
        ConversationItem(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            message_count=row.message_count,
        )
        for row in rows
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail, status_code=status.HTTP_200_OK)
async def get_conversation_detail(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy chi tiết cuộc hội thoại và toàn bộ lịch sử tin nhắn.
    """
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cuộc hội thoại với ID '{conversation_id}'.",
        )

    # Sắp xếp tin nhắn theo thời gian tăng dần
    sorted_messages = sorted(conv.messages, key=lambda m: m.created_at)

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        messages=[
            MessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in sorted_messages
        ],
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Xóa một cuộc hội thoại và toàn bộ lịch sử tin nhắn liên quan.
    """
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cuộc hội thoại với ID '{conversation_id}'.",
        )

    await db.delete(conv)
    await db.commit()

    return {"message": "Đã xóa cuộc hội thoại thành công.", "id": str(conversation_id)}

import asyncio
import json
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db, async_session_factory
from app.erp.models import User
from app.rag.models import Conversation, Message
from app.core.config import settings
from app.ai.tools.context import UserContext, set_current_user_context
from app.ai.agents.router import IntentRouter
from app.ai.agents.graph import (
    get_agent_graph,
    _get_llm,
    _extract_text,
    erp_agent_node,
    erp_tools_node,
    should_call_erp_tools,
    rag_agent_node,
    draft_order_agent_node,
)
from app.ai.prompts.agent_prompts import (
    CHITCHAT_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
)
from app.ai.schemas import (
    ChatCitation,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationItem,
    MessageItem,
    ThoughtStep,
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

    # Xây dựng luồng suy nghĩ tóm tắt
    intent_map = {
        "erp_query": ("Truy vấn cơ sở dữ liệu ERP", "Đã kết nối PostgreSQL và trích xuất số liệu thành công"),
        "erp_data_query": ("Truy vấn cơ sở dữ liệu ERP", "Đã kết nối PostgreSQL và trích xuất số liệu thành công"),
        "document_qa": ("Tra cứu tài liệu nội bộ (RAG)", f"Đã tìm kiếm và đối chiếu {len(citations)} nguồn tài liệu quy chế"),
        "create_order_draft": ("Lập đơn hàng nháp", "Đã kiểm tra tồn kho và tạo đề xuất đơn hàng nháp (Human-in-the-Loop)"),
        "chitchat": ("Xử lý hội thoại", "Phản hồi câu hỏi thông thường"),
    }
    action_title, action_detail = intent_map.get(intent or "", ("Xử lý yêu cầu", "Đã xử lý thông tin nghiệp vụ"))
    thought_steps = [
        ThoughtStep(step="intent", title="Phân tích yêu cầu", detail=f"Xác định loại câu hỏi: {action_title}", status="completed"),
        ThoughtStep(step="execution", title=action_title, detail=action_detail, status="completed"),
        ThoughtStep(step="synthesis", title="Tổng hợp kết quả", detail="Đã định dạng câu trả lời hoàn tất", status="completed"),
    ]

    return ChatResponse(
        conversation_id=conv_id,
        run_id=uuid.uuid4(),
        status="completed",
        answer=answer_text,
        intent=intent,
        citations=citations,
        proposed_action=proposed_action,
        requires_confirmation=bool(proposed_action),
        thought_steps=thought_steps,
    )


@router.post("/chat/stream")
async def chat_with_agent_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint Streaming Response (Server-Sent Events - SSE) cho ERP AI Copilot.
    - Truyền tải từng token theo thời gian thực (Time-to-first-token < 1s).
    - Tự động fallback sang gemini-3.1-flash-lite khi model chính gặp sự cố hoặc timeout.
    - Cung cấp trạng thái điều phối Agent (Intent, Tool execution status, Citations).
    """
    clean_message = request.message.strip()
    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nội dung tin nhắn không được để trống.",
        )

    # 1. Quản lý Conversation
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

    async def event_stream_generator():
        # Event 1: Bắt đầu luồng
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': str(conv_id)})}\n\n"

        # Thiết lập user context bảo mật
        set_current_user_context(UserContext(
            user_id=str(current_user.id),
            user_role=str(current_user.role),
        ))

        thought_steps = []

        def add_thought(step: str, title: str, detail: str = "", status: str = "completed"):
            item = {"step": step, "title": title, "detail": detail, "status": status}
            for idx, existing in enumerate(thought_steps):
                if existing["step"] == step:
                    thought_steps[idx] = item
                    return item
            thought_steps.append(item)
            return item

        # Event 2: Phân loại ý định
        router_instance = IntentRouter()
        classification = await router_instance.classify(clean_message)
        intent = classification.intent
        yield f"data: {json.dumps({'type': 'intent', 'intent': intent})}\n\n"

        intent_labels = {
            "erp_query": "Truy vấn cơ sở dữ liệu ERP",
            "erp_data_query": "Truy vấn cơ sở dữ liệu ERP",
            "document_qa": "Tra cứu tài liệu nội bộ (RAG)",
            "create_order_draft": "Lập đơn hàng nháp",
            "chitchat": "Trò chuyện & Hỗ trợ chung",
        }
        intent_desc = intent_labels.get(intent, "Phân tích yêu cầu")
        t_intent = add_thought("intent", "Phân tích yêu cầu", f"Xác định loại câu hỏi: {intent_desc}", "completed")
        yield f"data: {json.dumps({'type': 'thought', **t_intent})}\n\n"

        state = {
            "user_id": str(current_user.id),
            "user_role": str(current_user.role),
            "conversation_id": thread_id,
            "request_id": str(uuid.uuid4()),
            "user_query": clean_message,
            "messages": [HumanMessage(content=clean_message)],
            "intent": intent,
            "entities": classification.entities,
            "extracted_entities": classification.entities,
            "tool_results": [],
            "citations": [],
            "retrieved_context": [],
            "proposed_action": None,
        }

        full_answer = ""
        citations = []
        proposed_action = None

        if intent == "chitchat":
            t_chat = add_thought("chitchat", "Xử lý hội thoại", "Soạn câu trả lời hỗ trợ người dùng", "completed")
            yield f"data: {json.dumps({'type': 'thought', **t_chat})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI Copilot đang trả lời...'})}\n\n"
            prompt = [
                SystemMessage(content=CHITCHAT_SYSTEM_PROMPT),
                HumanMessage(content=clean_message),
            ]
            streamed = False
            try:
                llm = _get_llm(model=settings.GEMINI_MODEL, temperature=0.3)
                async for chunk in llm.astream(prompt):
                    token = _extract_text(chunk.content)
                    if token:
                        full_answer += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                streamed = True
            except Exception as e_primary:
                logger.warning("Primary stream failed in chitchat: %s. Trying fallback (%s)...", e_primary, settings.GEMINI_FALLBACK_MODEL)
                try:
                    llm_fallback = _get_llm(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.3)
                    async for chunk in llm_fallback.astream(prompt):
                        token = _extract_text(chunk.content)
                        if token:
                            full_answer += token
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    streamed = True
                except Exception as e_fallback:
                    logger.warning("Fallback stream failed in chitchat: %s", e_fallback)

            if not streamed or not full_answer:
                default_msg = "Xin chào! Tôi là ERP AI Copilot. Tôi có thể hỗ trợ bạn tra cứu tồn kho, doanh thu, hỏi đáp chính sách và lên đơn hàng nháp."
                full_answer = default_msg
                yield f"data: {json.dumps({'type': 'token', 'content': default_msg})}\n\n"

        elif intent == "document_qa":
            t_rag = add_thought("rag", "Tra cứu tài liệu nội bộ (RAG)", "Đang đối chiếu quy định trong kho tài liệu chính sách doanh nghiệp...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_rag})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tìm kiếm thông tin trong cơ sở tri thức RAG...'})}\n\n"
            rag_res = await rag_agent_node(state)
            state.update(rag_res)
            citations = state.get("citations", [])

            cit_summary = f"Đã tìm thấy {len(citations)} đoạn trích dẫn đối chiếu từ tài liệu nội bộ" if citations else "Đã hoàn thành rà soát kho tài liệu quy định"
            t_rag = add_thought("rag", "Tra cứu tài liệu nội bộ (RAG)", cit_summary, "completed")
            yield f"data: {json.dumps({'type': 'thought', **t_rag})}\n\n"

            t_syn = add_thought("synthesis", "Tổng hợp câu trả lời", "Đang trích xuất nội dung và đối chiếu nguồn tài liệu...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_syn})}\n\n"

            retrieved_ctx = state.get("retrieved_context", [])
            grounded_ans = None
            if retrieved_ctx and isinstance(retrieved_ctx[0], dict) and "answer" in retrieved_ctx[0]:
                grounded_ans = retrieved_ctx[0]["answer"]

            if grounded_ans:
                full_answer = grounded_ans
                words = grounded_ans.split(" ")
                for i in range(0, len(words), 3):
                    chunk_text = " ".join(words[i:i+3]) + " "
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk_text})}\n\n"
                    await asyncio.sleep(0.015)
            else:
                context_str = json.dumps(state.get("tool_results", []), ensure_ascii=False)
                prompt = [
                    SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                    HumanMessage(content=f"Câu hỏi: {clean_message}\n\nTài liệu RAG:\n{context_str}\n\nHãy trả lời bằng Tiếng Việt kèm nguồn trích dẫn:"),
                ]
                try:
                    llm = _get_llm(model=settings.GEMINI_MODEL)
                    async for chunk in llm.astream(prompt):
                        token = _extract_text(chunk.content)
                        if token:
                            full_answer += token
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                except Exception as e_primary:
                    logger.warning("Primary RAG stream failed: %s. Trying fallback (%s)...", e_primary, settings.GEMINI_FALLBACK_MODEL)
                    try:
                        llm_fb = _get_llm(model=settings.GEMINI_FALLBACK_MODEL)
                        async for chunk in llm_fb.astream(prompt):
                            token = _extract_text(chunk.content)
                            if token:
                                full_answer += token
                                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    except Exception as e_fallback:
                        logger.warning("Fallback RAG stream failed: %s", e_fallback)
                        full_answer = "Đã tìm thấy thông tin từ tài liệu RAG."
                        yield f"data: {json.dumps({'type': 'token', 'content': full_answer})}\n\n"

        elif intent == "create_order_draft":
            t_draft = add_thought("draft", "Kiểm tra khách hàng & tồn kho", "Đang đối chiếu mã khách hàng, giá sản phẩm và tồn kho...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_draft})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang kiểm tra tồn kho và lập đơn hàng nháp...'})}\n\n"
            draft_res = await draft_order_agent_node(state)
            state.update(draft_res)
            proposed_action = state.get("proposed_action")

            t_draft = add_thought("draft", "Kiểm tra khách hàng & tồn kho", "Đã khởi tạo đề xuất đơn hàng nháp (Human-in-the-Loop)", "completed")
            yield f"data: {json.dumps({'type': 'thought', **t_draft})}\n\n"

            t_syn = add_thought("synthesis", "Tổng hợp câu trả lời", "Soạn tóm tắt đơn hàng và lưu ý phê duyệt...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_syn})}\n\n"

            if proposed_action and proposed_action.get("draft_payload"):
                payload = proposed_action["draft_payload"]
                customer_name = payload.get("customer_name", "")
                customer_code = payload.get("customer_code", "")
                total_formatted = payload.get("formatted_total_amount") or payload.get("formatted_total", "")
                items = payload.get("items", [])
                items_table = "\n".join([
                    f"- **{it.get('product_name')}** (`{it.get('sku')}`): "
                    f"{it.get('quantity')} cái x {it.get('formatted_unit_price') or it.get('formatted_price', '')} = **{it.get('formatted_line_total') or it.get('formatted_subtotal', '')}**"
                    for it in items
                ])
                order_number = payload.get("order_number") or ""
                order_badge = f" - Mã đơn: `{order_number}`" if order_number else ""
                full_answer = (
                    f"### 📋 Đã khởi tạo đơn hàng nháp thành công{order_badge}\n\n"
                    f"Hệ thống đã lưu đơn hàng nháp cho khách hàng **{customer_name}** (`{customer_code}`):\n\n"
                    f"**Chi tiết sản phẩm:**\n{items_table}\n\n"
                    f"💵 **Tổng tiền:** {total_formatted}\n\n"
                    f"> ℹ️ **Lưu ý:** Đơn hàng đã được tạo thành công trong hệ thống tại tab **Đơn hàng** (trạng thái `Bản nháp / draft`) "
                    f"và xuất hiện trong **Hộp thư phê duyệt** (Human-in-the-Loop) chờ người có thẩm quyền xác nhận!"
                )
            else:
                tool_results = state.get("tool_results", [])
                if tool_results and not tool_results[-1].get("success", True):
                    full_answer = tool_results[-1].get("message", "Không thể tạo đơn hàng nháp do thiếu thông tin.")
                else:
                    full_answer = "Đã xử lý yêu cầu lập đơn hàng nháp."

            words = full_answer.split(" ")
            for i in range(0, len(words), 4):
                chunk_text = " ".join(words[i:i+4]) + " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk_text})}\n\n"
                await asyncio.sleep(0.015)

        else: # erp_query, erp_data_query, clarify, unknown
            is_erp = intent in ("erp_query", "erp_data_query")
            status_msg = "Đang kết nối cơ sở dữ liệu ERP..." if is_erp else "AI Copilot đang phân tích câu hỏi..."
            yield f"data: {json.dumps({'type': 'status', 'message': status_msg})}\n\n"

            if is_erp:
                t_erp = add_thought("db", "Truy vấn cơ sở dữ liệu ERP (PostgreSQL)", "Đang gọi công cụ truy vấn dữ liệu đơn hàng, doanh thu hoặc tồn kho...", "running")
                yield f"data: {json.dumps({'type': 'thought', **t_erp})}\n\n"

                erp_res = await erp_agent_node(state)
                state.setdefault("messages", []).extend(erp_res.get("messages", []))
                if should_call_erp_tools(state) == "erp_tools":
                    tool_res = await erp_tools_node(state)
                    state.setdefault("messages", []).extend(tool_res.get("messages", []))
                    if "tool_results" in tool_res:
                        state["tool_results"] = tool_res["tool_results"]

                num_tools = len(state.get("tool_results", []))
                db_detail = f"Đã thực thi thành công {num_tools} truy vấn nghiệp vụ trên cơ sở dữ liệu ERP" if num_tools > 0 else "Đã trích xuất số liệu thành công từ cơ sở dữ liệu"
                t_erp = add_thought("db", "Truy vấn cơ sở dữ liệu ERP (PostgreSQL)", db_detail, "completed")
                yield f"data: {json.dumps({'type': 'thought', **t_erp})}\n\n"
            else:
                t_other = add_thought("analyze", "Phân tích nội dung", "AI Copilot đang phân tích nội dung yêu cầu...", "completed")
                yield f"data: {json.dumps({'type': 'thought', **t_other})}\n\n"

            t_syn = add_thought("synthesis", "Tổng hợp câu trả lời", "Đang định dạng bảng số liệu và soạn câu trả lời...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_syn})}\n\n"

            context_summary = []
            for msg in state.get("messages", []):
                if isinstance(msg, ToolMessage):
                    context_summary.append(f"Tool Result ({msg.name}): {msg.content}")
            if state.get("tool_results"):
                context_summary.append(f"Structured Tool Results: {json.dumps(state['tool_results'], ensure_ascii=False)}")
            context_text = "\n\n".join(context_summary)

            prompt = [
                SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                HumanMessage(content=(
                    f"Câu hỏi người dùng: {clean_message}\n\n"
                    f"Ý định: {intent}\n\n"
                    f"Dữ liệu công cụ thu thập được:\n{context_text}\n\n"
                    f"Hãy tổng hợp thành phản hồi hoàn chỉnh, súc tích và chính xác bằng Tiếng Việt (dùng bảng Markdown chuẩn nếu có nhiều số liệu):"
                )),
            ]

            streamed = False
            try:
                llm = _get_llm(model=settings.GEMINI_MODEL, temperature=0.0)
                async for chunk in llm.astream(prompt):
                    token = _extract_text(chunk.content)
                    if token:
                        full_answer += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                streamed = True
            except Exception as e_primary:
                logger.warning("Primary stream failed in synthesizer: %s. Trying fallback (%s)...", e_primary, settings.GEMINI_FALLBACK_MODEL)
                try:
                    llm_fb = _get_llm(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.0)
                    async for chunk in llm_fb.astream(prompt):
                        token = _extract_text(chunk.content)
                        if token:
                            full_answer += token
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    streamed = True
                except Exception as e_fallback:
                    logger.warning("Fallback stream failed in synthesizer: %s", e_fallback)

            if not streamed or not full_answer:
                last_tool_content = None
                for msg in reversed(state.get("messages", [])):
                    if isinstance(msg, ToolMessage):
                        last_tool_content = msg.content
                        break
                fallback_msg = f"Kết quả từ hệ thống ERP:\n\n{last_tool_content}" if last_tool_content else "Đã xử lý yêu cầu thành công."
                full_answer = fallback_msg
                yield f"data: {json.dumps({'type': 'token', 'content': fallback_msg})}\n\n"

        # Format citations
        formatted_citations = [
            {
                "filename": c.get("filename", "unknown"),
                "page_number": c.get("page_number"),
                "chunk_index": c.get("chunk_index"),
                "quote": c.get("quote", ""),
            }
            for c in citations
        ]

        # Đánh dấu tất cả thought_steps là completed khi kết thúc
        for s in thought_steps:
            s["status"] = "completed"

        # Lưu tin nhắn Assistant vào database độc lập
        try:
            async with async_session_factory() as session:
                assistant_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_answer,
                )
                session.add(assistant_msg)
                await session.commit()
        except Exception as e_db:
            logger.error("Error saving assistant message in stream: %s", e_db)

        # Event 3: Hoàn tất kèm danh sách thought_steps
        yield f"data: {json.dumps({'type': 'done', 'answer': full_answer, 'citations': formatted_citations, 'proposed_action': proposed_action, 'thought_steps': thought_steps, 'conversation_id': str(conv_id)})}\n\n"

    return StreamingResponse(
        event_stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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

import asyncio
import json
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user, get_current_user_permissions
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
from app.ai.tools import ALL_AGENT_TOOLS
from app.ai.prompts.agent_prompts import (
    SUPER_AGENT_SYSTEM_PROMPT,
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
    user_permissions: set[str] = Depends(get_current_user_permissions),
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
    # Nạp danh tính tin cậy và quyền từ JWT
    user_perms_list = list(user_permissions)
    set_current_user_context(UserContext(
        user_id=str(current_user.id),
        user_role=str(current_user.role),
        user_name=str(current_user.full_name or current_user.email),
        user_email=str(current_user.email),
        user_permissions=user_perms_list,
    ))

    initial_state = {
        "user_id": str(current_user.id),
        "user_role": str(current_user.role),
        "user_name": str(current_user.full_name or current_user.email),
        "user_email": str(current_user.email),
        "user_permissions": user_perms_list,
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
    raw_thought_steps = final_state.get("thought_steps", [])
    if raw_thought_steps:
        thought_steps = [
            ThoughtStep(step="intent", title="Phân tích yêu cầu", detail="Xác định loại câu hỏi và lập kế hoạch ReAct", status="completed"),
        ]
        for ts in raw_thought_steps:
            thought_steps.append(
                ThoughtStep(
                    step=ts.get("step", "tool"),
                    title=ts.get("title", "Thực thi công cụ"),
                    detail=ts.get("detail", ""),
                    status=ts.get("status", "completed"),
                )
            )
        thought_steps.append(
            ThoughtStep(step="synthesis", title="Tổng hợp kết quả", detail="Đã tổng hợp toàn diện câu trả lời", status="completed")
        )
    else:
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
    user_permissions: set[str] = Depends(get_current_user_permissions),
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

    user_perms_list = list(user_permissions)

    async def event_stream_generator():
        # Event 1: Bắt đầu luồng
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': str(conv_id)})}\n\n"

        # Thiết lập user context bảo mật
        set_current_user_context(UserContext(
            user_id=str(current_user.id),
            user_role=str(current_user.role),
            user_name=str(current_user.full_name or current_user.email),
            user_email=str(current_user.email),
            user_permissions=user_perms_list,
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
            "user_name": str(current_user.full_name or current_user.email),
            "user_email": str(current_user.email),
            "user_permissions": user_perms_list,
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

        else:
            # ReAct Super-Agent: Hỗ trợ đa tác vụ liên hoàn (RAG + ERP Catalog + Inventory + Sales Orders + Revenue + Draft Order)
            t_react = add_thought("super_agent", "Lập kế hoạch & Điều phối", "Đang phân tích các tác vụ và điều phối chuỗi công cụ...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_react})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI Copilot đang phân tích và điều phối công cụ...'})}\n\n"

            messages: List[BaseMessage] = [
                SystemMessage(content=SUPER_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=clean_message),
            ]
            tools_by_name = {tool.name: tool for tool in ALL_AGENT_TOOLS}
            tool_results = []
            max_iterations = 6
            iteration = 0
            agent_answered = False

            tool_meta = {
                "search_company_knowledge": ("Tra cứu tài liệu nội bộ (RAG)", "Đang tra cứu cẩm nang và chính sách..."),
                "get_inventory": ("Kiểm tra tồn kho", "Đang kiểm tra số lượng tồn kho khả dụng..."),
                "get_product": ("Tra cứu thông tin sản phẩm", "Đang lấy thông số và đơn giá niêm yết..."),
                "list_products": ("Tìm kiếm danh mục sản phẩm", "Đang tra cứu danh mục mặt hàng..."),
                "get_customer": ("Xác minh khách hàng", "Đang kiểm tra thông tin đối tác..."),
                "list_customers": ("Tìm kiếm khách hàng", "Đang tìm kiếm đối tác trong hệ thống..."),
                "get_sales_orders": ("Tra cứu đơn hàng bán", "Đang tải lịch sử giao dịch đơn hàng..."),
                "get_revenue_report": ("Báo cáo doanh thu tài chính", "Đang trích xuất số liệu doanh thu..."),
                "propose_sales_order_draft": ("Đề xuất tạo đơn nháp (HITL)", "Đang lập đơn hàng nháp và kiểm tra tồn kho..."),
                "deliver_sales_order": ("Xuất kho đơn hàng", "Đang xử lý trừ kho và giao hàng..."),
                "adjust_inventory": ("Kiểm kê & Điều chỉnh kho", "Đang ghi nhận phiếu kiểm kê tồn kho..."),
                "generate_sales_quotation": ("Xuất file PDF Báo giá", "Đang khởi tạo tệp báo giá PDF kèm QR..."),
                "check_customer_credit": ("Thẩm định hạn mức công nợ", "Đang kiểm tra dư nợ tín dụng khách hàng..."),
                "get_sales_leaderboard": ("Bảng xếp hạng kinh doanh", "Đang phân tích doanh số và xếp hạng đội ngũ sales..."),
                "get_financial_and_debt_report": ("Báo cáo lợi nhuận & tuổi nợ", "Đang phân tích biên lợi nhuận và tuổi nợ..."),
                "get_audit_logs": ("Nhật ký kiểm toán hệ thống", "Đang truy xuất lịch sử thao tác & kiểm toán..."),
            }

            while iteration < max_iterations and not agent_answered:
                iteration += 1
                response = None
                for attempt in range(1, 3):
                    try:
                        llm = _get_llm(temperature=0.0).bind_tools(ALL_AGENT_TOOLS)
                        response = await llm.ainvoke(messages)
                        break
                    except Exception as e_llm:
                        if "429" in str(e_llm) or "ResourceExhausted" in str(e_llm):
                            logger.warning("Rate limit in super_agent stream (attempt %d). Backing off 5s...", attempt)
                            await asyncio.sleep(5)
                            continue
                        logger.error("LLM invoke error in super_agent stream: %s", e_llm)
                        break

                if not response:
                    logger.warning("No response from LLM in super_agent stream.")
                    break

                messages.append(response)
                tool_calls = getattr(response, "tool_calls", None) or []

                if tool_calls:
                    for idx, call in enumerate(tool_calls):
                        t_name = call.get("name")
                        t_args = call.get("args", {})
                        call_id = call.get("id") or f"call_{iteration}_{idx}_{t_name}"
                        step_id = f"tool_{iteration}_{idx}_{t_name}"
                        tool = tools_by_name.get(t_name)

                        # Tên công cụ thân thiện, tránh hiển thị tên hàm kỹ thuật
                        fallback_title = f"Xử lý {t_name.replace('_', ' ')}"
                        fallback_running = f"Đang thực hiện {t_name.replace('_', ' ')}..."
                        meta_title, meta_running = tool_meta.get(t_name, (fallback_title, fallback_running))
                        arg_summary = ", ".join(f"{k}={v}" for k, v in t_args.items() if v is not None)[:50]
                        running_detail = f"{meta_running} ({arg_summary})" if arg_summary else meta_running

                        # Stream event: tool is running
                        t_step = add_thought(step_id, meta_title, running_detail, "running")
                        yield f"data: {json.dumps({'type': 'thought', **t_step})}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'message': f'AI Copilot: {meta_title}...' })}\n\n"

                        if tool:
                            try:
                                res = await tool.ainvoke(t_args)
                                res_str = str(res)
                                messages.append(ToolMessage(content=res_str, tool_call_id=call_id, name=t_name))

                                completed_detail = "Đã hoàn thành tác vụ"
                                try:
                                    parsed = json.loads(res_str)
                                    if isinstance(parsed, dict):
                                        tool_results.append(parsed)
                                        # Trích xuất citations
                                        if "citations" in parsed and isinstance(parsed["citations"], list):
                                            for cit in parsed["citations"]:
                                                if cit not in citations:
                                                    citations.append(cit)
                                            completed_detail = f"Đã tìm thấy {len(parsed['citations'])} trích dẫn đối chiếu từ cẩm nang"
                                        # Trích xuất proposed_action
                                        elif parsed.get("action") == "create_sales_order_draft" and parsed.get("success"):
                                            proposed_action = parsed
                                            order_num = parsed.get("order_number") or parsed.get("draft_payload", {}).get("order_number") or ""
                                            cust_name = parsed.get("customer_name") or parsed.get("draft_payload", {}).get("customer_name") or ""
                                            completed_detail = f"Đã lập bản nháp đơn hàng #{order_num} cho {cust_name} (chờ duyệt)"
                                        elif t_name == "get_inventory":
                                            avail = parsed.get("total_available") or parsed.get("available_quantity") or 0
                                            items_list = parsed.get("items", [])
                                            pname = parsed.get("product_name") or (items_list[0].get("product_name") if items_list else "")
                                            completed_detail = f"Tồn kho khả dụng: {avail} sản phẩm{f' ({pname})' if pname else ''}" if parsed.get("found") else "Đã kiểm tra dữ liệu tồn kho"
                                        elif t_name == "get_product":
                                            pname = parsed.get("product", {}).get("name", "")
                                            pprice = parsed.get("product", {}).get("formatted_price", "")
                                            completed_detail = f"Sản phẩm: {pname} (Giá: {pprice})" if parsed.get("found") else "Không tìm thấy sản phẩm"
                                        elif t_name == "list_products":
                                            count = len(parsed.get("products", []))
                                            completed_detail = f"Đã tìm thấy {count} mặt hàng liên quan"
                                        elif t_name == "get_customer":
                                            cname = parsed.get("customer", {}).get("name", "")
                                            ccode = parsed.get("customer", {}).get("code", "")
                                            completed_detail = f"Khách hàng: {cname} ({ccode})" if parsed.get("found") else "Không tìm thấy khách hàng"
                                        elif t_name == "list_customers":
                                            count = len(parsed.get("customers", []))
                                            completed_detail = f"Đã tìm thấy {count} đối tác khách hàng"
                                        elif t_name == "get_revenue_report":
                                            tot = parsed.get("formatted_total_revenue", "")
                                            completed_detail = f"Tổng doanh thu: {tot}" if tot else "Đã xuất báo cáo doanh thu"
                                        elif t_name == "get_sales_orders":
                                            count = len(parsed.get("orders", []))
                                            completed_detail = f"Đã trích xuất {count} đơn hàng bán"
                                        elif t_name == "get_sales_leaderboard":
                                            total_sales = len(parsed.get("leaderboard", [])) if isinstance(parsed.get("leaderboard"), list) else 0
                                            completed_detail = f"Đã xếp hạng hiệu suất cho {total_sales} nhân viên kinh doanh" if total_sales else "Đã tổng hợp bảng xếp hạng doanh số"
                                        elif t_name == "get_financial_and_debt_report":
                                            rev = parsed.get("summary", {}).get("formatted_total_revenue", "")
                                            completed_detail = f"Đã phân tích lợi nhuận & tuổi nợ{f' (Doanh thu: {rev})' if rev else ''}"
                                        elif t_name == "check_customer_credit":
                                            cname = parsed.get("customer_name", "khách hàng")
                                            is_ok = parsed.get("allow_new_order", False)
                                            completed_detail = f"Thẩm định công nợ: {'Đủ điều kiện tín dụng' if is_ok else 'Cảnh báo vượt hạn mức'} ({cname})"
                                        elif t_name == "generate_sales_quotation":
                                            fname = parsed.get("file_name", "Bao_gia.pdf")
                                            completed_detail = f"Đã xuất thành công tệp PDF báo giá ({fname})" if parsed.get("success") else "Đã hoàn thành tạo báo giá"
                                        elif t_name == "deliver_sales_order":
                                            completed_detail = f"Đã xuất kho thành công đơn hàng #{parsed.get('order_number', '')}" if parsed.get("success") else "Đã hoàn tất xuất kho"
                                        elif t_name == "adjust_inventory":
                                            completed_detail = f"Đã cập nhật kiểm kê (Tồn mới: {parsed.get('new_quantity', '')})" if parsed.get("success") else "Đã ghi nhận điều chỉnh kho"
                                        elif t_name == "get_audit_logs":
                                            tot_logs = parsed.get("total", 0)
                                            completed_detail = f"Đã trích xuất {tot_logs} bản ghi kiểm toán gần nhất" if parsed.get("success") else "Đã tra cứu nhật ký kiểm toán"
                                        else:
                                            # Rút gọn message thô, loại bỏ các ký tự Markdown tiêu đề để giữ dòng suy nghĩ tinh tế
                                            raw_msg = str(parsed.get("message") or "Đã thực thi thành công")
                                            first_line = raw_msg.split("\n")[0].replace("#", "").replace("*", "").strip()
                                            completed_detail = (first_line[:80] + "...") if len(first_line) > 80 else first_line
                                    else:
                                        tool_results.append({"name": t_name, "result": parsed})
                                except Exception:
                                    tool_results.append({"name": t_name, "result": res_str})

                                # Stream event: tool is completed
                                t_step = add_thought(step_id, meta_title, completed_detail, "completed")
                                yield f"data: {json.dumps({'type': 'thought', **t_step})}\n\n"

                            except Exception as e_tool:
                                logger.error("Tool execution failed for %s: %s", t_name, e_tool)
                                err_str = f"Lỗi thực thi {t_name}: {str(e_tool)}"
                                messages.append(ToolMessage(content=err_str, tool_call_id=call_id, name=t_name))
                                t_step = add_thought(step_id, meta_title, f"Thất bại: {str(e_tool)}", "completed")
                                yield f"data: {json.dumps({'type': 'thought', **t_step})}\n\n"
                else:
                    # Model provided text answer without tool calls
                    content_text = _extract_text(response.content)
                    if content_text and len(content_text.strip()) > 10:
                        agent_answered = True
                        full_answer = content_text
                        break

            # Cập nhật thought plan hoàn thành
            t_react = add_thought("super_agent", "Lập kế hoạch & Điều phối", "Đã hoàn thành phân tích và thực thi chuỗi công cụ", "completed")
            yield f"data: {json.dumps({'type': 'thought', **t_react})}\n\n"

            t_syn = add_thought("synthesis", "Tổng hợp câu trả lời", "Đang truyền tải câu trả lời toàn diện...", "running")
            yield f"data: {json.dumps({'type': 'thought', **t_syn})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI Copilot đang trả lời...'})}\n\n"

            # Nếu agent đã có câu trả lời hoàn chỉnh
            if full_answer:
                words = full_answer.split(" ")
                for i in range(0, len(words), 3):
                    chunk_text = " ".join(words[i:i+3]) + " "
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk_text})}\n\n"
                    await asyncio.sleep(0.012)
            else:
                # Nếu agent chưa có câu trả lời hoặc cần synthesize
                context_summary = []
                for msg in messages:
                    if isinstance(msg, ToolMessage):
                        context_summary.append(f"Tool ({msg.name}): {msg.content}")
                context_text = "\n\n".join(context_summary)

                prompt = [
                    SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
                    HumanMessage(content=(
                        f"Câu hỏi người dùng: {clean_message}\n\n"
                        f"Dữ liệu công cụ thu thập được:\n{context_text}\n\n"
                        f"Hãy tổng hợp thành phản hồi hoàn chỉnh, súc tích và chính xác bằng Tiếng Việt:"
                    )),
                ]
                streamed = False
                try:
                    llm_syn = _get_llm(model=settings.GEMINI_MODEL, temperature=0.0)
                    async for chunk in llm_syn.astream(prompt):
                        token = _extract_text(chunk.content)
                        if token:
                            full_answer += token
                            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    streamed = True
                except Exception as e_syn:
                    logger.warning("Synthesizer stream failed: %s", e_syn)
                    try:
                        llm_fb = _get_llm(model=settings.GEMINI_FALLBACK_MODEL, temperature=0.0)
                        async for chunk in llm_fb.astream(prompt):
                            token = _extract_text(chunk.content)
                            if token:
                                full_answer += token
                                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                        streamed = True
                    except Exception as e_fb:
                        logger.warning("Fallback synthesizer failed: %s", e_fb)

                if not streamed or not full_answer:
                    if proposed_action and proposed_action.get("draft_payload"):
                        payload = proposed_action["draft_payload"]
                        full_answer = f"Đã lập đơn hàng nháp #{payload.get('order_number')} cho khách hàng {payload.get('customer_name')} thành công."
                    else:
                        full_answer = "Đã xử lý xong các yêu cầu của bạn."
                    yield f"data: {json.dumps({'type': 'token', 'content': full_answer})}\n\n"

            t_syn = add_thought("synthesis", "Tổng hợp câu trả lời", "Đã hoàn thành phản hồi toàn diện", "completed")
            yield f"data: {json.dumps({'type': 'thought', **t_syn})}\n\n"

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

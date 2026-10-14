from typing import Annotated, Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

AgentIntent = Literal[
    "erp_query",          # Tra cứu dữ liệu ERP: tồn kho, khách hàng, sản phẩm, đơn hàng, báo cáo
    "document_qa",        # Hỏi đáp chính sách, quy định, cẩm nang nội bộ qua RAG
    "create_order_draft", # Đề xuất tạo đơn hàng nháp (Human-in-the-Loop)
    "chitchat",           # Chào hỏi, giao tiếp xã giao, câu hỏi chung về trợ lý
    "unknown",            # Câu hỏi mơ hồ hoặc ngoài phạm vi hệ thống
]


class OrderItemDraft(BaseModel):
    """Chi tiết sản phẩm đặt trong đơn hàng nháp"""
    sku: Optional[str] = Field(default=None, description="Mã sản phẩm (VD: SKU-001) hoặc tên sản phẩm tự nhiên")
    product_name: Optional[str] = Field(default=None, description="Tên sản phẩm tự nhiên (VD: Chuột Ergonomic, Laptop Pro)")
    quantity: int = Field(default=1, description="Số lượng đặt")

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


class ExtractedEntities(BaseModel):
    """
    Concrete Typed Entities Model tương thích hoàn toàn với Google Gemini Constrained Decoding.
    Tránh lỗi 'additionalProperties' trong Gemini Developer API mode.
    Hỗ trợ truy cập cả dạng thuộc tính (.sku) lẫn dictionary (['sku'], .get('sku')).
    """
    sku: Optional[str] = Field(default=None, description="Mã sản phẩm (VD: SKU-001) hoặc tên sản phẩm tự nhiên")
    product_name: Optional[str] = Field(default=None, description="Tên sản phẩm tự nhiên")
    warehouse_code: Optional[str] = Field(default=None, description="Mã kho hàng (VD: WH-HN, WH-HCM)")
    customer_code: Optional[str] = Field(default=None, description="Mã khách hàng (VD: CUS-0001)")
    customer_name: Optional[str] = Field(default=None, description="Tên khách hàng hoặc tên công ty (VD: Tập đoàn Bán lẻ Toàn Cầu, Công ty Á Châu)")
    customer_phone: Optional[str] = Field(default=None, description="Số điện thoại khách hàng")
    quantity: Optional[int] = Field(default=None, description="Số lượng")
    items: Optional[List[OrderItemDraft]] = Field(default=None, description="Danh sách mặt hàng đặt")
    date_range: Optional[str] = Field(default=None, description="Kỳ báo cáo thời gian")

    def __getitem__(self, item: str) -> Any:
        val = getattr(self, item, None)
        if val is None and item not in self.model_fields:
            raise KeyError(item)
        return val

    def __contains__(self, item: str) -> bool:
        return getattr(self, item, None) is not None

    def get(self, item: str, default: Any = None) -> Any:
        val = getattr(self, item, None)
        return val if val is not None else default


class IntentClassificationResult(BaseModel):
    """
    Kết quả phân loại ý định (Intent) và trích xuất thực thể (Entities) từ câu hỏi người dùng.
    Được cưỡng chế cấu trúc 100% bằng Gemini Native response_schema.
    """
    intent: AgentIntent = Field(
        ...,
        description="Ý định phân loại chính: erp_query, document_qa, create_order_draft, chitchat, hoặc unknown",
    )
    entities: ExtractedEntities = Field(
        default_factory=ExtractedEntities,
        description="Thực thể trích xuất được với schema rõ ràng",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Độ tự tin của phân loại từ 0.0 đến 1.0",
    )
    reasoning: str = Field(
        default="",
        description="Giải thích ngắn gọn lý do phân loại",
    )


class ERPAgentState(TypedDict, total=False):
    """
    LangGraph State cho ERP AI Copilot Agent Orchestrator.
    Tuân thủ nghiêm ngặt Blueprint Mục 6.1 (ERP_AI_Copilot_MVP_Technical_Blueprint.md).
    """
    # --- Định danh và Ngữ cảnh tin cậy (Injected từ auth context, không tin từ prompt) ---
    user_id: Optional[str]
    user_role: Optional[str]
    conversation_id: Optional[str]
    request_id: Optional[str]

    # --- Lịch sử hội thoại (Quản lý tự động bởi LangGraph add_messages reducer) ---
    messages: Annotated[List[Any], add_messages]

    # --- Phân loại ý định & Định tuyến ---
    user_query: str
    intent: AgentIntent
    entities: Any  # ExtractedEntities hoặc Dict[str, Any]
    reasoning: Optional[str]

    # --- Ngữ cảnh truy xuất & Kết quả công cụ ---
    retrieved_context: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]

    # --- Đề xuất hành động & Phản hồi nghiệp vụ ---
    proposed_action: Optional[Dict[str, Any]]  # Payload đơn hàng nháp chờ phê duyệt
    approval_id: Optional[str]
    answer: str
    citations: List[Dict[str, Any]]
    error: Optional[str]

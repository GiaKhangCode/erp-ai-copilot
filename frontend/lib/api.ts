/**
 * Centralized API Client Layer kết nối FastAPI Backend
 * Hệ thống ERP AI Copilot (MVP)
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

interface RequestOptions extends RequestInit {
  token?: string;
}

// ----------------------------------------------------
// User & Auth Interfaces
// ----------------------------------------------------
export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  phone?: string | null;
  department?: string | null;
  job_title?: string | null;
  role: string;
  roles?: string[];
  permissions?: string[];
  is_active: boolean;
  is_superuser?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

// ----------------------------------------------------
// ERP Domain Interfaces
// ----------------------------------------------------
export interface CustomerItem {
  id: string;
  code: string;
  name: string;
  email?: string | null;
  status: string;
  credit_limit?: number;
  current_debt?: number;
  phone?: string | null;
  address?: string | null;
}

export interface ProductItem {
  id: string;
  sku: string;
  name: string;
  unit_price: number;
  is_active: boolean;
}

export interface InventoryItem {
  product_sku: string;
  product_name: string;
  warehouse_code: string;
  warehouse_name: string;
  quantity_on_hand: number;
  quantity_reserved: number;
  quantity_available: number;
}

export interface OrderItemDetail {
  id: string;
  product_id: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  catalog_price?: number;
  allocated_quantity?: number;
  backorder_quantity?: number;
  line_total: number;
}

export interface SalesOrderItem {
  id: string;
  order_number: string;
  customer_po_number?: string;
  customer_id: string;
  customer_name?: string;
  customer_code?: string;
  status: "draft" | "pending_approval" | "confirmed" | "cancelled" | "delivered" | string;
  total_amount: number;
  created_at: string;
  items: OrderItemDetail[];
}

export interface StockAdjustmentItem {
  id: string;
  sku: string;
  warehouse_code: string;
  delta_quantity: number;
  quantity_before: number;
  quantity_after: number;
  reason: string;
  adjusted_by: string;
  created_at: string;
}

export interface OrderDraftCreatePayload {
  customer_code: string;
  customer_po_number?: string;
  items: Array<{
    sku: string;
    quantity: number;
    unit_price?: number;
  }>;
  requested_delivery_date?: string;
  source_document_id?: string;
}

export interface OrderDraftUpdatePayload {
  customer_code?: string;
  customer_po_number?: string;
  items: Array<{
    sku: string;
    quantity: number;
    unit_price?: number;
  }>;
  requested_delivery_date?: string;
}

export interface RevenueReportBreakdown {
  period: string;
  order_count: number;
  total_revenue: number;
}

export interface RevenueReportData {
  metric_id: string;
  period?: string;
  total_revenue: number;
  total_orders: number;
  breakdown: RevenueReportBreakdown[];
}

// ----------------------------------------------------
// Phase 3: Executive Reporting Interfaces
// ----------------------------------------------------
export interface SalesLeaderboardItem {
  sales_id: string;
  sales_name: string;
  sales_email: string;
  total_revenue: number;
  total_orders: number;
  aov: number;
  rank: number;
}

export interface SalesLeaderboardResponse {
  metric_id: string;
  period: string;
  total_sales_reps: number;
  items: SalesLeaderboardItem[];
}

export interface FinancialProfitabilityResponse {
  metric_id: string;
  period: string;
  total_revenue: number;
  total_cogs: number;
  gross_profit: number;
  gross_margin_percent: number;
  total_orders: number;
}

export interface DebtAgingBucket {
  bucket: string;
  label: string;
  amount: number;
  customer_count: number;
}

export interface TopDebtorItem {
  customer_id: string;
  customer_code: string;
  customer_name: string;
  credit_limit: number;
  current_debt: number;
  credit_utilization_rate: number;
  is_over_limit: boolean;
}

export interface DebtAgingReportResponse {
  metric_id: string;
  total_debt: number;
  total_credit_limit: number;
  overall_utilization_rate: number;
  over_limit_customers_count: number;
  buckets: DebtAgingBucket[];
  top_debtors: TopDebtorItem[];
}

// ----------------------------------------------------
// RAG & Knowledge Documents Interfaces
// ----------------------------------------------------
export interface RagDocumentItem {
  id: string;
  filename: string;
  mime_type?: string;
  storage_key?: string;
  checksum?: string;
  owner_id?: string;
  access_scope: string;
  status: string;
  version?: number;
  created_at?: string;
  chunk_count?: number;
  download_url?: string;
}

export interface DocumentChunkDetail {
  id: string;
  chunk_index: number;
  content: string;
  metadata_?: any;
}

export interface DocumentDetailItem extends RagDocumentItem {
  chunks: DocumentChunkDetail[];
}

export interface RagDocumentListResponse {
  items: RagDocumentItem[];
  total: number;
  skip: number;
  limit: number;
}

// ----------------------------------------------------
// Document AI & Ingestion Interfaces
// ----------------------------------------------------
export interface OrderIngestionResult {
  source_type: string;
  source_identifier: string;
  status: string;
  extracted_data?: any;
  resolved_customer_id?: string;
  resolved_customer_code?: string;
  resolved_customer_name?: string;
  resolved_items?: Array<{
    sku: string;
    product_name: string;
    quantity: number;
    db_unit_price: number;
    line_total: number;
    stock_sufficient: boolean;
    price_discrepancy: boolean;
  }>;
  total_amount?: number;
  warnings?: string[];
  draft_order_id?: string;
  approval_request_id?: string;
}

// ----------------------------------------------------
// Chat & AI Assistant Interfaces
// ----------------------------------------------------
export interface Citation {
  filename: string;
  page_number?: number;
  chunk_index?: number;
  quote?: string;
}

export interface ProposedAction {
  action_type: string;
  customer_name?: string;
  customer_code?: string;
  order_type?: string;
  total_amount?: number;
  items?: Array<{
    product_sku?: string;
    sku?: string;
    product_name?: string;
    quantity: number;
    unit_price?: number;
  }>;
  notes?: string;
}

export interface ThoughtStep {
  step: string;
  title: string;
  detail?: string;
  status: "running" | "completed";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at?: string;
  intent?: string;
  citations?: Citation[];
  proposed_action?: ProposedAction | null;
  requires_confirmation?: boolean;
  thought_steps?: ThoughtStep[];
}

export interface ConversationItem {
  id: string;
  title: string;
  created_at: string;
  message_count: number;
}

export interface ChatResponse {
  conversation_id: string;
  run_id: string;
  status: string;
  answer: string;
  intent?: string;
  citations?: Citation[];
  proposed_action?: ProposedAction | null;
  requires_confirmation?: boolean;
  thought_steps?: ThoughtStep[];
}

// ----------------------------------------------------
// Approval Inbox Interfaces (HITL)
// ----------------------------------------------------
export interface ApprovalPayloadItem {
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  stock_sufficient?: boolean;
  price_discrepancy?: boolean;
}

export interface ApprovalPayload {
  order_id?: string;
  order_number?: string;
  customer_code?: string;
  customer_name?: string;
  total_amount?: number;
  source_type?: string;
  source_identifier?: string;
  warnings_count?: number;
  items?: ApprovalPayloadItem[];
  requested_delivery_date?: string;
  ai_notes?: string;
  [key: string]: any;
}

export interface ApprovalItem {
  id: string;
  action_type: string;
  target_id: string;
  payload: ApprovalPayload;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  approved_by?: string | null;
  created_at: string;
}

export interface ApprovalActionResponse {
  message: string;
  approval_id: string;
  order_id: string;
  status: string;
  order_number?: string;
  reason?: string;
}

// ----------------------------------------------------
// Core API Client Logic
// ----------------------------------------------------
export async function getAuthToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("erp_access_token");
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { token, headers = {}, ...rest } = options;

  let authToken = token;
  if (!authToken && typeof window !== "undefined") {
    authToken = (await getAuthToken()) || undefined;
  }

  const defaultHeaders: Record<string, string> = {
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };

  if (!(rest.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  const url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  const response = await fetch(url, {
    headers: {
      ...defaultHeaders,
      ...(headers as Record<string, string>),
    },
    ...rest,
  });

  if (!response.ok) {
    let errorDetail = `Lỗi hệ thống (${response.status})`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      const errText = await response.text();
      if (errText) errorDetail = errText;
    }
    throw new Error(errorDetail);
  }

  return response.json() as Promise<T>;
}

// ----------------------------------------------------
// Auth Service Endpoints
// ----------------------------------------------------
export async function loginApi(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || err.detail || "Đăng nhập thất bại");
  }
  const data: TokenResponse = await res.json();
  if (typeof window !== "undefined") {
    localStorage.setItem("erp_access_token", data.access_token);
    localStorage.setItem("erp_user", JSON.stringify(data.user));
  }
  return data;
}

export async function fetchMeApi(): Promise<UserProfile> {
  return apiClient<UserProfile>("/auth/me");
}

// ----------------------------------------------------
// ERP Domain APIs
// ----------------------------------------------------

export async function fetchRevenueReport(
  year?: number,
  month?: number
): Promise<RevenueReportData> {
  const params = new URLSearchParams();
  if (year) params.append("year", year.toString());
  if (month) params.append("month", month.toString());
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiClient<RevenueReportData>(`/reporting/revenue${query}`);
}

export async function fetchSalesLeaderboardApi(
  year?: number,
  month?: number
): Promise<SalesLeaderboardResponse> {
  const params = new URLSearchParams();
  if (year) params.append("year", year.toString());
  if (month) params.append("month", month.toString());
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiClient<SalesLeaderboardResponse>(`/reporting/sales-leaderboard${query}`);
}

export async function fetchFinancialProfitabilityApi(
  year?: number,
  month?: number
): Promise<FinancialProfitabilityResponse> {
  const params = new URLSearchParams();
  if (year) params.append("year", year.toString());
  if (month) params.append("month", month.toString());
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiClient<FinancialProfitabilityResponse>(`/reporting/profitability${query}`);
}

export async function fetchDebtAgingApi(): Promise<DebtAgingReportResponse> {
  return apiClient<DebtAgingReportResponse>("/reporting/debt-aging");
}

export async function fetchOrders(params?: {
  customer_code?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<SalesOrderItem[]> {
  const q = new URLSearchParams();
  if (params?.customer_code) q.append("customer_code", params.customer_code);
  if (params?.status) q.append("status", params.status);
  if (params?.limit) q.append("limit", params.limit.toString());
  if (params?.offset) q.append("offset", params.offset.toString());
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<SalesOrderItem[]>(`/sales-orders${queryString}`);
}

export async function fetchOrderDetail(orderId: string): Promise<SalesOrderItem> {
  return apiClient<SalesOrderItem>(`/sales-orders/${orderId}`);
}

export async function createOrderDraftApi(
  payload: OrderDraftCreatePayload,
  idempotencyKey?: string
): Promise<SalesOrderItem> {
  return apiClient<SalesOrderItem>("/sales-orders/drafts", {
    method: "POST",
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
    body: JSON.stringify(payload),
  });
}

export async function updateOrderDraftApi(
  orderId: string,
  payload: OrderDraftUpdatePayload
): Promise<SalesOrderItem> {
  return apiClient<SalesOrderItem>(`/sales-orders/${orderId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function deleteOrderDraftApi(
  orderId: string
): Promise<{ message: string; order_id: string }> {
  return apiClient<{ message: string; order_id: string }>(`/sales-orders/${orderId}`, {
    method: "DELETE",
  });
}

export async function fetchInventory(params?: {
  sku?: string;
  warehouse_code?: string;
}): Promise<InventoryItem[]> {
  const q = new URLSearchParams();
  if (params?.sku) q.append("sku", params.sku);
  if (params?.warehouse_code) q.append("warehouse_code", params.warehouse_code);
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<InventoryItem[]>(`/inventory${queryString}`);
}

export async function adjustInventoryApi(payload: {
  sku: string;
  warehouse_code: string;
  delta_quantity: number;
  reason: string;
}): Promise<StockAdjustmentItem> {
  return apiClient<StockAdjustmentItem>("/inventory/adjust", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchStockAdjustmentsApi(params?: {
  sku?: string;
  warehouse_code?: string;
  limit?: number;
  offset?: number;
}): Promise<StockAdjustmentItem[]> {
  const q = new URLSearchParams();
  if (params?.sku) q.append("sku", params.sku);
  if (params?.warehouse_code) q.append("warehouse_code", params.warehouse_code);
  if (params?.limit) q.append("limit", params.limit.toString());
  if (params?.offset) q.append("offset", params.offset.toString());
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<StockAdjustmentItem[]>(`/inventory/adjustments${queryString}`);
}

export async function deliverOrderApi(orderId: string): Promise<SalesOrderItem> {
  return apiClient<SalesOrderItem>(`/orders/${orderId}/deliver`, {
    method: "POST",
  });
}

export async function fetchProducts(params?: {
  limit?: number;
  offset?: number;
  is_active?: boolean;
}): Promise<ProductItem[]> {
  const q = new URLSearchParams();
  if (params?.limit) q.append("limit", params.limit.toString());
  if (params?.offset) q.append("offset", params.offset.toString());
  if (params?.is_active !== undefined) q.append("is_active", params.is_active.toString());
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<ProductItem[]>(`/products${queryString}`);
}

export async function fetchCustomers(params?: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<CustomerItem[]> {
  const q = new URLSearchParams();
  if (params?.limit) q.append("limit", params.limit.toString());
  if (params?.offset) q.append("offset", params.offset.toString());
  if (params?.status) q.append("status", params.status);
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<CustomerItem[]>(`/customers${queryString}`);
}

// ----------------------------------------------------
// Document AI & Ingestion APIs
// ----------------------------------------------------

export async function uploadOrderDocumentApi(file: File): Promise<OrderIngestionResult> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<OrderIngestionResult>("/orders/ingest-document", {
    method: "POST",
    body: formData,
  });
}

export async function uploadOrderEmlApi(file: File): Promise<OrderIngestionResult> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<OrderIngestionResult>("/orders/ingest-email", {
    method: "POST",
    body: formData,
  });
}

export async function uploadOrderTextApi(
  text: string,
  sourceIdentifier?: string
): Promise<OrderIngestionResult> {
  return apiClient<OrderIngestionResult>("/orders/ingest-text", {
    method: "POST",
    body: JSON.stringify({
      text,
      source_identifier: sourceIdentifier || "manual_text_input",
    }),
  });
}

// ----------------------------------------------------
// RAG Documents APIs
// ----------------------------------------------------

export async function fetchDocumentsApi(params?: {
  skip?: number;
  limit?: number;
  status?: string;
  access_scope?: string;
}): Promise<RagDocumentListResponse> {
  const q = new URLSearchParams();
  if (params?.skip !== undefined) q.append("skip", params.skip.toString());
  if (params?.limit !== undefined) q.append("limit", params.limit.toString());
  if (params?.status) q.append("status", params.status);
  if (params?.access_scope) q.append("access_scope", params.access_scope);
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<RagDocumentListResponse>(`/documents${queryString}`);
}

export async function uploadRagDocumentApi(
  file: File,
  accessScope: string = "internal"
): Promise<RagDocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("access_scope", accessScope);
  return apiClient<RagDocumentItem>("/documents/upload", {
    method: "POST",
    body: formData,
  });
}

export async function fetchDocumentDetailApi(documentId: string): Promise<DocumentDetailItem> {
  return apiClient<DocumentDetailItem>(`/documents/${documentId}`);
}

export async function fetchDocumentDownloadUrlApi(
  documentId: string,
  expiresIn: number = 3600
): Promise<{ download_url: string; expires_in: number }> {
  return apiClient<{ download_url: string; expires_in: number }>(
    `/documents/${documentId}/download-url?expires_in=${expiresIn}`
  );
}

export async function deleteDocumentApi(documentId: string): Promise<{ message: string }> {
  return apiClient<{ message: string }>(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function fetchDocumentBlobApi(
  documentId: string,
  inline: boolean = true
): Promise<{ blob: Blob; url: string; mimeType: string }> {
  const token = await getAuthToken();
  const res = await fetch(`${API_BASE_URL}/documents/${documentId}/file?inline=${inline}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Không thể tải tệp tin gốc: HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const mimeType = res.headers.get("content-type") || "application/octet-stream";
  return { blob, url, mimeType };
}

// ----------------------------------------------------
// Chat & AI Helper APIs
// ----------------------------------------------------

export interface StreamCallbacks {
  onStart?: (conversationId: string) => void;
  onIntent?: (intent: string) => void;
  onThought?: (step: ThoughtStep) => void;
  onStatus?: (statusMessage: string) => void;
  onToken?: (token: string) => void;
  onDone?: (data: {
    answer: string;
    citations?: Citation[];
    proposed_action?: ProposedAction | null;
    thought_steps?: ThoughtStep[];
    conversation_id?: string;
  }) => void;
  onError?: (error: string) => void;
}

export async function sendChatMessageStream(
  message: string,
  conversationId: string | null | undefined,
  callbacks: StreamCallbacks
): Promise<void> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  try {
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        message,
        conversation_id: conversationId || undefined,
      }),
    });

    if (!response.ok) {
      const errJson = await response.json().catch(() => ({}));
      throw new Error(errJson.detail || `Server trả về mã lỗi: ${response.status}`);
    }

    if (!response.body) {
      throw new Error("Trình duyệt không hỗ trợ ReadableStream.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;

        const dataStr = trimmed.replace(/^data:\s*/, "");
        try {
          const payload = JSON.parse(dataStr);
          if (payload.type === "start") {
            callbacks.onStart?.(payload.conversation_id);
          } else if (payload.type === "intent") {
            callbacks.onIntent?.(payload.intent);
          } else if (payload.type === "thought") {
            callbacks.onThought?.(payload);
          } else if (payload.type === "status") {
            callbacks.onStatus?.(payload.message);
          } else if (payload.type === "token") {
            callbacks.onToken?.(payload.content);
          } else if (payload.type === "done") {
            callbacks.onDone?.(payload);
          }
        } catch (parseErr) {
          console.warn("Lỗi parse SSE:", parseErr, dataStr);
        }
      }
    }
  } catch (err: any) {
    callbacks.onError?.(err.message || "Lỗi kết nối streaming AI Copilot");
    throw err;
  }
}

export async function sendChatMessage(
  message: string,
  conversationId?: string | null
): Promise<ChatResponse> {
  return apiClient<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
    }),
  });
}

export async function fetchConversations(): Promise<ConversationItem[]> {
  return apiClient<ConversationItem[]>("/conversations", {
    method: "GET",
  });
}

export async function fetchConversationDetail(conversationId: string): Promise<{
  id: string;
  title: string;
  created_at: string;
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
  }>;
}> {
  return apiClient(`/conversations/${conversationId}`, {
    method: "GET",
  });
}

export async function deleteConversationApi(conversationId: string): Promise<void> {
  return apiClient(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

// ----------------------------------------------------
// Approval Inbox APIs (Human-In-The-Loop)
// ----------------------------------------------------

export async function fetchApprovalsApi(statusFilter?: string): Promise<ApprovalItem[]> {
  const query = statusFilter && statusFilter !== "all" ? `?status=${encodeURIComponent(statusFilter)}` : "";
  return apiClient<ApprovalItem[]>(`/approvals${query}`, {
    method: "GET",
  });
}

export async function fetchApprovalDetailApi(approvalId: string): Promise<ApprovalItem> {
  return apiClient<ApprovalItem>(`/approvals/${approvalId}`, {
    method: "GET",
  });
}

export async function approveRequestApi(approvalId: string): Promise<ApprovalActionResponse> {
  return apiClient<ApprovalActionResponse>(`/approvals/${approvalId}/approve`, {
    method: "POST",
  });
}

export async function rejectRequestApi(
  approvalId: string,
  reason?: string
): Promise<ApprovalActionResponse> {
  return apiClient<ApprovalActionResponse>(`/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || "Từ chối theo quyết định người duyệt" }),
  });
}

// ----------------------------------------------------
// Admin User & Role Management APIs
// ----------------------------------------------------

export interface AdminRoleBrief {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  created_at: string;
}

export interface AdminPermissionItem {
  id: string;
  code: string;
  module: string;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface AdminPermissionGroup {
  module: string;
  module_name: string;
  permissions: AdminPermissionItem[];
}

export interface AdminRoleDetail {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  is_system: boolean;
  user_count: number;
  permissions: AdminPermissionItem[];
  created_at: string;
}

export interface AdminUserItem {
  id: string;
  email: string;
  full_name: string;
  phone?: string | null;
  department?: string | null;
  job_title?: string | null;
  role: string;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at?: string | null;
  created_at: string;
  updated_at?: string | null;
  roles: AdminRoleBrief[];
  permissions: string[];
}

export interface AdminUserListResponse {
  items: AdminUserItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CreateAdminUserPayload {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
  department?: string;
  job_title?: string;
  role_ids?: string[];
  is_active?: boolean;
  is_superuser?: boolean;
}

export interface UpdateAdminUserPayload {
  full_name?: string;
  phone?: string;
  department?: string;
  job_title?: string;
  role_ids?: string[];
  is_active?: boolean;
}

export async function fetchAdminUsersApi(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  role?: string;
  department?: string;
  is_active?: boolean;
}): Promise<AdminUserListResponse> {
  const q = new URLSearchParams();
  if (params?.page) q.append("page", params.page.toString());
  if (params?.page_size) q.append("page_size", params.page_size.toString());
  if (params?.search) q.append("search", params.search);
  if (params?.role && params.role !== "all") q.append("role", params.role);
  if (params?.department && params.department !== "all") q.append("department", params.department);
  if (params?.is_active !== undefined) q.append("is_active", params.is_active.toString());
  const query = q.toString() ? `?${q.toString()}` : "";
  return apiClient<AdminUserListResponse>(`/admin/users${query}`);
}

export async function createAdminUserApi(payload: CreateAdminUserPayload): Promise<AdminUserItem> {
  return apiClient<AdminUserItem>("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAdminUserApi(
  userId: string,
  payload: UpdateAdminUserPayload
): Promise<AdminUserItem> {
  return apiClient<AdminUserItem>(`/admin/users/${userId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function toggleAdminUserStatusApi(
  userId: string,
  isActive: boolean
): Promise<AdminUserItem> {
  return apiClient<AdminUserItem>(`/admin/users/${userId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
}

export async function resetAdminUserPasswordApi(
  userId: string,
  newPassword: string
): Promise<{ message: string }> {
  return apiClient<{ message: string }>(`/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export async function deleteAdminUserApi(userId: string): Promise<{ message: string }> {
  return apiClient<{ message: string }>(`/admin/users/${userId}`, {
    method: "DELETE",
  });
}

export async function fetchAdminRolesApi(): Promise<AdminRoleDetail[]> {
  return apiClient<AdminRoleDetail[]>("/admin/roles");
}

export async function createAdminRoleApi(payload: {
  code: string;
  name: string;
  description?: string;
  permission_ids?: string[];
}): Promise<AdminRoleDetail> {
  return apiClient<AdminRoleDetail>("/admin/roles", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateAdminRoleApi(
  roleId: string,
  payload: { name?: string; description?: string }
): Promise<AdminRoleDetail> {
  return apiClient<AdminRoleDetail>(`/admin/roles/${roleId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function updateAdminRolePermissionsApi(
  roleId: string,
  permissionIds: string[]
): Promise<AdminRoleDetail> {
  return apiClient<AdminRoleDetail>(`/admin/roles/${roleId}/permissions`, {
    method: "PUT",
    body: JSON.stringify({ permission_ids: permissionIds }),
  });
}

export async function deleteAdminRoleApi(roleId: string): Promise<{ message: string }> {
  return apiClient<{ message: string }>(`/admin/roles/${roleId}`, {
    method: "DELETE",
  });
}

export async function fetchAdminPermissionsApi(): Promise<AdminPermissionGroup[]> {
  return apiClient<AdminPermissionGroup[]>("/admin/permissions");
}

// ----------------------------------------------------
// Phase 2: Quotation PDF & Customer Credit Check
// ----------------------------------------------------
export interface QuotationSummary {
  order_id: string;
  order_number: string;
  customer_id: string;
  customer_name: string;
  customer_code: string;
  total_amount: number;
  status: string;
  created_at: string;
  filename: string;
  pdf_url: string;
  items: Array<{
    sku: string;
    name: string;
    quantity: number;
    unit_price: number;
    line_total: number;
  }>;
}

export interface CustomerCreditInfo {
  customer_id: string;
  customer_code: string;
  customer_name: string;
  credit_limit: number;
  current_debt: number;
  available_credit: number;
  credit_utilization_rate: number;
  is_exceeded: boolean;
  currency: string;
}

export async function fetchOrderQuotationSummaryApi(orderId: string): Promise<QuotationSummary> {
  return apiClient<QuotationSummary>(`/orders/${orderId}/quotation/summary`);
}

export async function fetchCustomerCreditCheckApi(
  customerIdentifier: string,
  additionalAmount: number = 0
): Promise<CustomerCreditInfo> {
  return apiClient<CustomerCreditInfo>(
    `/customers/${encodeURIComponent(customerIdentifier)}/credit-check?additional_amount=${additionalAmount}`
  );
}

export async function fetchOrderQuotationBlobApi(orderId: string): Promise<{ blob: Blob; url: string; filename: string }> {
  const token = typeof window !== "undefined" ? localStorage.getItem("erp_access_token") : null;
  const res = await fetch(`${API_BASE_URL}/orders/${orderId}/quotation/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.message || "Không thể tải file PDF báo giá.");
  }
  const filename = res.headers.get("x-filename") || `Phieu_Xac_Nhan_${orderId}.pdf`;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  return { blob, url, filename };
}

// ----------------------------------------------------
// Audit Trail & Compliance Interfaces & APIs (Giai đoạn 4)
// ----------------------------------------------------
export interface AuditLogItem {
  id: string;
  actor_id: string;
  actor_email: string;
  actor_role: string;
  action: string;
  resource_type: string;
  resource_id: string;
  result: string;
  ip_address?: string | null;
  details?: Record<string, any> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
}

export interface AuditLogStatsResponse {
  total_logs: number;
  by_resource: Array<{ resource_type: string; count: number }>;
  by_action: Array<{ action: string; count: number }>;
  top_users: Array<{ email: string; count: number }>;
}

export interface AuditLogFilterParams {
  page?: number;
  limit?: number;
  actor_email?: string;
  action?: string;
  resource_type?: string;
  from_date?: string;
  to_date?: string;
}

export async function fetchAuditLogsApi(params?: AuditLogFilterParams): Promise<AuditLogListResponse> {
  const query = new URLSearchParams();
  if (params?.page) query.set("page", params.page.toString());
  if (params?.limit) query.set("limit", params.limit.toString());
  if (params?.actor_email) query.set("actor_email", params.actor_email);
  if (params?.action) query.set("action", params.action);
  if (params?.resource_type) query.set("resource_type", params.resource_type);
  if (params?.from_date) query.set("from_date", params.from_date);
  if (params?.to_date) query.set("to_date", params.to_date);

  const qs = query.toString();
  return apiClient<AuditLogListResponse>(`/admin/audit-logs${qs ? `?${qs}` : ""}`);
}

export async function fetchAuditLogStatsApi(): Promise<AuditLogStatsResponse> {
  return apiClient<AuditLogStatsResponse>("/admin/audit-logs/stats");
}

// ----------------------------------------------------
// Core ERP CRUD Interfaces & APIs (Customer, Product, Order)
// ----------------------------------------------------

export interface CustomerCreateInput {
  code: string;
  name: string;
  email?: string;
  phone?: string;
  address?: string;
  credit_limit?: number;
  status?: string;
}

export interface CustomerUpdateInput {
  name?: string;
  email?: string;
  phone?: string;
  address?: string;
  credit_limit?: number;
  status?: string;
}

export async function createCustomerApi(data: CustomerCreateInput): Promise<CustomerItem> {
  return apiClient<CustomerItem>("/customers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCustomerApi(customerId: string, data: CustomerUpdateInput): Promise<CustomerItem> {
  return apiClient<CustomerItem>(`/customers/${customerId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteCustomerApi(customerId: string): Promise<CustomerItem> {
  return apiClient<CustomerItem>(`/customers/${customerId}`, {
    method: "DELETE",
  });
}

export interface ProductCreateInput {
  sku: string;
  name: string;
  unit_price: number;
  cost_price?: number;
  is_active?: boolean;
}

export interface ProductUpdateInput {
  name?: string;
  unit_price?: number;
  cost_price?: number;
  is_active?: boolean;
}

export async function createProductApi(data: ProductCreateInput): Promise<ProductItem> {
  return apiClient<ProductItem>("/products", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateProductApi(productId: string, data: ProductUpdateInput): Promise<ProductItem> {
  return apiClient<ProductItem>(`/products/${productId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteProductApi(productId: string): Promise<ProductItem> {
  return apiClient<ProductItem>(`/products/${productId}`, {
    method: "DELETE",
  });
}

export async function cancelSalesOrderApi(orderId: string, reason?: string): Promise<SalesOrderItem> {
  return apiClient<SalesOrderItem>(`/orders/${orderId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || "Người dùng yêu cầu hủy đơn" }),
  });
}

// ----------------------------------------------------
// Payments & AR Debt Collection API
// ----------------------------------------------------
export interface PaymentItem {
  id: string;
  payment_number: string;
  customer_id: string;
  customer_name?: string | null;
  customer_code?: string | null;
  order_id?: string | null;
  order_number?: string | null;
  amount: number;
  payment_method: string;
  reference_code?: string | null;
  note?: string | null;
  received_by: string;
  receiver_name?: string | null;
  created_at: string;
}

export interface PaymentCreateInput {
  customer_id: string;
  order_id?: string;
  amount: number;
  payment_method?: string;
  reference_code?: string;
  note?: string;
}

export async function createPaymentApi(data: PaymentCreateInput): Promise<PaymentItem> {
  return apiClient<PaymentItem>("/payments", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchPaymentsApi(params?: {
  customer_id?: string;
  order_id?: string;
  limit?: number;
  offset?: number;
}): Promise<PaymentItem[]> {
  const query = new URLSearchParams();
  if (params?.customer_id) query.append("customer_id", params.customer_id);
  if (params?.order_id) query.append("order_id", params.order_id);
  if (params?.limit) query.append("limit", params.limit.toString());
  if (params?.offset) query.append("offset", params.offset.toString());

  const qs = query.toString();
  return apiClient<PaymentItem[]>(`/payments${qs ? `?${qs}` : ""}`);
}

// ----------------------------------------------------
// Stock Transfer API (Điều chuyển kho nội bộ)
// ----------------------------------------------------
export interface StockTransferItem {
  id: string;
  transfer_number: string;
  sku: string;
  product_name: string;
  source_warehouse_code: string;
  source_warehouse_name: string;
  target_warehouse_code: string;
  target_warehouse_name: string;
  quantity: number;
  reason: string;
  transferred_by: string;
  transferrer_name?: string | null;
  created_at: string;
}

export interface StockTransferCreateInput {
  source_warehouse_code: string;
  target_warehouse_code: string;
  sku: string;
  quantity: number;
  reason: string;
}

export async function transferInventoryApi(data: StockTransferCreateInput): Promise<StockTransferItem> {
  return apiClient<StockTransferItem>("/inventory/transfers", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchStockTransfersApi(params?: {
  sku?: string;
  limit?: number;
  offset?: number;
}): Promise<StockTransferItem[]> {
  const query = new URLSearchParams();
  if (params?.sku) query.append("sku", params.sku);
  if (params?.limit) query.append("limit", params.limit.toString());
  if (params?.offset) query.append("offset", params.offset.toString());

  const qs = query.toString();
  return apiClient<StockTransferItem[]>(`/inventory/transfers${qs ? `?${qs}` : ""}`);
}

// ----------------------------------------------------
// Purchasing & Supplier APIs (Phase 6)
// ----------------------------------------------------
export interface SupplierItem {
  id: string;
  code: string;
  name: string;
  tax_code?: string | null;
  contact_email?: string | null;
  phone?: string | null;
  address?: string | null;
  status: "active" | "inactive" | string;
  created_at: string;
}

export interface PurchaseOrderItemDetail {
  id: string;
  product_id: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface PurchaseOrderItem {
  id: string;
  po_number: string;
  supplier_id: string;
  supplier_code: string;
  supplier_name: string;
  warehouse_id: string;
  warehouse_code: string;
  warehouse_name: string;
  status: "draft" | "ordered" | "received" | "cancelled" | string;
  total_amount: number;
  notes?: string | null;
  created_by: string;
  creator_name?: string | null;
  created_at: string;
  items: PurchaseOrderItemDetail[];
}

export async function fetchSuppliers(params?: {
  status?: string;
  limit?: number;
}): Promise<SupplierItem[]> {
  const q = new URLSearchParams();
  if (params?.status) q.append("status", params.status);
  if (params?.limit) q.append("limit", params.limit.toString());
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<SupplierItem[]>(`/purchasing/suppliers${queryString}`);
}

export async function createSupplierApi(payload: {
  code: string;
  name: string;
  tax_code?: string;
  contact_email?: string;
  phone?: string;
  address?: string;
}): Promise<SupplierItem> {
  return apiClient<SupplierItem>("/purchasing/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchPurchaseOrders(params?: {
  status?: string;
  supplier_code?: string;
  warehouse_code?: string;
  limit?: number;
}): Promise<PurchaseOrderItem[]> {
  const q = new URLSearchParams();
  if (params?.status) q.append("status", params.status);
  if (params?.supplier_code) q.append("supplier_code", params.supplier_code);
  if (params?.warehouse_code) q.append("warehouse_code", params.warehouse_code);
  if (params?.limit) q.append("limit", params.limit.toString());
  const queryString = q.toString() ? `?${q.toString()}` : "";
  return apiClient<PurchaseOrderItem[]>(`/purchasing/orders${queryString}`);
}

export async function fetchPurchaseOrderDetail(poId: string): Promise<PurchaseOrderItem> {
  return apiClient<PurchaseOrderItem>(`/purchasing/orders/${poId}`);
}

export async function createPurchaseOrderApi(payload: {
  supplier_code: string;
  warehouse_code: string;
  items: Array<{ sku: string; quantity: number; unit_price: number }>;
  notes?: string;
}): Promise<PurchaseOrderItem> {
  return apiClient<PurchaseOrderItem>("/purchasing/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function receivePurchaseOrderApi(poId: string): Promise<PurchaseOrderItem> {
  return apiClient<PurchaseOrderItem>(`/purchasing/orders/${poId}/receive`, {
    method: "POST",
  });
}

export async function cancelPurchaseOrderApi(poId: string, reason?: string): Promise<PurchaseOrderItem> {
  return apiClient<PurchaseOrderItem>(`/purchasing/orders/${poId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || "Hủy đơn mua hàng" }),
  });
}






from typing import Dict, List
from langchain_core.tools import BaseTool

from app.ai.tools.erp_tools import (
    get_inventory,
    get_product,
    list_products,
    get_customer,
    list_customers,
    get_sales_orders,
    get_revenue_report,
    propose_sales_order_draft,
    deliver_sales_order,
    adjust_inventory,
    generate_sales_quotation,
    check_customer_credit,
    get_sales_leaderboard,
    get_financial_and_debt_report,
    get_audit_logs,
)
from app.ai.tools.rag_tool import search_company_knowledge
from app.ai.tools.context import (
    UserContext,
    get_current_user_context,
    set_current_user_context,
)

ALL_AGENT_TOOLS: List[BaseTool] = [
    get_inventory,
    get_product,
    list_products,
    get_customer,
    list_customers,
    get_sales_orders,
    get_revenue_report,
    propose_sales_order_draft,
    deliver_sales_order,
    adjust_inventory,
    generate_sales_quotation,
    check_customer_credit,
    get_sales_leaderboard,
    get_financial_and_debt_report,
    get_audit_logs,
    search_company_knowledge,
]


def get_tools_map() -> Dict[str, BaseTool]:
    """Returns a dictionary mapping tool names to BaseTool instances."""
    return {tool.name: tool for tool in ALL_AGENT_TOOLS}


__all__ = [
    "ALL_AGENT_TOOLS",
    "get_tools_map",
    "get_inventory",
    "get_product",
    "list_products",
    "get_customer",
    "list_customers",
    "get_sales_orders",
    "get_revenue_report",
    "propose_sales_order_draft",
    "deliver_sales_order",
    "adjust_inventory",
    "generate_sales_quotation",
    "check_customer_credit",
    "get_sales_leaderboard",
    "get_financial_and_debt_report",
    "search_company_knowledge",
    "UserContext",
    "get_current_user_context",
    "set_current_user_context",
]

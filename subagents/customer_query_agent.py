"""
客户查询子智能体配置

负责查询客户基础信息，包括姓名、电话、地址和客户等级。
"""

from typing import Dict, Any
from tools.crm_tools import get_customer_info


customer_query_agent: Dict[str, Any] = {
    "name": "customer-query",
    "description": "查询客户基础信息的专家，可返回姓名、电话、地址与客户等级。",
    "system_prompt": (
        "你是客户洞察专家。收到请求后优先调用 get_customer_info，"
        "返回结构化客户信息；如查询失败，返回明确且友好的错误提示。"
    ),
    "tools": [get_customer_info],
}

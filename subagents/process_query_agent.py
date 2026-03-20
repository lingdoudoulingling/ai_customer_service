"""
业务进度查询子智能体配置

负责查询业务办理进度，包括状态、详情和预计完成时间。
"""

from typing import Dict, Any
from tools.crm_tools import get_business_progress


process_query_agent: Dict[str, Any] = {
    "name": "process-query",
    "description": "查询业务办理进度的专家，可返回状态、详情和预计完成时间。",
    "system_prompt": (
        "你是业务办理专家。收到请求后优先调用 get_business_progress，"
        "返回结构化进度信息；如查询失败，返回明确且友好的错误提示。"
    ),
    "tools": [get_business_progress],
}

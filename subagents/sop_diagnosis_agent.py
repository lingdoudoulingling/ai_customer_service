"""Lightweight SOP-guided diagnosis subagent configuration."""

from typing import Any, Dict

from prompts.sop_diagnosis_prompt import SOP_DIAGNOSIS_SYSTEM_PROMPT
from tools.tieta_tools import (
    query_pms_system_push_log,
    query_public_library,
    query_resource_system,
    query_resource_system_change_history,
    query_resource_system_receive_log,
)


sop_diagnosis_agent: Dict[str, Any] = {
    "name": "sop-diagnosis",
    "description": "铁塔客户问题诊断专家。适用于资源在建异常、利旧资源查不到等场景。",
    "system_prompt": SOP_DIAGNOSIS_SYSTEM_PROMPT,
    "tools": [
        query_resource_system,
        query_public_library,
        query_resource_system_receive_log,
        query_resource_system_change_history,
        query_pms_system_push_log,
    ],
}

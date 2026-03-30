"""Structured-yet-flexible SOP knowledge used by the diagnosis subagent."""

from __future__ import annotations

from typing import Any


SOP_SCENE_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "01": {
        "scene_id": "01",
        "scene_name": "项目已内验，但对应资源在系统中仍为在建状态",
        "trigger_keywords": [
            "内验后资源还是在建",
            "项目已经内验了资源还是在建",
            "资源状态异常",
            "在建状态",
        ],
        "required_inputs": ["resource_code"],
        "recommended_evidence": [
            "资源系统基础信息",
            "公共库内验状态",
            "资源系统接收日志",
            "资源系统变更履历",
        ],
        "diagnosis_guidance": [
            "先确认资源系统当前资源状态、PMS 项目编码和资源是否存在。",
            "再核实公共库是否已存在内验状态以及是否已向资源系统转发。",
            "如果公共库已转发但资源系统仍未变化，再检查资源系统是否收到报文和是否有状态变更记录。",
            "当证据不足时，可以补充说明缺失证据，不要硬性下结论。",
        ],
        "common_conclusions": [
            "PMS 上游未推送内验状态",
            "公共库下发链路异常",
            "资源系统处理异常",
        ],
        "default_message_type": "INNER_ACCEPTANCE",
    },
    "02": {
        "scene_id": "02",
        "scene_name": "PMS 发起利旧流程后，资源录入页无法查询到利旧设备资源",
        "trigger_keywords": [
            "利旧资源查不到",
            "资源录入缺少利旧设备",
            "利旧资源匹配失败",
            "录入页看不到利旧设备",
        ],
        "required_inputs": ["asset_code"],
        "recommended_evidence": [
            "资源系统资源详情与绑定关系",
            "资源系统变更履历",
            "PMS 推送日志",
            "资源系统接收日志",
        ],
        "diagnosis_guidance": [
            "先核实资源是否存在、是否可见、是否绑定、是否删除。",
            "如果资源存在但看不到，继续检查是否发生解绑或逻辑删除。",
            "再核实 PMS 是否发起利旧流程、是否已推送资源系统，以及资源系统是否接收到利旧指令。",
            "当发现 SOP 未覆盖的新组合时，输出证据链、你的推断和后续建议，而不是只返回失败。",
        ],
        "common_conclusions": [
            "资源与资产编码已解绑",
            "资源已逻辑删除",
            "PMS 未推送利旧指令",
            "资源系统接收或处理异常",
        ],
        "default_message_type": "REUSE_INSTRUCTION",
    },
}


def list_scene_summaries() -> list[dict[str, str]]:
    """Return light-weight summaries for routing and prompting."""
    return [
        {
            "scene_id": scene["scene_id"],
            "scene_name": scene["scene_name"],
            "required_inputs": ",".join(scene.get("required_inputs", [])),
        }
        for scene in SOP_SCENE_KNOWLEDGE.values()
    ]


def get_scene_knowledge(scene_id: str) -> dict[str, Any] | None:
    """Return a single scene's knowledge entry."""
    return SOP_SCENE_KNOWLEDGE.get(str(scene_id).strip())

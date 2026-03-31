"""
主智能体创建模块。

使用 deepagents 的 create_deep_agent 创建主智能体，并支持对敏感工具启用 HITL。
"""

from typing import Any, Callable, Dict, List

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver


def create_master_agent(
    model: str | BaseChatModel,
    tools: List[Callable],
    subagents: List[Dict[str, Any]],
    system_prompt: str,
    memory_files: List[str],
    skills: List[str] | None = None,
    interrupt_on: Dict[str, Any] | None = None,
) -> Any:
    """创建带 memory 和可选 HITL 审批配置的 deep agent。"""
    return create_deep_agent(
        model=model,
        tools=tools,
        subagents=subagents,
        system_prompt=system_prompt,
        checkpointer=MemorySaver(),
        memory=memory_files,
        skills=skills,
        interrupt_on=interrupt_on,
    )


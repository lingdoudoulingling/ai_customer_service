"""Master agent factory."""

from typing import Any, Callable

from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver


def create_master_agent(
    model: str | BaseChatModel,
    tools: list[Callable],
    subagents: list[dict[str, Any]],
    system_prompt: str,
    skills: list[str] | None = None,
    interrupt_on: dict[str, Any] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """创建主智能体，并把记忆能力保持为外部可注入的依赖。"""
    return create_deep_agent(
        model=model,
        tools=tools,
        subagents=subagents,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        skills=skills,
        interrupt_on=interrupt_on,
    )

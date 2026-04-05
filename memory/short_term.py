"""Short-term memory helpers backed by LangGraph Postgres checkpoints."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

try:
    from langchain_core.messages import BaseMessage
except ImportError:  # pragma: no cover - dependency is already required by the app
    BaseMessage = Any  # type: ignore[assignment]

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:  # pragma: no cover - handled at runtime with a clear error
    PostgresSaver = None

DEFAULT_CHECKPOINT_NAMESPACE = "ai_customer_service"
DEFAULT_SHORT_TERM_MESSAGE_LIMIT = 6


@dataclass(frozen=True)
class ShortTermContext:
    """Short-term context read from LangGraph checkpoints."""

    thread_id: str
    checkpoint_ns: str
    summary: str
    raw_messages: list[Any]


def build_checkpoint_config(
    thread_id: str,
    checkpoint_ns: str = DEFAULT_CHECKPOINT_NAMESPACE,
) -> dict[str, Any]:
    """构造 LangGraph 统一使用的 thread_id/checkpoint_ns 配置。"""
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }
    }


@contextmanager
def open_postgres_checkpointer(
    postgres_url: str,
    auto_setup: bool = True,
) -> Iterator[Any]:
    """打开 Postgres checkpointer，并在需要时自动初始化表结构。"""
    if PostgresSaver is None:
        raise ImportError(
            "缺少 langgraph-checkpoint-postgres 依赖，请先安装 "
            "`langgraph-checkpoint-postgres` 和 `psycopg[binary,pool]`。"
        )

    with PostgresSaver.from_conn_string(postgres_url) as checkpointer:
        if auto_setup:
            checkpointer.setup()
        yield checkpointer


def get_short_term_context(
    agent: Any,
    thread_id: str,
    checkpoint_ns: str = DEFAULT_CHECKPOINT_NAMESPACE,
    limit: int = DEFAULT_SHORT_TERM_MESSAGE_LIMIT,
) -> ShortTermContext:
    """读取指定线程最近的有效对话片段，作为短期上下文输入。"""
    config = build_checkpoint_config(thread_id, checkpoint_ns)
    try:
        snapshot = agent.get_state(config)
    except Exception:
        return ShortTermContext(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            summary="",
            raw_messages=[],
        )

    values = getattr(snapshot, "values", {}) or {}
    raw_messages = values.get("messages", []) if isinstance(values, dict) else []
    filtered_messages = []
    for message in raw_messages:
        role, content = message_to_role_content(message)
        if role == "system" and "<external_context>" in content:
            continue
        filtered_messages.append(message)

    recent_messages = filtered_messages[-limit:]
    summary = format_messages_as_text(recent_messages)
    return ShortTermContext(
        thread_id=thread_id,
        checkpoint_ns=checkpoint_ns,
        summary=summary,
        raw_messages=recent_messages,
    )


def format_messages_as_text(messages: list[Any]) -> str:
    """把最近消息压成易读文本，供上下文服务层注入。"""
    rendered: list[str] = []
    for message in messages:
        role, content = message_to_role_content(message)
        if not content:
            continue
        role_label = {
            "human": "用户",
            "user": "用户",
            "ai": "助手",
            "assistant": "助手",
            "tool": "工具",
            "system": "系统",
        }.get(role, role)
        rendered.append(f"{role_label}：{content}")
    return "\n".join(rendered)


def message_to_role_content(message: Any) -> tuple[str, str]:
    """兼容 LangChain message 和 dict message，统一抽取 role/content。"""
    if isinstance(message, dict):
        role = str(message.get("role", "unknown"))
        content = str(message.get("content", ""))
        return role, content

    if isinstance(message, BaseMessage):
        role = getattr(message, "type", "unknown")
        content = getattr(message, "content", "")
        if isinstance(content, list):
            text_parts = [str(part) for part in content if isinstance(part, (str, dict))]
            return role, " ".join(text_parts)
        return role, str(content)

    role = getattr(message, "type", "unknown")
    content = getattr(message, "content", "")
    return str(role), str(content)

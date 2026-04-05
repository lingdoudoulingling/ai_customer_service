"""Context service that fuses short-term and long-term memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memory.compression import compress_context
from memory.long_term import LongTermMemoryStore, extract_long_term_memory_items
from memory.short_term import (
    DEFAULT_CHECKPOINT_NAMESPACE,
    DEFAULT_SHORT_TERM_MESSAGE_LIMIT,
    get_short_term_context,
)


@dataclass(frozen=True)
class RuntimeContextBundle:
    """单轮调用前注入给主智能体的上下文包。"""

    session_context: str
    mem0_memories: list[str]
    compressed_context: str


class ContextService:
    """负责记忆检索、压缩融合，以及长期记忆写回的服务层。"""

    def __init__(
        self,
        long_term_store: LongTermMemoryStore,
        checkpoint_ns: str = DEFAULT_CHECKPOINT_NAMESPACE,
        context_max_items: int = 5,
        context_max_chars: int = 1200,
        short_term_limit: int = DEFAULT_SHORT_TERM_MESSAGE_LIMIT,
    ) -> None:
        self.long_term_store = long_term_store
        self.checkpoint_ns = checkpoint_ns
        self.context_max_items = context_max_items
        self.context_max_chars = context_max_chars
        self.short_term_limit = short_term_limit

    def build_runtime_context(
        self,
        agent: Any,
        user_id: str,
        thread_id: str,
        user_input: str,
    ) -> RuntimeContextBundle:
        """同时读取短期/长期记忆，并压缩成一段高浓度上下文。"""
        short_term = get_short_term_context(
            agent=agent,
            thread_id=thread_id,
            checkpoint_ns=self.checkpoint_ns,
            limit=self.short_term_limit,
        )
        long_term_items = self.long_term_store.search(
            query=user_input,
            user_id=user_id,
            limit=self.context_max_items,
        )
        compressed = compress_context(
            user_input=user_input,
            session_context=short_term.summary,
            mem0_memories=long_term_items,
            max_items=self.context_max_items,
            max_chars=self.context_max_chars,
        )
        return RuntimeContextBundle(
            session_context=short_term.summary,
            mem0_memories=[item.text for item in long_term_items],
            compressed_context=compressed,
        )

    def build_agent_messages(
        self,
        runtime_context: RuntimeContextBundle,
        user_input: str,
    ) -> list[dict[str, str]]:
        """把外部上下文包装成 system 消息，再附上当前用户输入。"""
        messages: list[dict[str, str]] = []
        if runtime_context.compressed_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "<external_context>\n"
                        f"{runtime_context.compressed_context}\n"
                        "</external_context>"
                    ),
                }
            )
        messages.append({"role": "user", "content": user_input})
        return messages

    def write_memory_after_turn(
        self,
        user_id: str,
        thread_id: str,
        user_input: str,
        assistant_response: str,
    ) -> list[str]:
        """把本轮里值得长期保存的稳定事实写回 Mem0。"""
        memories = extract_long_term_memory_items(
            user_input=user_input,
            assistant_response=assistant_response,
        )
        if not memories:
            return []
        return self.long_term_store.write_memories(
            user_id=user_id,
            memories=memories,
            metadata={"thread_id": thread_id, "source": "app.py"},
        )

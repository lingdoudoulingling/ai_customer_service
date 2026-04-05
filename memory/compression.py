"""Manual compression rules for runtime context construction."""

from __future__ import annotations

import re

from memory.long_term import LongTermMemoryItem


def compress_context(
    user_input: str,
    session_context: str,
    mem0_memories: list[LongTermMemoryItem],
    max_items: int,
    max_chars: int,
) -> str:
    """把短期上下文和长期记忆压缩成可注入 prompt 的文本块。"""
    sections: list[str] = []
    if session_context:
        session_text = truncate_text(session_context.strip(), max_chars // 2)
        if session_text:
            sections.append(f"【短期上下文】\n{session_text}")

    ranked_memories = rank_memories(user_input, mem0_memories)[:max_items]
    if ranked_memories:
        rendered = "\n".join(f"- {item.text}" for item in ranked_memories)
        sections.append(f"【长期记忆】\n{rendered}")

    merged = "\n\n".join(sections)
    return truncate_text(merged, max_chars)


def rank_memories(user_input: str, memories: list[LongTermMemoryItem]) -> list[LongTermMemoryItem]:
    """按词项重叠和偏好优先级，对长期记忆做轻量排序。"""
    query_terms = tokenize(user_input)

    def score(item: LongTermMemoryItem) -> tuple[int, int]:
        item_terms = tokenize(item.text)
        overlap = len(query_terms.intersection(item_terms))
        preference_bonus = 1 if ("偏好" in item.text or "喜欢" in item.text or "回答" in item.text) else 0
        return overlap, preference_bonus

    return sorted(memories, key=score, reverse=True)


def tokenize(text: str) -> set[str]:
    """把中英混合文本切成轻量词项，供简单相关性排序使用。"""
    ascii_terms = re.findall(r"[A-Za-z0-9_]+", text.lower())
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    return set(ascii_terms + chinese_terms)


def truncate_text(text: str, max_chars: int) -> str:
    """限制上下文长度，避免单轮注入过长。"""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."

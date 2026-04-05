"""Long-term memory helpers backed by Mem0."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any

PROJECT_MEM0_DIR = Path("data") / "mem0"
# 将 Mem0 的本地文件统一收口到项目目录，避免写入用户主目录。
os.environ.setdefault("MEM0_DIR", str(PROJECT_MEM0_DIR.resolve()))
os.environ.setdefault("MEM0_TELEMETRY", "False")

try:
    from mem0 import Memory
except ImportError:  # pragma: no cover - handled at runtime with a clear error
    Memory = None

SENSITIVE_PATTERNS = (
    re.compile(r"api[_ -]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"密钥|密码|令牌|验证码"),
)
TRANSIENT_PATTERNS = (
    re.compile(r"\bT\d{3,}\b", re.IGNORECASE),
    re.compile(r"\b\d{12,}\b"),
    re.compile(r"工单号|资源编码|traceid|sessionid", re.IGNORECASE),
    re.compile(r"临时|这次|本次|刚才"),
)


@dataclass(frozen=True)
class LongTermMemoryItem:
    """上下文服务层使用的长期记忆条目。"""

    text: str
    metadata: dict[str, Any]


class LongTermMemoryStore:
    """对 Mem0 做一层适配，统一检索、过滤和写回接口。"""

    def __init__(self, memory_client: Any | None, enabled: bool = True) -> None:
        self.memory_client = memory_client
        self.enabled = enabled and memory_client is not None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None, enabled: bool = True) -> "LongTermMemoryStore":
        """根据项目配置创建长期记忆存储，并处理本地路径初始化。"""
        if not enabled:
            return cls(memory_client=None, enabled=False)
        if Memory is None:
            raise ImportError("缺少 mem0ai 依赖，请先安装 `mem0ai`。")
        if not config or not isinstance(config, dict):
            raise ValueError("启用 Mem0 时必须提供 MEM0_CONFIG。")
        normalized_config = normalize_mem0_config(config)
        history_db_path = Path(str(normalized_config["history_db_path"]))
        history_db_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_config["history_db_path"] = str(history_db_path)
        return cls(memory_client=Memory.from_config(normalized_config), enabled=True)

    def search(self, query: str, user_id: str, limit: int = 5) -> list[LongTermMemoryItem]:
        """按 user_id 检索与当前问题相关的长期记忆。"""
        if not self.enabled:
            return []

        try:
            response = self.memory_client.search(query, user_id=user_id)
        except Exception:
            return []

        results = response.get("results", []) if isinstance(response, dict) else response
        items: list[LongTermMemoryItem] = []
        for raw in results[:limit]:
            text = str(raw.get("memory", "")).strip()
            if not text:
                continue
            metadata = raw.get("metadata", {}) if isinstance(raw, dict) else {}
            items.append(LongTermMemoryItem(text=text, metadata=metadata))
        return items

    def write_memories(
        self,
        user_id: str,
        memories: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        """把过滤后的长期记忆写入 Mem0，并返回实际写入内容。"""
        if not self.enabled:
            return []

        written: list[str] = []
        payload_metadata = metadata or {}
        for memory_text in memories:
            clean_text = memory_text.strip()
            if not clean_text:
                continue
            if not is_long_term_memory_candidate(clean_text):
                continue
            try:
                self.memory_client.add(
                    [{"role": "user", "content": clean_text}],
                    user_id=user_id,
                    metadata=payload_metadata,
                )
                written.append(clean_text)
            except Exception:
                continue
        return written

def extract_long_term_memory_items(
    user_input: str,
    assistant_response: str,
) -> list[str]:
    """从用户输入里抽取值得长期保存的偏好和稳定事实。"""
    del assistant_response
    text = user_input.strip()
    if not text:
        return []

    candidates: list[str] = []
    explicit_prefixes = ("请记住：", "请记住:", "记住：", "记住:")
    for prefix in explicit_prefixes:
        if text.startswith(prefix):
            remainder = text[len(prefix) :].strip()
            candidates.extend(split_memory_sentences(remainder))
            break

    if not candidates:
        for marker in ("我喜欢", "我偏好", "以后回答请", "请按我的偏好", "我是", "我负责"):
            if marker in text:
                candidates.extend(split_memory_sentences(text))
                break

    deduped: list[str] = []
    for candidate in candidates:
        normalized = candidate.strip("。；;，, ")
        if not normalized:
            continue
        if not is_long_term_memory_candidate(normalized):
            continue
        if normalized not in deduped:
            deduped.append(normalized)
    return deduped


def is_long_term_memory_candidate(text: str) -> bool:
    """判断文本是否足够稳定且安全，适合写入长期记忆。"""
    if not text.strip():
        return False
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(text):
            return False
    for pattern in TRANSIENT_PATTERNS:
        if pattern.search(text):
            return False
    return True


def split_memory_sentences(text: str) -> list[str]:
    """把一段记忆表达拆成多个短句，便于逐条入库。"""
    parts = re.split(r"[。；;\n]", text)
    return [part.strip() for part in parts if part.strip()]


def normalize_mem0_config(config: dict[str, Any]) -> dict[str, Any]:
    """把项目配置转换成当前安装版 mem0 可识别的 provider 形式。"""
    normalized = deepcopy(config)
    normalized.setdefault("history_db_path", str(Path("data") / "mem0_history.db"))

    for section in ("llm", "embedder"):
        provider_block = normalized.get(section)
        if not isinstance(provider_block, dict):
            continue

        provider = str(provider_block.get("provider", "")).strip().lower()
        provider_config = provider_block.get("config")
        if not isinstance(provider_config, dict):
            provider_config = {}
            provider_block["config"] = provider_config

        if provider == "siliconflow":
            provider_block["provider"] = "openai"
            provider_config.setdefault(
                "openai_base_url",
                provider_config.get("base_url")
                or provider_config.get("api_base")
                or "https://api.siliconflow.cn/v1",
            )
        elif provider == "openai":
            base_url = provider_config.get("base_url") or provider_config.get("api_base")
            if base_url:
                provider_config.setdefault("openai_base_url", base_url)

    reranker_block = normalized.get("reranker")
    if isinstance(reranker_block, dict):
        reranker_provider = str(reranker_block.get("provider", "")).strip().lower()
        if reranker_provider == "siliconflow":
            normalized["reranker"] = None

    return normalized

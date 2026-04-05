import json
import uuid
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from langchain_siliconflow import ChatSiliconFlow
from langgraph.types import Command

from master_agent import create_master_agent
from memory.context_service import ContextService
from memory.long_term import LongTermMemoryStore
from memory.short_term import (
    build_checkpoint_config,
    open_postgres_checkpointer,
)
from prompts.master_agent_prompt import MASTER_AGENT_SYSTEM_PROMPT
from subagents.customer_query_agent import customer_query_agent
from subagents.process_query_agent import process_query_agent
from subagents.sop_diagnosis_agent import sop_diagnosis_agent
from subagents.tv_package_query_subagent import tv_package_query_subagent
from tools.ticket_tools import build_manual_ticket_draft, submit_manual_ticket

MASTER_AGENT_SKILLS = ["skills/diagnosis-workflow"]
SESSION_HISTORY_PATH = Path("data/session_history.json")


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """加载并校验运行配置，避免主流程带着缺失参数启动。"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    with path.open("r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file) or {}

    required_keys = [
        "SILICONFLOW_API_KEY",
        "SILICONFLOW_BASE_URL",
        "DEFAULT_MODEL",
        "SHOW_REASONING",
        "ENABLE_THINKING",
        "THINKING_BUDGET",
        "POSTGRES_URL",
        "POSTGRES_AUTO_SETUP",
        "CHECKPOINT_NAMESPACE",
        "MEM0_ENABLED",
        "MEM0_CONFIG",
        "CONTEXT_MAX_ITEMS",
        "CONTEXT_MAX_CHARS",
        "SHORT_TERM_MESSAGE_LIMIT",
    ]
    for key in required_keys:
        if key not in cfg:
            raise ValueError(f"config.yaml 缺少必要配置: {key}")
        value = cfg[key]
        if value is None:
            raise ValueError(f"config.yaml 缺少必要配置: {key}")
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"config.yaml 缺少必要配置: {key}")

    if cfg["MEM0_ENABLED"] and not cfg.get("MEM0_CONFIG"):
        raise ValueError("启用 Mem0 时，config.yaml 必须配置 MEM0_CONFIG")

    return cfg


def build_model(cfg: dict[str, Any]) -> ChatSiliconFlow:
    """根据配置构建主模型实例。"""
    return ChatSiliconFlow(
        model=cfg["DEFAULT_MODEL"],
        api_key=cfg["SILICONFLOW_API_KEY"],
        base_url=cfg["SILICONFLOW_BASE_URL"],
        extra_body={
            "enable_thinking": bool(cfg["ENABLE_THINKING"]),
            "thinking_budget": int(cfg["THINKING_BUDGET"]),
        },
    )


def create_context_service(cfg: dict[str, Any]) -> ContextService:
    """组装上下文服务层，统一管理短期/长期记忆读取与写回。"""
    long_term_store = LongTermMemoryStore.from_config(
        config=cfg["MEM0_CONFIG"],
        enabled=bool(cfg["MEM0_ENABLED"]),
    )
    return ContextService(
        long_term_store=long_term_store,
        checkpoint_ns=str(cfg["CHECKPOINT_NAMESPACE"]),
        context_max_items=int(cfg["CONTEXT_MAX_ITEMS"]),
        context_max_chars=int(cfg["CONTEXT_MAX_CHARS"]),
        short_term_limit=int(cfg["SHORT_TERM_MESSAGE_LIMIT"]),
    )


def build_master_agent(model: ChatSiliconFlow, checkpointer: Any) -> Any:
    """构建主智能体实例。

    Args:
        model: LLM 模型实例
        checkpointer: 检查点存储器

    Returns:
        主智能体实例
    """
    return create_master_agent(
        model=model,
        tools=[build_manual_ticket_draft, submit_manual_ticket],
        subagents=[
            customer_query_agent,
            process_query_agent,
            tv_package_query_subagent,
            sop_diagnosis_agent,
        ],
        system_prompt=MASTER_AGENT_SYSTEM_PROMPT,
        skills=MASTER_AGENT_SKILLS,
        interrupt_on={
            "submit_manual_ticket": {
                "allowed_decisions": ["approve", "reject"],
                "description": "提交人工工单前请核对工单标题、正文以及完整诊断记录附件。",
            }
        },
        checkpointer=checkpointer,
    )


def _get_last_message_text(result_value: dict[str, Any]) -> str:
    """提取当前轮对话里最后一条助手消息文本。"""
    last_msg = result_value["messages"][-1]
    return str(last_msg.content)


def _print_last_message(result_value: dict[str, Any], show_reasoning: bool = True) -> None:
    """按控制台展示格式输出模型思考和最终回复。"""
    last_msg = result_value["messages"][-1]
    reasoning = getattr(last_msg, "additional_kwargs", {}).get("reasoning_content")
    if show_reasoning and reasoning:
        print(f"思考：{reasoning}")
    print(f"助手：{last_msg.content}")


def _prompt_hitl_decisions(interrupt_value: dict[str, Any]) -> list[dict[str, Any]]:
    """处理 HITL 中断，让操作者决定是否批准敏感工具调用。"""
    action_requests = interrupt_value.get("action_requests", [])
    review_configs = interrupt_value.get("review_configs", [])
    decisions: list[dict[str, Any]] = []

    for idx, action in enumerate(action_requests):
        review = review_configs[idx] if idx < len(review_configs) else {}
        print("\n【人工审批】")
        print(f"工具：{action.get('name')}")
        print(f"参数：{action.get('args')}")
        if review.get("description"):
            print(f"说明：{review['description']}")

        while True:
            decision = input("是否批准该操作？请输入 approve/reject：").strip().lower()
            if decision in {"approve", "reject"}:
                break

        if decision == "approve":
            decisions.append({"type": "approve"})
        else:
            reason = input("请输入拒绝原因（可留空）：").strip()
            item: dict[str, Any] = {"type": "reject"}
            if reason:
                item["message"] = reason
            decisions.append(item)

    return decisions


def invoke_agent_once(
    agent: Any,
    context_service: ContextService,
    user_id: str,
    user_input: str,
    thread_id: str,
    checkpoint_ns: str,
    show_reasoning: bool = True,
) -> str:
    """执行单轮对话：先注入记忆上下文，再处理 HITL，最后写回长期记忆。"""
    config = build_checkpoint_config(thread_id, checkpoint_ns)
    runtime_context = context_service.build_runtime_context(
        agent=agent,
        user_id=user_id,
        thread_id=thread_id,
        user_input=user_input,
    )
    messages = context_service.build_agent_messages(runtime_context, user_input)
    result = agent.invoke(
        {"messages": messages},
        config=config,
        version="v2",
    )

    while getattr(result, "interrupts", None):
        interrupt_value = result.interrupts[0].value
        decisions = _prompt_hitl_decisions(interrupt_value)
        result = agent.invoke(
            Command(resume={"decisions": decisions}),
            config=config,
            version="v2",
        )

    result_value = result.value if hasattr(result, "value") else result
    assistant_text = _get_last_message_text(result_value)
    context_service.write_memory_after_turn(
        user_id=user_id,
        thread_id=thread_id,
        user_input=user_input,
        assistant_response=assistant_text,
    )
    _print_last_message(result_value, show_reasoning=show_reasoning)
    return assistant_text


def prompt_user_id() -> str:
    """读取用户标识，作为长期记忆隔离键。"""
    while True:
        user_id = input("请输入 user_id：").strip()
        if user_id:
            return user_id
        print("user_id 不能为空。")


def load_session_history() -> dict[str, Any]:
    """读取本地会话索引，用于 new/resume 会话选择。"""
    if not SESSION_HISTORY_PATH.exists():
        return {}
    try:
        content = json.loads(SESSION_HISTORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return content if isinstance(content, dict) else {}


def save_session_history(history: dict[str, Any]) -> None:
    """持久化最近会话信息，便于下次恢复 thread_id。"""
    SESSION_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def update_session_history(user_id: str, thread_id: str) -> None:
    """更新某个 user_id 最近使用过的 thread_id 列表。"""
    history = load_session_history()
    record = history.get(user_id, {})
    recent_thread_ids = record.get("recent_thread_ids", [])
    if not isinstance(recent_thread_ids, list):
        recent_thread_ids = []

    deduped = [item for item in recent_thread_ids if item != thread_id]
    deduped.insert(0, thread_id)
    history[user_id] = {
        "last_thread_id": thread_id,
        "recent_thread_ids": deduped[:5],
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_session_history(history)


def prompt_thread_id(user_id: str) -> tuple[str, str]:
    """为当前 user_id 选择新会话或恢复旧会话。"""
    history = load_session_history()
    record = history.get(user_id, {})
    last_thread_id = record.get("last_thread_id")

    if not isinstance(last_thread_id, str) or not last_thread_id.strip():
        thread_id = str(uuid.uuid4())
        update_session_history(user_id, thread_id)
        return thread_id, "新会话"

    print(f"检测到上次会话 thread_id：{last_thread_id}")
    while True:
        choice = input("请选择会话模式（new/resume，默认 resume）：").strip().lower()
        if not choice:
            choice = "resume"
        if choice in {"new", "n"}:
            thread_id = str(uuid.uuid4())
            update_session_history(user_id, thread_id)
            return thread_id, "新会话"
        if choice in {"resume", "r"}:
            custom_thread_id = input(
                f"请输入要恢复的 thread_id，直接回车使用上次的 {last_thread_id}："
            ).strip()
            thread_id = custom_thread_id or last_thread_id
            update_session_history(user_id, thread_id)
            return thread_id, "恢复旧会话"
        print("请输入 new 或 resume。")


def main() -> None:
    """控制台入口：初始化依赖、选择会话并循环处理用户输入。"""
    cfg = load_config()
    model = build_model(cfg)
    context_service = create_context_service(cfg)
    checkpoint_ns = str(cfg["CHECKPOINT_NAMESPACE"])

    with ExitStack() as stack:
        checkpointer = stack.enter_context(
            open_postgres_checkpointer(
                postgres_url=cfg["POSTGRES_URL"],
                auto_setup=bool(cfg["POSTGRES_AUTO_SETUP"]),
            )
        )
        agent = build_master_agent(model, checkpointer)

        user_id = prompt_user_id()
        thread_id, session_mode = prompt_thread_id(user_id)
        print(
            f"DeepAgents 控制台已启动，user_id={user_id}，"
            f"模式={session_mode}，thread_id={thread_id}，输入 exit 退出。"
        )

        while True:
            try:
                user_input = input("\n用户：").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n已退出。")
                break

            if user_input.lower() in {"exit", "quit", "q"}:
                print("已退出。")
                break

            if not user_input:
                continue

            show_reasoning = bool(cfg["SHOW_REASONING"])
            invoke_agent_once(
                agent=agent,
                context_service=context_service,
                user_id=user_id,
                user_input=user_input,
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                show_reasoning=show_reasoning,
            )


if __name__ == "__main__":
    main()

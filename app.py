# main.py
import uuid
from pathlib import Path

import yaml
from langchain_siliconflow import ChatSiliconFlow
from langgraph.types import Command

from master_agent import create_master_agent
from prompts.master_agent_prompt import MASTER_AGENT_SYSTEM_PROMPT
from subagents.customer_query_agent import customer_query_agent
from subagents.process_query_agent import process_query_agent
from subagents.sop_diagnosis_agent import sop_diagnosis_agent
from subagents.tv_package_query_subagent import tv_package_query_subagent
from tools.ticket_tools import build_manual_ticket_draft, submit_manual_ticket

MASTER_AGENT_SKILLS = ["skills/diagnosis-workflow"]


def load_config(config_path: str = "config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到配置文件: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    required_keys = ["SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL", "DEFAULT_MODEL"]
    for key in required_keys:
        if key not in cfg or not cfg[key]:
            raise ValueError(f"config.yaml 缺少必要配置: {key}")

    return cfg


def build_model(cfg: dict) -> ChatSiliconFlow:
    return ChatSiliconFlow(
        model=cfg["DEFAULT_MODEL"],
        api_key=cfg["SILICONFLOW_API_KEY"],
        base_url=cfg["SILICONFLOW_BASE_URL"],
        extra_body={
            "enable_thinking": bool(cfg.get("ENABLE_THINKING", True)),
            "thinking_budget": int(cfg.get("THINKING_BUDGET", 4096)),
        },
    )


def _print_last_message(result_value: dict, show_reasoning: bool = True) -> None:
    last_msg = result_value["messages"][-1]
    print(f"助手：{last_msg.content}")

    reasoning = getattr(last_msg, "additional_kwargs", {}).get("reasoning_content")
    if show_reasoning and reasoning:
        print(f"思考：{reasoning}")


def _prompt_hitl_decisions(interrupt_value: dict) -> list[dict]:
    action_requests = interrupt_value.get("action_requests", [])
    review_configs = interrupt_value.get("review_configs", [])
    decisions: list[dict] = []

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
            item = {"type": "reject"}
            if reason:
                item["message"] = reason
            decisions.append(item)

    return decisions


def invoke_agent_once(
    agent,
    user_input: str,
    thread_id: str,
    show_reasoning: bool = True,
) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
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
    _print_last_message(result_value, show_reasoning=show_reasoning)


def main():
    cfg = load_config()
    model = build_model(cfg)

    agent = create_master_agent(
        model=model,
        tools=[build_manual_ticket_draft, submit_manual_ticket],
        subagents=[
            customer_query_agent,
            process_query_agent,
            tv_package_query_subagent,
            sop_diagnosis_agent,
        ],
        system_prompt=MASTER_AGENT_SYSTEM_PROMPT,
        memory_files=["memories/LTM.md"],
        skills=MASTER_AGENT_SKILLS,
        interrupt_on={
            "submit_manual_ticket": {
                "allowed_decisions": ["approve", "reject"],
                "description": "提交人工工单前请核对工单标题、正文以及完整诊断记录附件。",
            }
        },
    )

    thread_id = str(uuid.uuid4())
    print("DeepAgents 控制台已启动，输入 exit 退出。")

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

        show_reasoning = bool(cfg.get("SHOW_REASONING", True))
        invoke_agent_once(agent, user_input, thread_id, show_reasoning=show_reasoning)


if __name__ == "__main__":
    main()

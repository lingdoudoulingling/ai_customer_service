# main.py
import uuid
from pathlib import Path

import yaml
from langchain_siliconflow import ChatSiliconFlow

from master_agent import create_master_agent
from prompts.master_agent_prompt import MASTER_AGENT_SYSTEM_PROMPT
from subagents.customer_query_agent import customer_query_agent
from subagents.process_query_agent import process_query_agent
from subagents.tv_package_query_subagent import tv_package_query_subagent


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
        # SiliconFlow 专属参数，放这里透传
        extra_body={
            "enable_thinking": bool(cfg.get("ENABLE_THINKING", True)),
            "thinking_budget": int(cfg.get("THINKING_BUDGET", 4096)),
        },
    )


def stream_agent_response(
    agent,
    user_input: str,
    thread_id: str,
    show_reasoning: bool = True,
) -> None:
    reasoning_started = False
    reply_parts: list[str] = []

    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": user_input}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="messages",
    ):
        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue

        message, _metadata = chunk
        if not type(message).__name__.startswith("AIMessage"):
            continue

        reasoning = getattr(message, "additional_kwargs", {}).get("reasoning_content")
        if show_reasoning and reasoning:
            reasoning = str(reasoning)
            if not reasoning_started:
                reasoning = reasoning.lstrip("\r\n")
                if reasoning:
                    print("思考：", end="", flush=True)
                    reasoning_started = True
            if reasoning:
                print(reasoning, end="", flush=True)

        text = str(getattr(message, "text", ""))
        if text:
            reply_parts.append(text)

    if show_reasoning and reasoning_started:
        print()

    reply_text = "".join(reply_parts).lstrip("\r\n")
    if reply_text:
        print(f"助手：{reply_text}")


def invoke_agent_once(
    agent,
    user_input: str,
    thread_id: str,
    show_reasoning: bool = True,
) -> None:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config={"configurable": {"thread_id": thread_id}},
    )

    last_msg = result["messages"][-1]
    print(f"助手：{last_msg.content}")

    reasoning = getattr(last_msg, "additional_kwargs", {}).get("reasoning_content")
    if show_reasoning and reasoning:
        print(f"思考：{reasoning}")


def main():
    cfg = load_config()

    model = build_model(cfg)

    agent = create_master_agent(
        model=model,
        tools=[],
        subagents=[customer_query_agent, process_query_agent, tv_package_query_subagent],
        system_prompt=MASTER_AGENT_SYSTEM_PROMPT,
        memory_files=["memories/LTM.md"],
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

        if cfg.get("STREAM_OUTPUT", True):
            stream_agent_response(agent, user_input, thread_id, show_reasoning=show_reasoning)
        else:
            invoke_agent_once(agent, user_input, thread_id, show_reasoning=show_reasoning)


if __name__ == "__main__":
    main()

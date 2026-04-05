import json
from pathlib import Path

from langgraph.types import Command

from app import (
    build_master_agent,
    build_model,
    create_context_service,
    invoke_agent_once,
    load_config,
)
from memory.short_term import build_checkpoint_config, open_postgres_checkpointer


def main() -> None:
    log_path = Path("data/tool_debug.log")
    before_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""

    cfg = load_config()
    model = build_model(cfg)
    context_service = create_context_service(cfg)
    checkpoint_ns = str(cfg["CHECKPOINT_NAMESPACE"])

    with open_postgres_checkpointer(
        postgres_url=cfg["POSTGRES_URL"],
        auto_setup=bool(cfg.get("POSTGRES_AUTO_SETUP", True)),
    ) as checkpointer:
        agent = build_master_agent(model, checkpointer)
        user_id = "demo-user"
        thread_id = "demo-two-stage-ticket-flow"

        round1 = (
            "查一下资源编码 00135100000000013123839，"
            "项目已经内验了但资源系统里还是在建。"
        )
        print("ROUND1 USER:", round1, flush=True)
        invoke_agent_once(
            agent=agent,
            context_service=context_service,
            user_id=user_id,
            user_input=round1,
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            show_reasoning=False,
        )

        round2 = "我确认提交人工工单。"
        print("ROUND2 USER:", round2, flush=True)
        result2 = agent.invoke(
            {
                "messages": context_service.build_agent_messages(
                    context_service.build_runtime_context(agent, user_id, thread_id, round2),
                    round2,
                )
            },
            config=build_checkpoint_config(thread_id, checkpoint_ns),
            version="v2",
        )
        print("ROUND2_INTERRUPTS:", bool(getattr(result2, "interrupts", None)), flush=True)
        if getattr(result2, "interrupts", None):
            print(
                "ROUND2_INTERRUPT_VALUE:",
                json.dumps(result2.interrupts[0].value, ensure_ascii=False, indent=2),
                flush=True,
            )
            result2 = agent.invoke(
                Command(resume={"decisions": [{"type": "approve"}]}),
                config=build_checkpoint_config(thread_id, checkpoint_ns),
                version="v2",
            )
        value2 = result2.value if hasattr(result2, "value") else result2
        print("ROUND2 FINAL_MESSAGE:", flush=True)
        print(value2["messages"][-1].content, flush=True)

    after_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    new_log = after_log[len(before_log) :]
    print("NEW_TOOL_DEBUG_LOG:", flush=True)
    print(new_log if new_log else "<empty>", flush=True)


if __name__ == "__main__":
    main()

import json
from pathlib import Path

from app import build_model, load_config
from langgraph.types import Command
from master_agent import create_master_agent
from prompts.master_agent_prompt import MASTER_AGENT_SYSTEM_PROMPT
from subagents.customer_query_agent import customer_query_agent
from subagents.process_query_agent import process_query_agent
from subagents.sop_diagnosis_agent import sop_diagnosis_agent
from subagents.tv_package_query_subagent import tv_package_query_subagent
from tools.ticket_tools import build_manual_ticket_draft, submit_manual_ticket


def main() -> None:
    log_path = Path("data/tool_debug.log")
    before_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""

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
        interrupt_on={
            "submit_manual_ticket": {
                "allowed_decisions": ["approve", "reject"],
                "description": "提交人工工单前请核对工单标题、正文以及完整诊断记录附件。",
            }
        },
    )
    config = {"configurable": {"thread_id": "demo-two-stage-ticket-flow"}}

    round1 = "查一下资源编码500135100000000013123839，项目已经内验了但资源系统里还是在建。"
    print("ROUND1 USER:", round1, flush=True)
    result1 = agent.invoke(
        {"messages": [{"role": "user", "content": round1}]},
        config=config,
        version="v2",
    )
    value1 = result1.value if hasattr(result1, "value") else result1
    msg1 = value1["messages"][-1].content
    print("ROUND1 FINAL_MESSAGE:", flush=True)
    print(msg1, flush=True)
    print("ROUND1_INTERRUPTS:", bool(getattr(result1, "interrupts", None)), flush=True)

    round2 = "我确认提交人工工单。"
    print("ROUND2 USER:", round2, flush=True)
    result2 = agent.invoke(
        {"messages": [{"role": "user", "content": round2}]},
        config=config,
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
            config=config,
            version="v2",
        )

    value2 = result2.value if hasattr(result2, "value") else result2
    msg2 = value2["messages"][-1].content
    print("ROUND2 FINAL_MESSAGE:", flush=True)
    print(msg2, flush=True)

    after_log = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    new_log = after_log[len(before_log) :]
    print("NEW_TOOL_DEBUG_LOG:", flush=True)
    print(new_log if new_log else "<empty>", flush=True)


if __name__ == "__main__":
    main()

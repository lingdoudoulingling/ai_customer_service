from app import build_master_agent, build_model, create_context_service, invoke_agent_once, load_config
from memory.short_term import open_postgres_checkpointer


def main() -> None:
    cfg = load_config()
    model = build_model(cfg)
    context_service = create_context_service(cfg)
    checkpoint_ns = str(cfg["CHECKPOINT_NAMESPACE"])
    user_id = "memory-demo-user"

    write_text = (
        "请记住：我是平台创新中心的张三，负责北京地区铁塔资源问题。"
        "以后回答请先给结论，再给依据。"
    )
    read_text = "你还记得我负责哪个区域吗？请按我的偏好回答。"

    with open_postgres_checkpointer(
        postgres_url=cfg["POSTGRES_URL"],
        auto_setup=bool(cfg.get("POSTGRES_AUTO_SETUP", True)),
    ) as checkpointer:
        agent = build_master_agent(model, checkpointer)
        invoke_agent_once(
            agent=agent,
            context_service=context_service,
            user_id=user_id,
            user_input=write_text,
            thread_id="memory-write-thread",
            checkpoint_ns=checkpoint_ns,
            show_reasoning=False,
        )

    print("=== restart app ===", flush=True)

    with open_postgres_checkpointer(
        postgres_url=cfg["POSTGRES_URL"],
        auto_setup=bool(cfg.get("POSTGRES_AUTO_SETUP", True)),
    ) as checkpointer:
        agent = build_master_agent(model, checkpointer)
        invoke_agent_once(
            agent=agent,
            context_service=context_service,
            user_id=user_id,
            user_input=read_text,
            thread_id="memory-read-thread",
            checkpoint_ns=checkpoint_ns,
            show_reasoning=False,
        )


if __name__ == "__main__":
    main()

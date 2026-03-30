"""Manual ticket submission tools with human approval."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TICKET_STORE = DATA_DIR / "manual_tickets.json"
DEBUG_LOG = DATA_DIR / "tool_debug.log"


def _load_tickets() -> list[dict[str, Any]]:
    if not TICKET_STORE.exists():
        return []
    with TICKET_STORE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_tickets(tickets: list[dict[str, Any]]) -> None:
    with TICKET_STORE.open("w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


def _log_debug_event(event: dict[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False)
    with DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def build_manual_ticket_draft(
    diagnosis_record: str,
    user_problem: str = "",
    target_team: str = "资源系统支撑",
    urgency: str = "medium",
) -> dict[str, Any]:
    """使用本地模板生成工单草稿，避免第二阶段再次消耗 LLM。"""
    summary_line = "资源状态同步异常，需人工介入排查。"
    for line in diagnosis_record.splitlines():
        text = line.strip()
        if text.startswith("summary:"):
            summary_line = text.split(":", 1)[1].strip() or summary_line
            break

    ticket_title = f"铁塔资源诊断工单 - {summary_line[:24]}"
    ticket_body = (
        f"问题现象：{user_problem or '用户反馈资源状态异常。'}\n\n"
        f"当前判断：{summary_line}\n\n"
        "请支撑团队根据附带的完整诊断记录继续排查并处理。"
    )
    draft = {
        "ticket_title": ticket_title,
        "target_team": target_team,
        "urgency": urgency,
        "submission_reason": "诊断已完成，建议人工处理。",
        "ticket_body": ticket_body,
        "diagnosis_record": diagnosis_record,
    }
    print(
        "[DEBUG][build_manual_ticket_draft] generated "
        f"title={ticket_title} target_team={target_team}",
        flush=True,
    )
    _log_debug_event(
        {
            "event": "build_manual_ticket_draft_called",
            "ticket_title": ticket_title,
            "target_team": target_team,
            "urgency": urgency,
        }
    )
    return draft


def submit_manual_ticket(
    ticket_title: str,
    ticket_body: str,
    diagnosis_record: str,
    target_team: str = "订单中心",
    urgency: str = "medium",
    submission_reason: str = "",
) -> dict[str, Any]:
    """
    提交人工工单。

    该工具会把 AI 生成的工单正文与完整诊断记录一起保存到本地工单池。
    建议在 deepagents 的 interrupt_on 中将该工具配置为需要人工审批后再执行。
    """
    ticket_id = f"TICKET-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "ticket_id": ticket_id,
        "ticket_title": ticket_title,
        "ticket_body": ticket_body,
        "target_team": target_team,
        "urgency": urgency,
        "submission_reason": submission_reason,
        "diagnosis_record": diagnosis_record,
        "status": "submitted",
        "submitted_at": timestamp,
    }
    print(
        "[DEBUG][submit_manual_ticket] hit "
        f"ticket_id={ticket_id} target_team={target_team} urgency={urgency}",
        flush=True,
    )
    _log_debug_event(
        {
            "event": "submit_manual_ticket_called",
            "ticket_id": ticket_id,
            "target_team": target_team,
            "urgency": urgency,
            "submission_reason": submission_reason,
            "submitted_at": timestamp,
        }
    )
    tickets = _load_tickets()
    tickets.append(payload)
    _save_tickets(tickets)
    return payload

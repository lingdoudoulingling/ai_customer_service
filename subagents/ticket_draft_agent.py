"""Ticket drafting subagent configuration."""

from typing import Any, Dict

from prompts.ticket_draft_prompt import TICKET_DRAFT_SYSTEM_PROMPT


ticket_draft_agent: Dict[str, Any] = {
    "name": "ticket-draft",
    "description": "人工工单撰写专家。根据诊断记录生成工单标题、工单正文，并附带完整诊断记录附件。",
    "system_prompt": TICKET_DRAFT_SYSTEM_PROMPT,
    "tools": [],
}


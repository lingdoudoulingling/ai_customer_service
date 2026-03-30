"""Tooling for China Tower style SOP diagnosis scenarios."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sop.scene_knowledge import get_scene_knowledge, list_scene_summaries


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DEBUG_LOG = DATA_DIR / "tool_debug.log"


def _load_json(filename: str) -> list[dict[str, Any]]:
    file_path = DATA_DIR / filename
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _retryable_lookup(fetcher, *, retries: int = 2, delay_seconds: float = 0.1) -> dict[str, Any]:
    last_error = None
    for attempt in range(1, retries + 2):
        try:
            result = fetcher()
            if isinstance(result, dict):
                result.setdefault("_attempts", attempt)
            return result
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt > retries:
                return {"error": f"工具调用失败: {exc}", "_attempts": attempt}
            time.sleep(delay_seconds)
    return {"error": f"工具调用失败: {last_error}", "_attempts": retries + 1}


def _log_debug_event(event: dict[str, Any]) -> None:
    line = json.dumps(event, ensure_ascii=False)
    with DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def list_sop_scenes() -> list[dict[str, str]]:
    """列出当前支持的问题场景，便于主智能体或诊断子智能体做路由。"""
    return list_scene_summaries()


def get_sop_scene_guide(scene_id: str) -> dict[str, Any]:
    """读取某个问题场景的 SOP 诊断指南。"""
    scene = get_scene_knowledge(scene_id)
    if not scene:
        return {"error": f"未找到场景 {scene_id}"}
    return scene


def query_order_info(order_id: str) -> dict[str, Any]:
    """根据订单编号查询 CRM 订单基础信息。"""

    def _fetch() -> dict[str, Any]:
        for row in _load_json("tower_orders.json"):
            if row.get("order_id") == order_id:
                return {"found": True, **row}
        return {"found": False, "order_id": order_id, "error": "订单不存在"}

    return _retryable_lookup(_fetch)


def query_demand_trace(order_id: str) -> dict[str, Any]:
    """模拟需求单轨迹查询，用于排查订单不存在等问题。"""

    def _fetch() -> dict[str, Any]:
        presets = {
            "ORD-BJ-HD-20260301001": {
                "found": True,
                "order_id": order_id,
                "failure_reason": "订单不存在",
                "trace_events": [
                    "2026-03-01 10:00 创建终止申请",
                    "2026-03-01 10:05 向运营商推送终止报文",
                    "2026-03-01 10:05 运营商返回: 订单不存在",
                ],
            },
            "ORD-SH-PD-20260308004": {
                "found": True,
                "order_id": order_id,
                "failure_reason": "状态非已起租",
                "trace_events": [
                    "2026-03-08 11:20 创建终止申请",
                    "2026-03-08 11:25 向运营商推送终止报文",
                    "2026-03-08 11:25 运营商返回: 当前状态非已起租",
                ],
            },
        }
        return presets.get(
            order_id,
            {"found": False, "order_id": order_id, "error": "未找到需求单轨迹"},
        )

    return _retryable_lookup(_fetch)


def query_resource_system(resource_code: str = "", asset_code: str = "") -> dict[str, Any]:
    """查询资源系统中的资源详情、绑定关系和页面可见性。"""
    print(
        "[DEBUG][query_resource_system] "
        f"resource_code={resource_code or '<empty>'} asset_code={asset_code or '<empty>'}",
        flush=True,
    )
    _log_debug_event(
        {
            "event": "query_resource_system_called",
            "resource_code": resource_code,
            "asset_code": asset_code,
        }
    )

    def _fetch() -> dict[str, Any]:
        for row in _load_json("tower_resource_system.json"):
            if resource_code and row.get("resource_code") == resource_code:
                return {"found": True, **row}
            if asset_code and row.get("asset_code") == asset_code:
                return {"found": True, **row}
        return {
            "found": False,
            "resource_code": resource_code or None,
            "asset_code": asset_code or None,
            "error": "资源不存在",
        }

    return _retryable_lookup(_fetch)


def query_public_library(pms_project_code: str) -> dict[str, Any]:
    """查询公共库内验状态及是否已向资源系统转发。"""
    print(f"[DEBUG][query_public_library] pms_project_code={pms_project_code}", flush=True)
    _log_debug_event(
        {
            "event": "query_public_library_called",
            "pms_project_code": pms_project_code,
        }
    )

    def _fetch() -> dict[str, Any]:
        for row in _load_json("tower_public_library.json"):
            if row.get("pms_project_code") == pms_project_code:
                return {
                    **row,
                    "derived_time_range": row.get("forward_time") or "最近24小时",
                }
        return {
            "pms_project_code": pms_project_code,
            "found_acceptance_status": False,
            "forwarded_to_resource_system": False,
            "forward_time": None,
            "derived_time_range": "最近24小时",
        }

    return _retryable_lookup(_fetch)


def query_resource_system_receive_log(pms_project_code: str, message_type: str = "", time_range: str = "") -> dict[str, Any]:
    """查询资源系统接收日志，用于确认报文是否到达。"""
    print(
        "[DEBUG][query_resource_system_receive_log] "
        f"pms_project_code={pms_project_code} message_type={message_type or '<empty>'}",
        flush=True,
    )
    _log_debug_event(
        {
            "event": "query_resource_system_receive_log_called",
            "pms_project_code": pms_project_code,
            "message_type": message_type,
            "time_range": time_range,
        }
    )

    def _fetch() -> dict[str, Any]:
        for row in _load_json("tower_resource_receive_logs.json"):
            if row.get("pms_project_code") == pms_project_code and (
                not message_type or row.get("message_type") == message_type
            ):
                received = bool(row.get("receive_time"))
                return {
                    "received": received,
                    "receive_time": row.get("receive_time"),
                    "matched_records_count": 1 if received else 0,
                    "message_type": row.get("message_type"),
                    "time_range": time_range,
                }
        return {
            "received": False,
            "receive_time": None,
            "matched_records_count": 0,
            "message_type": message_type,
            "time_range": time_range,
        }

    return _retryable_lookup(_fetch)


def query_resource_system_change_history(resource_code: str) -> dict[str, Any]:
    """查询资源变更履历，并归纳解绑、删除等诊断信号。"""

    def _fetch() -> dict[str, Any]:
        for row in _load_json("tower_resource_change_history.json"):
            if row.get("resource_code") == resource_code:
                records = row.get("change_records", [])
                return {
                    "resource_code": resource_code,
                    "change_records": records,
                    "has_unbind_record": any(item.get("change_type") == "asset_unbind" for item in records),
                    "has_logical_delete_record": any(item.get("change_type") == "logical_delete" for item in records),
                    "has_status_change": any(item.get("change_type") == "status_change" for item in records),
                }
        return {
            "resource_code": resource_code,
            "change_records": [],
            "has_unbind_record": False,
            "has_logical_delete_record": False,
            "has_status_change": False,
        }

    return _retryable_lookup(_fetch)


def query_pms_system_push_log(pms_project_code: str, asset_code: str = "") -> dict[str, Any]:
    """查询 PMS 是否已发起利旧流程并向资源系统推送。"""

    def _fetch() -> dict[str, Any]:
        for row in _load_json("tower_pms_push_logs.json"):
            if row.get("pms_project_code") == pms_project_code or (asset_code and row.get("asset_code") == asset_code):
                return {
                    **row,
                    "derived_time_range": row.get("push_time") or "最近24小时",
                }
        return {
            "pms_project_code": pms_project_code,
            "asset_code": asset_code or None,
            "reuse_flow_started": False,
            "pushed_to_resource_system": False,
            "push_time": None,
            "derived_time_range": "最近24小时",
        }

    return _retryable_lookup(_fetch)

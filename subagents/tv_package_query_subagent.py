"""
电视套餐查询子智能体（LangGraph 版本）。

该子智能体用于根据地区和客户级别查询可办理电视套餐。
作为 CompiledSubAgent 注册到 Deep Agents 后，会通过 task 工具被主智能体调用。
"""

from __future__ import annotations

import re
from typing import Annotated, Any, TypedDict

from deepagents.middleware.subagents import CompiledSubAgent
from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from tools.crm_tools import get_tv_packages

# 继承了MessagesState中的messages字段
class TVPackageQueryState(MessagesState):
    """电视套餐查询子图状态。"""

    city: str
    customer_level: str
    packages: list[dict[str, Any]]
    error: str


def _normalize_customer_level(raw_level: str | None) -> str:
    if not raw_level:
        return ""
    level = str(raw_level).strip().upper()
    if level == "VIP":
        return "VIP"
    if str(raw_level).strip() in {"普通", "普卡", "一般"} or level in {"NORMAL", "STANDARD"}:
        return "普通"
    return ""


def _extract_city_from_text(text: str) -> str:
    pattern = r"(北京|上海|广州|深圳|杭州|成都|武汉|西安|南京|重庆)"
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _extract_level_from_text(text: str) -> str:
    match = re.search(r"(?:客户级别|客户等级|级别|等级|customer_level)\s*[:：=]\s*([^\s,，。；;]+)", text, re.IGNORECASE)
    if match:
        return _normalize_customer_level(match.group(1))
    if "VIP" in text.upper():
        return "VIP"
    if "普通" in text:
        return "普通"
    return ""


def _extract_params_node(state: TVPackageQueryState) -> TVPackageQueryState:
    """从 task 描述里提取地区与客户级别。"""
    messages = state["messages"]
    text = str(messages[-1].content) if messages else ""
    city = _extract_city_from_text(text)
    customer_level = _extract_level_from_text(text)

    if not city or not customer_level:
        return {"error": "请提供完整参数：地区 和 客户级别（VIP/普通）。"}

    if customer_level not in {"VIP", "普通"}:
        return {"error": "客户级别仅支持 VIP 或 普通。"}

    return {"city": city, "customer_level": customer_level}


def _query_packages_node(state: TVPackageQueryState) -> TVPackageQueryState:
    """执行套餐查询。"""
    if state.get("error"):
        return {}
    try:
        packages = get_tv_packages(
            customer_level=state["customer_level"],
            city=state["city"],
            limit=5,
        )
        return {"packages": packages}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"查询失败：{exc}"}


def _format_response_node(state: TVPackageQueryState) -> TVPackageQueryState:
    """构造最终返回给主智能体的消息。"""
    if state.get("error"):
        return {"messages": [AIMessage(content=state["error"])]}

    city = state.get("city", "")
    customer_level = state.get("customer_level", "")
    packages = state.get("packages", [])
    if not packages:
        return {"messages": [AIMessage(content=f"{city} 地区暂无适合 {customer_level} 客户的电视套餐。")]}

    lines = [f"已查询到 {city} 地区适合 {customer_level} 客户的电视套餐："]
    for pkg in packages:
        lines.append(
            f"- {pkg.get('product_id')} | {pkg.get('name')} | {pkg.get('price')}元/月 | {pkg.get('description', '暂无描述')}"
        )

    return {"messages": [AIMessage(content="\n".join(lines))]}


def build_tv_package_query_graph():
    """构建并编译电视套餐查询子图。"""
    graph_builder = StateGraph(TVPackageQueryState)
    graph_builder.add_node("extract_params", _extract_params_node)
    graph_builder.add_node("query_packages", _query_packages_node)
    graph_builder.add_node("format_response", _format_response_node)

    graph_builder.add_edge(START, "extract_params")
    graph_builder.add_edge("extract_params", "query_packages")
    graph_builder.add_edge("query_packages", "format_response")
    graph_builder.add_edge("format_response", END)
    return graph_builder.compile()


tv_package_query_subagent: CompiledSubAgent = {
    "name": "tv-package-query",
    "description": "查询电视套餐。输入必须包含地区和客户级别（VIP/普通），返回该地区可办理的套餐列表。"
                   "地区参数必须用中文",
    "runnable": build_tv_package_query_graph(),
}

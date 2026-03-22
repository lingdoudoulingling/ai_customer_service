"""LangGraph implementation of product recommendation and order generation subagent."""
from __future__ import annotations
import random
import re
import time
from typing import Any, Dict, List, Optional
from deepagents import CompiledSubAgent
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt


class ProductRecommendationState(MessagesState):
    """产品推荐子智能体的状态定义"""
    # 输入参数
    customer_id: str                          # 客户ID（必需）
    customer_level: Optional[str]             # 客户等级（可选，从客户信息查询）
    city: Optional[str]                       # 城市（可选，从客户地址提取）
    # 中间数据
    customer_info: Dict[str, Any]             # 客户信息
    recommended_products: List[Dict]          # 推荐的产品列表（2个）
    selected_product: Dict[str, Any]          # 客户选择的产品
    order_details: Dict[str, Any]             # 订单详情
    # 错误信息
    error: Optional[str]                      # 错误信息


def _message_to_text(message: BaseMessage | Dict[str, Any]) -> str:
    content = message.get("content", "") if isinstance(message, dict) else message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def _extract_request_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """Extract the customer id from the isolated task message."""
    
    last_message = state["messages"][-1] if state.get("messages") else {"content": ""}
    print("-------last_message--------:",last_message)
    text = _message_to_text(last_message)
    print("-------message_to_text--------:",text)
    customer_id_match = re.search(r"(?<!\d)\d{4}(?!\d)", text)
    customer_id = customer_id_match.group(0) if customer_id_match else ""
    print("---------customer_id----------:",customer_id)
    return {"customer_id": customer_id}

def extract_city_from_address(address: str) -> str:
    """
    从地址中提取城市名称
    支持的格式：
    - "北京市朝阳区" -> "北京"
    - "上海市浦东新区" -> "上海"
    - "广州市天河区" -> "广州"
    参数：
        address: 客户地址字符串
    返回：
        城市名称（不含"市"），如果未匹配则返回空字符串
    """
    match = re.search(r'([\u4e00-\u9fa5]+)市', address)
    if match:
        return match.group(1)
    return ""


def generate_order_id() -> str:
    """
    生成唯一订单ID
    格式：ORD + 10位时间戳 + 4位随机数
    示例：ORD17012345671234
    返回：
        订单ID字符串
    """
    timestamp = str(int(time.time()))  # 10位时间戳
    random_suffix = str(random.randint(1000, 9999))  # 4位随机数
    return f"ORD{timestamp}{random_suffix}"


def validate_params_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """
    参数验证节点
    验证逻辑：
    1. customer_id 必需
    2. 如果 customer_level 未提供，从客户信息查询
    3. 如果 city 未提供，从客户地址提取
    4. 验证 customer_level 值为 "VIP" 或 "普通"
    5. 验证 city 为非空字符串
    参数：
        state: 当前状态对象
    返回：
        更新后的状态字典，包含 customer_info, customer_level, city
        或错误信息
    """
    from src.tools import get_customer_info
    # 1. 验证 customer_id 必需参数
    customer_id = state.get("customer_id")
    if not customer_id:
        return {"error": "缺少必需参数：customer_id"}
    # 2. 如果 customer_level 未提供，从客户信息查询
    
    customer_level = state.get("customer_level")
    
    city = state.get("city")
    customer_info = state.get("customer_info", {})
    # 如果需要查询客户信息（customer_level 或 city 未提供）
    if not customer_level or not city:
        customer_info = get_customer_info(customer_id)
        # 检查客户是否存在
        if "error" in customer_info:
            return {"error": "客户不存在"}
        # 从客户信息中获取 customer_level
        if not customer_level:
            customer_level = customer_info.get("customer_level")
        # 3. 如果 city 未提供，从客户地址提取城市名称
        if not city:
            address = customer_info.get("address", "")
            city = extract_city_from_address(address)
    # 4. 验证 customer_level 值为 "VIP" 或 "普通"
    if customer_level not in ["VIP", "普通"]:
        return {"error": "客户等级必须为 'VIP' 或 '普通'"}
    # 5. 验证 city 为非空字符串
    if not city or not isinstance(city, str) or city.strip() == "":
        return {"error": "城市参数不能为空"}
    # 返回更新后的状态
    print("validate_params---------city:",  city)
    return {
        "customer_info": customer_info,
        "customer_level": customer_level,
        "city": city
    }


def recommend_products_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """
    产品推荐节点
    推荐逻辑：
    1. 调用 get_tv_packages(customer_level, city, limit=2)
    2. VIP 客户优先推荐价格 >= 200 的产品
    3. 普通客户优先推荐价格 < 200 的产品
    4. 为每个产品生成推荐理由
    参数：
        state: 当前状态对象
    返回：
        更新后的状态字典，包含 recommended_products（2个产品）
        或错误信息
    """
    from src.tools import get_tv_packages
    customer_level = state.get("customer_level")
    city = state.get("city")
    try:
        # 调用 get_tv_packages 获取推荐产品
        products = get_tv_packages(customer_level, city, limit=2)
        # 为每个产品生成推荐理由
        recommended_products = []
        for product in products:
            # 生成推荐理由
            reason = _generate_recommendation_reason(product, customer_level, city)
            # 添加推荐理由到产品信息
            product_with_reason = {
                "product_id": product["product_id"],
                "name": product["name"],
                "price": product["price"],
                "cities": product["cities"],
                "description": product.get("description", ""),
                "reason": reason
            }
            recommended_products.append(product_with_reason)
        return {"recommended_products": recommended_products}
    except FileNotFoundError:
        return {"error": "产品数据文件不存在"}
    except ValueError as e:
        # 处理无可用产品等异常
        return {"error": str(e)}
    except Exception as e:
        # 处理其他未预期的异常
        return {"error": f"推荐产品时出现错误：{str(e)}"}


def _generate_recommendation_reason(product: Dict[str, Any], customer_level: str, city: str) -> str:
    """
    为产品生成推荐理由
    参数：
        product: 产品信息字典
        customer_level: 客户等级
        city: 客户所在城市
    返回：
        推荐理由字符串
    """
    reasons = []
    # 根据客户等级生成理由
    if customer_level == "VIP":
        if product["price"] >= 200:
            reasons.append("专为VIP客户打造的高端套餐")
        reasons.append("享受优质服务体验")
    else:
        if product["price"] < 200:
            reasons.append("性价比高，适合日常使用")
        reasons.append("经济实惠的选择")
    # 根据城市生成理由
    if city in product.get("cities", []):
        reasons.append(f"在{city}地区可用")
    # 根据产品描述生成理由
    description = product.get("description", "")
    if description:
        reasons.append(description)
    # 组合推荐理由
    if reasons:
        return "；".join(reasons[:3])  # 最多3条理由
    else:
        return "优质电视套餐产品"


def generate_order_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """
    订单生成节点
    生成逻辑：
    1. 从 selected_product 提取产品信息
    2. 构造订单详情（customer_id, product_id, product_name, quantity, price）
    参数：
        state: 当前状态对象
    返回：
        更新后的状态字典，包含 order_details
    """
    # 从状态中获取必需信息
    selected_product = state.get("selected_product", {})
    customer_id = state.get("customer_id")
    # 验证必需数据是否存在
    if not selected_product:
        return {"error": "未选择产品，无法生成订单"}
    if not customer_id:
        return {"error": "缺少客户ID，无法生成订单"}
    # 从 selected_product 提取产品信息
    product_id = selected_product.get("product_id")
    product_name = selected_product.get("name")
    price = selected_product.get("price", 0.0)
    quantity = 1  # 默认数量为1
    # 验证产品信息完整性
    if not product_id or not product_name:
        return {"error": "产品信息不完整，无法生成订单"}
    # 构造订单详情
    order_details = {
        "customer_id": customer_id,
        "product_id": product_id,
        "product_name": product_name,
        "quantity": quantity,
        "price": price,
    }
    # 返回更新后的状态
    return {"order_details": order_details}


def create_order_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """
    创建订单节点
    创建逻辑：
    1. 调用 create_order 工具函数
    2. 持久化订单到 data/orders.json
    3. 返回订单ID和成功消息
    参数：
        state: 当前状态对象
    返回：
        更新后的状态字典，包含订单ID和成功消息
        或错误信息
    """
    from src.tools import create_order
    # 从状态中获取订单详情
    order_details = state.get("order_details", {})
    # 验证订单详情是否存在
    if not order_details:
        return {"error": "订单详情不存在，无法创建订单"}
    # 提取订单参数
    customer_id = order_details.get("customer_id")
    product_id = order_details.get("product_id")
    quantity = order_details.get("quantity", 1)
    price = order_details.get("price", 0.0)
    # 验证必需参数
    if not customer_id or not product_id:
        return {"error": "订单详情缺少必需参数（customer_id 或 product_id）"}
    try:
        # 调用 create_order 工具函数创建订单
        order = create_order(
            customer_id=customer_id,
            product_id=product_id,
            quantity=quantity,
            price=price
        )
        # 构造成功消息
        success_message = (
            f"订单创建成功！\n"
            f"订单ID: {order['order_id']}\n"
            f"客户ID: {order['customer_id']}\n"
            f"产品ID: {order['product_id']}\n"
            f"产品名称: {order_details.get('product_name', '未知')}\n"
            f"数量: {order['quantity']}\n"
            f"价格: {order['price']}元\n"
            f"状态: {order['status']}\n"
            f"创建时间: {order['created_at']}"
        )
        # 返回订单信息和成功消息
        return {
            "messages": [AIMessage(content=success_message)],
            "order_id": order["order_id"],
            "order": order
        }
    except IOError as e:
        # 处理订单文件写入失败
        return {"error": f"订单创建失败，请稍后重试: {str(e)}"}
    except Exception as e:
        # 处理其他未预期的异常
        return {"error": f"订单创建时出现错误: {str(e)}"}


def product_selection_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """HITL product selection node implemented with interrupt/edit."""
    products = state.get("recommended_products", [])
    if not products:
        return {"error": "没有可选的推荐产品"}
    options: List[Dict[str, Any]] = [
        {
            "product_id": p.get("product_id"),
            "name": p.get("name"),
            "price": p.get("price"),
            "cities": p.get("cities", []),
            "reason": p.get("reason", ""),
        }
        for p in products
    ]
    print("----select_options-----",options)
    default_selection = options[0]["product_id"]
    hitl_payload = {
        "type": "product_selection",
        "message": "请选择推荐产品，可修改默认选项或取消?",
        "options": options,
        "default_selection": default_selection,
    }
    
    print("----hitl_payload-----", hitl_payload)
    # 此处被打断
    selection = interrupt(hitl_payload)
    # 这里没执行到
    print("-----selection-------:",selection)    
    if isinstance(selection, dict):
        action = selection.get("action")
        if selection.get("cancelled") or action == "cancel":
            return {"error": "推荐已取消"}
        if action in {"select_product", "select"}:
            selected_product_id = selection.get("product_id") or default_selection
        else:
            selected_product_id = selection.get("product_id") or default_selection
    elif isinstance(selection, str) and selection.strip():
        selected_product_id = selection.strip()
    else:
        selected_product_id = default_selection
    selected_product = next(
        (item for item in options if item.get("product_id") == selected_product_id),
        options[0],
    )
    return {"selected_product": selected_product}


def order_confirmation_node(state: ProductRecommendationState) -> Dict[str, Any]:
    """HITL order confirmation node implemented with interrupt."""
    order_details = state.get("order_details", {})
    if not order_details:
        return {"error": "订单详情不存在，无法确认"}
    confirmation_message = (
        "请确认订单信息：\n"
        f"- 客户ID: {order_details.get('customer_id', '')}\n"
        f"- 产品ID: {order_details.get('product_id', '')}\n"
        f"- 产品名称: {order_details.get('product_name', '')}\n"
        f"- 数量: {order_details.get('quantity', 1)}\n"
        f"- 价格: {order_details.get('price', 0.0)}\n"
        "是否确认创建订单?"
    )
    hitl_payload = {
        "type": "order_confirmation",
        "message": confirmation_message,
        "order_details": order_details,
    }
    decision = interrupt(hitl_payload)
    confirmed = False
    if isinstance(decision, dict):
        if decision.get("action") == "cancel":
            confirmed = False
        elif (
            decision.get("approved") is True
            or decision.get("confirmed") is True
            or decision.get("action") == "confirm"
        ):
            confirmed = True
        elif decision.get("approved") is False:
            confirmed = False
    elif isinstance(decision, bool):
        confirmed = decision
    elif isinstance(decision, str):
        confirmed = decision.strip().lower() in {"confirm", "confirmed", "yes", "y", "true", "1"}
    if not confirmed:
        return {
            "error": "订单创建已取消",
            "messages": [AIMessage(content="订单创建已取消，如需可重新发起推荐。")],
        }
    return {"order_confirmed": True}


def _route_after_validate(state: ProductRecommendationState) -> str:
    if state.get("error"):
        return END
    return "recommend_products"


def _route_after_recommend(state: ProductRecommendationState) -> str:
    if state.get("error"):
        return END
    return "product_selection"


def _route_after_product_selection(state: ProductRecommendationState) -> str:
    if state.get("error"):
        return END
    return "generate_order"


def _route_after_generate_order(state: ProductRecommendationState) -> str:
    if state.get("error"):
        return END
    return "order_confirmation"


def _route_after_order_confirmation(state: ProductRecommendationState) -> str:
    if state.get("error"):
        return END
    return "create_order"


def _create_product_recommendation_graph():
    """Build and compile product recommendation workflow graph."""
    graph = StateGraph(ProductRecommendationState)
    graph.add_node("extract_request", _extract_request_node)
    graph.add_node("validate_params", validate_params_node)
    graph.add_node("recommend_products", recommend_products_node)
    graph.add_node("product_selection", product_selection_node)
    graph.add_node("generate_order", generate_order_node)
    graph.add_node("order_confirmation", order_confirmation_node)
    graph.add_node("create_order", create_order_node)

    graph.add_edge(START, "extract_request")
    graph.add_edge("extract_request", "validate_params")

    graph.add_conditional_edges("validate_params", _route_after_validate)
    graph.add_conditional_edges("recommend_products", _route_after_recommend)
    graph.add_conditional_edges("product_selection", _route_after_product_selection)
    graph.add_conditional_edges("generate_order", _route_after_generate_order)
    graph.add_conditional_edges("order_confirmation", _route_after_order_confirmation)
    graph.add_edge("create_order", END)
    return graph.compile(checkpointer=MemorySaver())

_compiled_graph = _create_product_recommendation_graph()


def _invoke_product_recommendation_subagent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Subagent invocation entry. Return final messages or propagate interrupts."""
    thread_id = state.get("thread_id", "product-recommendation-order")
    config = {"configurable": {"thread_id": thread_id}}

    result = _compiled_graph.invoke(
        {"messages": state.get("messages", [])},
        config=config,
    )

    # 兼容 LangGraph / DeepAgents 在 interrupt 场景下返回的不同结果结构。
    if hasattr(result, "interrupts") and result.interrupts:
        return result

    result_value = getattr(result, "value", result)

    if isinstance(result_value, dict):
        messages = result_value.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return {"messages": [message]}

        if result_value.get("error"):
            return {"messages": [AIMessage(content=str(result_value["error"]))]}

    return {"messages": [AIMessage(content="No result generated yet, please retry.")]}


product_recommendation_subagent: CompiledSubAgent = {
    "name": "product-recommendation-order",
    "description": (
        "电视套餐产品推荐与订单生成专家，根据客户等级与地理位置推荐套餐，"
        "必须传入客户id,可以选择传入客户等级与地理位置"
        "并在产品选择与订单确认环节进行人工确认。"
    ),
    "runnable": RunnableLambda(_invoke_product_recommendation_subagent),
}

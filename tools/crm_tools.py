"""
MCP 工具函数模块。

提供模拟客户信息、业务进度、产品知识库和优惠策略查询能力。
"""

from typing import Any, Dict, List, Optional


def get_customer_info(customer_id: str) -> Dict[str, Any]:
    """
    查询客户基础信息
    
    根据客户 ID 查询客户的基本信息，包括姓名、联系方式、地址和客户等级。
    
    参数：
        customer_id: 客户唯一标识，4位数字格式（如 "1001"）
    
    返回：
        结果字典，包含以下字段：
        - customer_id (str): 客户唯一标识
        - name (str): 客户姓名
        - phone (str): 联系电话（已脱敏，格式如 138****8000）
        - address (str): 客户地址
        - customer_level (str): 客户等级（"VIP" 或 "普通"）
        
        如果客户不存在，返回：
        - error (str): 错误信息 "客户不存在"
    
    示例：
        >>> get_customer_info("1001")
        {
            "customer_id": "1001",
            "name": "张三",
            "phone": "138****8000",
            "address": "北京市朝阳区",
            "customer_level": "VIP"
        }
        
        >>> get_customer_info("9999")
        {"error": "客户不存在"}
    
    注意：
        - 演示系统支持的客户 ID 范围：1001-1010
        - 客户电话号码已脱敏处理，不可还原
        - VIP 客户享有优先处理权和更高服务质量
    """
    import json
    import os
    
    file_path = "data/customers.json"
    
    if not os.path.exists(file_path):
        return {"error": "客户数据文件不存在"}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            customers = json.load(f)
    except json.JSONDecodeError:
        return {"error": "客户数据文件格式错误"}
    
    if not customer_id:
        return {"error": "客户不存在"}
    
    for customer in customers:
        if customer.get("customer_id") == customer_id:
            return customer
    
    return {"error": "客户不存在"}


def get_business_progress(customer_id: str, service_type: str) -> Dict[str, Any]:
    """
    查询业务办理进度
    
    根据客户 ID 和服务类型查询业务办理的当前状态和进度详情。
    
    参数：
        customer_id: 客户唯一标识，4位数字格式（如 "1001"）
        service_type: 服务类型，可选值：
            - "broadband": 宽带服务
            - "mobile": 手机服务
    
    返回：
        结果字典，包含以下字段：
        - customer_id (str): 客户唯一标识
        - service_type (str): 服务类型
        - status (str): 当前状态，可能的值：
            * "pending": 待审核
            * "approved": 已审核
            * "installing": 安装中
            * "completed": 已完成
        - progress_detail (str): 详细进度说明
        - estimated_completion (str): 预计完成时间（格式：YYYY-MM-DD）
        
        如果查询失败，返回：
        - error (str): 错误信息
            * "参数不能为空": customer_id 或 service_type 为空
            * "未找到办理记录": 该客户没有对应服务类型的办理记录
    
    示例：
        >>> get_business_progress("1001", "broadband")
        {
            "customer_id": "1001",
            "service_type": "broadband",
            "status": "approved",
            "progress_detail": "已审核，待安装",
            "estimated_completion": "2024-02-15"
        }
        
        >>> get_business_progress("1001", "tv")
        {"error": "未找到办理记录"}
        
        >>> get_business_progress("", "broadband")
        {"error": "参数不能为空"}
    
    注意：
        - 演示系统支持的客户 ID 范围：1001-1010
        - 每个客户可能有多个服务类型的办理记录
        - 状态说明：
            * pending: 业务申请已提交，等待审核
            * approved: 业务申请已通过审核，等待后续处理
            * installing: 正在进行现场安装或配置
            * completed: 业务办理已全部完成
    """
    import json
    import os
    
    file_path = "data/business_progress.json"
    
    if not os.path.exists(file_path):
        return {"error": "业务进度数据文件不存在"}
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            progress_list = json.load(f)
    except json.JSONDecodeError:
        return {"error": "业务进度数据文件格式错误"}
    
    if not customer_id or not service_type:
        return {"error": "参数不能为空"}
    
    for progress in progress_list:
        if progress.get("customer_id") == customer_id and progress.get("service_type") == service_type:
            return progress
    
    return {"error": "未找到办理记录"}



def get_tv_packages(
    customer_level: str,
    city: str,
    limit: int = 2
) -> List[Dict[str, Any]]:
    """
    查询电视套餐产品
    
    根据客户等级和城市查询可用的电视套餐产品。VIP 客户优先推荐高价套餐（价格 >= 200元/月），
    普通客户优先推荐标准套餐（价格 < 200元/月）。
    
    参数：
        customer_level: 客户等级（"VIP" 或 "普通"）
        city: 城市名称（如 "北京"、"上海"）
        limit: 返回产品数量（默认2个）
    
    返回：
        产品列表，每个产品包含：
        - product_id (str): 产品ID
        - name (str): 产品名称
        - price (float): 价格（元/月）
        - cities (list): 适用城市列表
        - customer_levels (list): 适用客户等级列表
        - description (str): 产品描述
    
    异常：
        - FileNotFoundError: 产品数据文件不存在
        - ValueError: 产品数据文件格式错误或该地区暂无可用电视套餐
    
    示例：
        >>> get_tv_packages("VIP", "北京", limit=2)
        [
            {
                "product_id": "TV001",
                "name": "VIP 尊享电视套餐",
                "price": 299.0,
                "cities": ["北京", "上海", "广州"],
                "customer_levels": ["VIP"],
                "description": "包含300+高清频道"
            }
        ]
    
    注意：
        - VIP 客户优先推荐价格 >= 200 的产品
        - 普通客户优先推荐价格 < 200 的产品
        - 产品必须在其 cities 字段中包含指定城市
        - 返回的产品数量不超过 limit 参数
    """
    import json
    import os
    
    # 读取产品数据文件
    file_path = "data/tv_packages.json"
    
    if not os.path.exists(file_path):
        raise FileNotFoundError("产品数据文件不存在")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_products = json.load(f)
    except json.JSONDecodeError:
        raise ValueError("产品数据文件格式错误")
    
    # 验证产品数据完整性
    for product in all_products:
        required_fields = ["product_id", "name", "price", "cities", "customer_levels"]
        if not all(field in product for field in required_fields):
            raise ValueError("产品数据文件格式错误")
    
    # 根据城市过滤产品
    city_filtered = [
        p for p in all_products
        if city in p.get("cities", [])
    ]
    
    if not city_filtered:
        raise ValueError("该地区暂无可用电视套餐")
    
    # 根据客户等级过滤和排序产品
    if customer_level == "VIP":
        # VIP 客户优先推荐价格 >= 200 的产品
        suitable_products = [p for p in city_filtered if p["price"] >= 200]
        # 按价格降序排序
        suitable_products.sort(key=lambda x: x["price"], reverse=True)
    else:  # 普通客户
        # 普通客户优先推荐价格 < 200 的产品
        suitable_products = [p for p in city_filtered if p["price"] < 200]
        # 按价格升序排序
        suitable_products.sort(key=lambda x: x["price"])
    
    # 如果没有符合价格范围的产品，返回所有城市可用产品
    if not suitable_products:
        suitable_products = city_filtered
        suitable_products.sort(key=lambda x: x["price"])
    
    # 返回最多 limit 个产品
    return suitable_products[:limit]


def create_order(
    customer_id: str,
    product_id: str,
    quantity: int = 1,
    price: float = 0.0
) -> Dict[str, Any]:
    """
    创建订单
    
    创建新的电视套餐订单并持久化到 JSON 文件。订单会被追加到现有订单列表中，
    不会覆盖已有订单。
    
    参数：
        customer_id: 客户ID
        product_id: 产品ID
        quantity: 数量（默认1）
        price: 价格
    
    返回：
        订单对象，包含：
        - order_id (str): 订单ID（格式：ORD + 10位时间戳 + 4位随机数）
        - customer_id (str): 客户ID
        - product_id (str): 产品ID
        - quantity (int): 数量
        - price (float): 价格
        - status (str): 状态（"confirmed"）
        - created_at (str): 创建时间（YYYY-MM-DD HH:MM:SS）
    
    异常：
        - IOError: 订单文件写入失败
    
    示例：
        >>> create_order("1001", "TV001", quantity=1, price=299.0)
        {
            "order_id": "ORD17012345671234",
            "customer_id": "1001",
            "product_id": "TV001",
            "quantity": 1,
            "price": 299.0,
            "status": "confirmed",
            "created_at": "2024-02-15 14:30:00"
        }
    
    注意：
        - 订单ID格式：ORD + 10位时间戳 + 4位随机数
        - 订单状态初始值为 "confirmed"
        - 订单会追加到 data/orders.json 文件
        - 如果订单文件不存在，会自动创建并初始化为空列表
        - JSON 文件使用 UTF-8 编码，缩进为 2 个空格
    """
    import json
    import os
    import time
    import random
    from datetime import datetime
    
    # 生成唯一订单ID（ORD + 10位时间戳 + 4位随机数）
    timestamp = str(int(time.time()))  # 10位时间戳
    random_suffix = str(random.randint(1000, 9999))  # 4位随机数
    order_id = f"ORD{timestamp}{random_suffix}"
    
    # 生成创建时间
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 构造订单对象
    order = {
        "order_id": order_id,
        "customer_id": customer_id,
        "product_id": product_id,
        "quantity": quantity,
        "price": price,
        "status": "confirmed",
        "created_at": created_at
    }
    
    # 订单文件路径
    file_path = "data/orders.json"
    
    # 读取现有订单列表
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                orders = json.load(f)
        except json.JSONDecodeError:
            # 如果文件格式错误，初始化为空列表
            orders = []
    else:
        # 如果文件不存在，初始化为空列表
        orders = []
        # 确保 data 目录存在
        os.makedirs("data", exist_ok=True)
    
    # 追加新订单到列表
    orders.append(order)
    
    # 写入 JSON 文件（UTF-8 编码，缩进 2 个空格）
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise IOError(f"订单创建失败，请稍后重试: {str(e)}")
    
    return order

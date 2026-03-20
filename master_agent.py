"""
主智能体创建模块

使用 deepagents 框架的 create_deep_agent 函数创建主智能体
主智能体负责意图识别、任务规划和子智能体协调
"""

from typing import List, Callable, Dict, Any
from deepagents import create_deep_agent
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver



def create_master_agent(
    model: str | BaseChatModel,
    tools: List[Callable],
    subagents: List[Dict[str, Any]],
    system_prompt: str,
    memory_files: List[str]
) -> Any:
    """
    创建主智能体
    
    使用 deepagents 框架创建配置完整的主智能体，包含：
    - 意图识别能力（通过 system_prompt 引导）
    - 任务规划能力（使用内置的 write_todos 工具）
    - 子智能体调用能力（使用内置的 task() 工具）
    - 记忆管理能力（使用 MemoryMiddleware 和 Checkpointer）
    
    参数：
        model: LLM 模型名称（如 "anthropic:claude-sonnet-4"）
        tools: MCP 工具函数列表
        subagents: 子智能体配置列表，每个配置包含 name, description, system_prompt, tools
        system_prompt: 系统提示词，引导 LLM 进行意图识别和任务协调
        memory_files: 持久记忆文件路径列表（如 ["./LTM.md"]）
    
    返回：
        配置好的 agent 实例，可以通过 invoke() 方法调用
    
    示例：
        >>> agent = create_master_agent(
        ...     model="anthropic:claude-sonnet-4",
        ...     tools=[get_customer_info, get_business_progress],
        ...     subagents=[customer_agent, business_agent],
        ...     system_prompt="你是智能助手...",
        ...     memory_files=["./LTM.md"]
        ... )
        >>> result = agent.invoke(
        ...     {"messages": [{"role": "user", "content": "查询客户1001"}]},
        ...     config={"configurable": {"thread_id": "session_001"}}
        ... )
    
    注意：
        - 主智能体自动获得 write_todos 和 task() 等内置工具
        - 使用 MemorySaver 作为 checkpointer 实现短期记忆
        - memory_files 中的文件内容会被加载为持久记忆
        - 所有对话历史和执行结果自动保存到 checkpoint
    """
    agent = create_deep_agent(
        model=model,
        tools=tools,
        subagents=subagents,
        system_prompt=system_prompt,
        checkpointer=MemorySaver(),
        memory=memory_files,
    )
    return agent

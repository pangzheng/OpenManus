from abc import ABC, abstractmethod
from typing import Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.llm import LLM
from app.schema import AgentState, Memory

class ReActAgent(BaseAgent, ABC):
    """
    ReActAgent类继承自BaseAgent和ABC（抽象基类），意味着它是一个抽象类，包含抽象方法
    """
    # 代理的名称
    name: str
    # 描代理的描述述
    description: Optional[str] = None
    # 系统提示
    system_prompt: Optional[str] = None
    # 下一步提示
    next_step_prompt: Optional[str] = None

    # 语言模型实例
    llm: Optional[LLM] = Field(default_factory=LLM)
    # 记忆实例
    memory: Memory = Field(default_factory=Memory)
    # 代理的状态，AgentState类型，初始值为AgentState.IDLE（空闲状态）
    state: AgentState = AgentState.IDLE

    # 最大步骤数，整数类型，默认值为10
    max_steps: int = 10
    # 当前步骤数，整数类型，默认值为0
    current_step: int = 0

    @abstractmethod
    # 抽象异步方法 think，
    async def think(self) -> bool:
        """用于处理当前状态并决定下一步行动，返回布尔值"""

    @abstractmethod
    # 抽象异步方法 act，
    async def act(self) -> str:
        """用于执行已决定的行动，返回字符串"""

    # 异步方法 step，：思考并行动，返回字符串
    async def step(self) -> str:
        """用于执行单个步骤"""
        should_act = await self.think()
        # 如果think()返回正常,执行act()
        if not should_act:
            return "Thinking complete - no action needed"
        return await self.act()

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Memory, Message


class BaseAgent(BaseModel, ABC):
    """
    用于管理代理状态和执行的基础类。
    提供状态转换、记忆管理和基于步骤的执行循环的基本功能。
    子类必须实现 `step` 方法。
    """

    # 核心属性
    ## 代理的名称，必填字段
    name: str = Field(..., description="Unique name of the agent") 
    ## 代理的描述，可选字段
    description: Optional[str] = Field(None, description="Optional agent description") 

    # 提示信息
    # 系统级指令提示词，可选字段
    system_prompt: Optional[str] = Field(
        None, description="System-level instruction prompt"
    )
    # 用于确定下一步行动的提示，可选字段
    next_step_prompt: Optional[str] = Field(
        None, description="Prompt for determining next action"
    )

    # 依赖
    # 语言模型实例，默认使用LLM类的默认构造函数创建
    llm: LLM = Field(default_factory=LLM, description="Language model instance")
    # 代理的记忆存储，默认使用Memory类的默认构造函数创建
    memory: Memory = Field(default_factory=Memory, description="Agent's memory store")
    # 代理的当前状态，默认是IDLE状态
    state: AgentState = Field(
        default=AgentState.IDLE, description="Current agent state"
    )

    # 执行控制
    # 执行的最大步数，默认10步
    max_steps: int = Field(default=10, description="Maximum steps before termination")
    # 当前执行的步骤，默认从0开始
    current_step: int = Field(default=0, description="Current step in execution")

    # 检测到重复内容的阈值，用于判断是否陷入死循环
    duplicate_threshold: int = 2

    class Config:
        arbitrary_types_allowed = True # 允许任意类型，增加灵活性
        extra = "allow"  # 允许子类有额外的字段

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """如果未提供，则使用默认设置初始化代理。"""
        # 如果llm未设置或不是LLM类型，创建一个新的LLM实例
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower()) 
        # 如果memory不是Memory类型，创建一个新的Memory实例    
        if not isinstance(self.memory, Memory): 
            self.memory = Memory()
        return self

    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """用于安全代理状态转换的上下文管理器。

        Args:
            new_state: 要在上下文中转换到的状态。

        Yields:
            None: 允许在新状态下执行。

        Raises:
            ValueError: 如果 new_state 无效。
        """

        # 检查新状态是否为 AgentState 类型
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        # 保存当前状态
        previous_state = self.state
        # 转换到新状态
        self.state = new_state

        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # 在失败时转到ERROR状态
            raise e
        finally:
            self.state = previous_state  # 还原为先前的状态

    def update_memory(
        self,
        role: Literal["user", "system", "assistant", "tool"],
        content: str,
        **kwargs,
    ) -> None:
        """向代理的记忆中添加一条消息。

        Args:
            role: 消息发送者的角色（user、system、assistant、tool）。
            content: 消息内容。
            **kwargs: 其他参数（例如，tool消息的tool_call_id）。

        Raises:
            ValueError: 如果角色不受支持。
        """
        # 消息角色映射到相应的消息创建函数
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        # 检查角色是否在映射中
        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")

        msg_factory = message_map[role]
        msg = msg_factory(content, **kwargs) if role == "tool" else msg_factory(content)
        # 创建消息并添加到记忆中
        self.memory.add_message(msg)

    async def run(self, request: Optional[str] = None) -> str:
        """异步执行代理的主循环。

        Args:
            request: 可选的初始用户请求以进行处理。

        Returns:
            一个总结执行结果的字符串。

        Raises:
            RuntimeError: 如果代理在开始时不是IDLE状态。
        """

        # 检查代理,如果不处于IDLE状态，报错
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        # 如果有请求，将其添加到记忆中
        if request:
            self.update_memory("user", request)

        # 结果创建一个列表
        results: List[str] = []
        
        async with self.state_context(AgentState.RUNNING):
            while (
                self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                # 执行一步并获取结果
                step_result = await self.step()

                # 检查是否处于停滞状态
                if self.is_stuck():
                    self.handle_stuck_state() # 如果陷入停滞循环，处理该状态

                # 将步骤结果添加到结果列表中
                results.append(f"Step {self.current_step}: {step_result}")

            # 如果达到最大步数，添加终止信息
            if self.current_step >= self.max_steps:
                results.append(f"Terminated: Reached max steps ({self.max_steps})")
        # 返回结果字符串
        return "\n".join(results) if results else "No steps executed"

    @abstractmethod
    async def step(self) -> str:
        """在代理的工作流程中执行单个步骤。

        子类必须实现此方法以定义特定行为。
        """
    def handle_stuck_state(self):
        """通过添加一个改变策略的提示来处理停滞状态"""
        # 观察到重复响应。考虑新策略并避免重复已经尝试过的无效路径。
        stuck_prompt = "\
        Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        # 代理检测到卡滞状态，添加了提示
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """通过检测重复内容检查代理是否陷入循环"""
        # 如果内存中的消息数少于2条，不可能陷入死循环
        if len(self.memory.messages) < 2:
            return False
        
        # 如果最后一条消息没有内容，不可能陷入死循环
        last_message = self.memory.messages[-1]
        if not last_message.content:
            return False

        # 统计相同内容的出现次数
        duplicate_count = sum(
            1
            for msg in reversed(self.memory.messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        # 如果重复次数达到阈值，认为陷入死循环
        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """从代理的记忆中检索消息列表。"""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """在代理的记忆中设置消息列表。"""
        self.memory.messages = value

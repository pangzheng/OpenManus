from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# 定义AgentState枚举类，继承自str和Enum
class AgentState(str, Enum):
    """Agent执行状态"""

    # 空闲状态
    IDLE = "IDLE"
    # 运行状态
    RUNNING = "RUNNING"
    # 完成状态
    FINISHED = "FINISHED"
    # 错误状态
    ERROR = "ERROR"

# 定义Function数据模型类，继承自BaseModel
class Function(BaseModel):
    # 名字
    name: str
    # 参数
    arguments: str

# 定义ToolCall数据模型类，继承自BaseModel
class ToolCall(BaseModel):
    """表示消息中的工具/函数调用"""
    # 工具ID
    id: str
    # 调用类型，默认为"function"
    type: str = "function"
    # 函数相关信息
    function: Function

# 定义Message数据模型类，继承自BaseModel
class Message(BaseModel):
    """表示对话中的聊天消息"""

    # 消息角色，只能是"system", "user", "assistant", "tool"中的一个
    role: Literal["system", "user", "assistant", "tool"] = Field(...)
    # 消息内容，可选，默认为None
    content: Optional[str] = Field(default=None)
    # 工具调用列表，可选，默认为None
    tool_calls: Optional[List[ToolCall]] = Field(default=None)
    # 名字
    name: Optional[str] = Field(default=None)
    # 工具调用标识，可选，默认为None
    tool_call_id: Optional[str] = Field(default=None)

    # 重载加法运算符，支持Message + list或Message + Message的操作
    def __add__(self, other) -> List["Message"]:
        """支持 Message + list 或 Message + Message 的操作"""
        if isinstance(other, list):
            # 如果other是列表，将自身添加到列表开头并返回
            return [self] + other
        elif isinstance(other, Message):
            # 如果other是Message，将自身和other组成列表并返回
            return [self, other]
        else:
            # 否则抛出类型错误
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )
    
    # 重载反向加法运算符，支持list + Message的操作
    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作"""
        if isinstance(other, list):
            # 如果other是列表，将自身添加到列表末尾并返回
            return other + [self]
        else:
            # 否则抛出类型错误
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(other).__name__}' and '{type(self).__name__}'"
            )

    # 将消息转换为字典格式
    def to_dict(self) -> dict:
        message = {"role": self.role}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            message["tool_calls"] = [tool_call.dict() for tool_call in self.tool_calls]
        if self.name is not None:
            message["name"] = self.name
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        return message

    @classmethod
    def user_message(cls, content: str) -> "Message":
        """类方法，创建用户消息"""
        return cls(role="user", content=content)

    @classmethod
    def system_message(cls, content: str) -> "Message":
        """类方法，创建系统消息"""
        return cls(role="system", content=content)

    @classmethod
    def assistant_message(cls, content: Optional[str] = None) -> "Message":
        """类方法，创建助手消息"""
        return cls(role="assistant", content=content)

    @classmethod
    def tool_message(cls, content: str, name, tool_call_id: str) -> "Message":
        """类方法，创建工具消息"""
        return cls(role="tool", content=content, name=name, tool_call_id=tool_call_id)

    @classmethod
    def from_tool_calls(
        cls, tool_calls: List[Any], content: Union[str, List[str]] = "", **kwargs
    ):
        """Create ToolCallsMessage from raw tool calls.

        Args:
            tool_calls: Raw tool calls from LLM
            content: Optional message content
        """

        """
        从原始工具调用创建 ToolCallsMessage。 

        Args: 
            tool_calls: 由LLM返回的原始工具调用 
            content: 可选的消息内容 
        """
        formatted_calls = [
            {"id": call.id, "function": call.function.model_dump(), "type": "function"}
            for call in tool_calls
        ]
        return cls(
            role="assistant", content=content, tool_calls=formatted_calls, **kwargs
        )

# 定义Memory数据模型类，继承自BaseModel
class Memory(BaseModel):
    # 消息列表，默认使用空列表
    messages: List[Message] = Field(default_factory=list)
    # 最大消息数，默认100
    max_messages: int = Field(default=100)

    def add_message(self, message: Message) -> None:
        """向记忆中添加一条消息"""
        self.messages.append(message)
        # 可选：实现消息数量限制
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def add_messages(self, messages: List[Message]) -> None:
        """向记忆中添加多条消息"""
        self.messages.extend(messages)

    def clear(self) -> None:
        """清空所有消息"""
        self.messages.clear()

    def get_recent_messages(self, n: int) -> List[Message]:
        """获取最近的n条消息"""
        return self.messages[-n:]

    def to_dict_list(self) -> List[dict]:
        """将消息转换为字典列表"""
        return [msg.to_dict() for msg in self.messages]

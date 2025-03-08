#从 **  模块中导入 ** 类
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

# 定义抽象基类 BaseTool
class BaseTool(ABC, BaseModel):
    # 工具的名称，字符串类型
    name: str
    # 工具的描述，字符串类型
    description: str
    # 工具的参数，字典类型，默认值为 None
    parameters: Optional[dict] = None

    # 内部类 Config，用于配置 pydantic 模型的行为
    class Config:
        arbitrary_types_allowed = True

    # 定义 __call__ 异步可调用方法，它会调用 execute 方法
    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        """执行给定参数下的工具"""
        return await self.execute(**kwargs)
    
    # 定义 execute 抽象异步方法，需要子类去实现
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        """执行给定参数下的工具"""
    
    # 将工具转换为函数调用格式的方法
    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

# 定义表示工具执行结果的数据模型类 ToolResult
class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    # 工具执行的输出，任意类型，默认值为 None
    output: Any = Field(default=None)
    # 工具执行过程中发生的错误，字符串类型，默认值为 None
    error: Optional[str] = Field(default=None)
     # 系统相关信息，字符串类型，默认值为 None
    system: Optional[str] = Field(default=None)

    # 内部类 Config，用于配置 pydantic 模型的行为
    class Config:
        arbitrary_types_allowed = True

    # 定义布尔值判断方法，只要有任何一个字段有值就返回 True
    def __bool__(self):
        return any(getattr(self, field) for field in self.__fields__)

    # 定义加法运算符重载方法，用于合并两个 ToolResult 对象
    def __add__(self, other: "ToolResult"):
        # 定义一个内部函数用于合并字段
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                     # 如果两个字段都有值且 concatenate 为 True，则拼接两个字段 为返回值
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field
        
        # 返回一个新的 ToolResult 对象，包含合并后的字段
        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            system=combine_fields(self.system, other.system),
        )

    # 定义字符串表示方法，如果有错误则返回错误信息，否则返回输出
    def __str__(self):
        return f"Error: {self.error}" if self.error else self.output

     # 定义replace方法用于替换给定字段
    def replace(self, **kwargs):
        """Returns a new ToolResult with the given fields replaced."""
        # return self.copy(update=kwargs)
        return type(self)(**{**self.dict(), **kwargs})

# 定义 CLIResult 类，它继承自 ToolResult，用于表示可渲染为 CLI 输出的工具结果
class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""

# 定义 ToolFailure 类，它继承自 ToolResult，用于表示工具执行失败的结果
class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""
    
# 定义 AgentAwareTool 类，它有一个可选的 agent 属性
class AgentAwareTool:
    agent: Optional = None

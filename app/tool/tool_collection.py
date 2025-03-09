"""该模块用于管理多个工具的集合类"""
from typing import Any, Dict, List

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolFailure, ToolResult


class ToolCollection:
    """一组定义的工具。"""
    # 初始化方法，接收多个BaseTool类型的工具实例
    def __init__(self, *tools: BaseTool):
        # 将传入的工具实例保存到实例属性tools中，tools是一个元组
        self.tools = tools
        # 使用字典推导式创建一个工具名称到工具实例的映射字典tool_map
        self.tool_map = {tool.name: tool for tool in tools}
    
    # 使该类实例可迭代，返回工具实例元组的迭代器
    def __iter__(self):
        return iter(self.tools)

    # 将每个工具转换为参数格式的方法，返回一个列表，列表中的每个元素是一个字典
    def to_params(self) -> List[Dict[str, Any]]:
        # 使用列表推导式，调用每个工具的to_param方法，将结果收集到列表中返回
        return [tool.to_param() for tool in self.tools]

    # 异步执行指定名称工具的方法，接收工具名称name和工具输入参数tool_input
    async def execute(
        self, *, name: str, tool_input: Dict[str, Any] = None
    ) -> ToolResult:
        # 从tool_map字典中获取指定名称的工具实例
        tool = self.tool_map.get(name)
        # 如果未找到指定名称的工具
        if not tool:
            # 返回工具执行失败结果，错误信息为指定工具无效
            return ToolFailure(error=f"Tool {name} is invalid")
        try:
            # 异步调用工具实例，传入tool_input参数（如果有），并等待执行结果
            result = await tool(**tool_input)
            # 返回工具执行结果
            return result
        # 如果在工具执行过程中捕获到ToolError异常
        except ToolError as e:
            # 返回工具执行失败结果，错误信息为异常中的消息
            return ToolFailure(error=e.message)

    async def execute_all(self) -> List[ToolResult]:
        """按顺序依次执行集合中的所有工具。"""
        # 初始化一个空列表，用于存储所有工具的执行结果
        results = []
        # 遍历工具实例元组中的每个工具
        for tool in self.tools:
            try:
                # 异步调用工具实例，并等待执行结果
                result = await tool()
                # 将工具执行结果添加到results列表中
                results.append(result)
            # 如果在工具执行过程中捕获到ToolError异常
            except ToolError as e:
                # 将工具执行失败结果添加到results列表中，错误信息为异常中的消息
                results.append(ToolFailure(error=e.message))
        # 返回包含所有工具执行结果（成功或失败）的列表        
        return results
    
    # 根据工具名称获取工具实例的方法
    def get_tool(self, name: str) -> BaseTool:
        # 从tool_map字典中获取指定名称的工具实例并返回，如果未找到则返回None
        return self.tool_map.get(name)
    
    # 添加单个工具的方法
    def add_tool(self, tool: BaseTool):
        # 将传入的工具实例添加到tools元组中
        self.tools += (tool,)
        # 将工具名称和工具实例添加到tool_map字典中
        self.tool_map[tool.name] = tool
        # 返回当前ToolCollection实例，以便支持链式调用
        return self

    # 添加多个工具的方法
    def add_tools(self, *tools: BaseTool):
        # 遍历传入的每个工具实例
        for tool in tools:
            # 调用add_tool方法添加每个工具
            self.add_tool(tool)
        # 返回当前ToolCollection实例，以便支持链式调用
        return self

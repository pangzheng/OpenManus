import json
from typing import Any, List, Literal

from pydantic import Field

from app.agent.react import ReActAgent
from app.logger import logger
from app.prompt.toolcall import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.schema import AgentState, Message, ToolCall
from app.tool import CreateChatCompletion, Terminate, ToolCollection

# 需要工具调用但未提供
TOOL_CALL_REQUIRED = "Tool calls required but none provided"

class ToolCallAgent(ReActAgent):
    """定义 ToolCallAgent 类，继承自 ReActAgent，一个处理工具/函数调用的基础代理类，具有增强的抽象层"""

    # 名字
    name: str = "toolcall"
    # 描述，一个可以执行工具调用的代理。
    description: str = "an agent that can execute tool calls."

    # 系统提示词，位置 toolcall.py
    system_prompt: str = SYSTEM_PROMPT
    # 下一步提示词，位置 toolcall.py
    next_step_prompt: str = NEXT_STEP_PROMPT

    # 可用工具集合，初始化时包含创建聊天完成和终止工具
    available_tools: ToolCollection = ToolCollection(
        CreateChatCompletion(), Terminate()
    )

    # 工具选择模式，有"none"（不使用工具）、"auto"（自动决定是否使用工具）、"required"（必须使用工具），默认为"auto"
    tool_choices: Literal["none", "auto", "required"] = "auto"
    # 特殊工具名称列表，默认包含终止工具的名称
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])
    # 工具调用列表，默认为空列表
    tool_calls: List[ToolCall] = Field(default_factory=list)
    # 最大步骤数
    max_steps: int = 30

    async def think(self) -> bool:
        """处理当前状态并使用工具决定下一步行动"""
        # 如果存在下一步提示，添加用户消息到消息列表
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]

        # 使用语言模型获取带有工具选项的响应
        response = await self.llm.ask_tool(
            messages=self.messages,
            # 如果存在系统提示，添加系统消息
            system_msgs=[Message.system_message(self.system_prompt)]
            if self.system_prompt
            else None,
            # 可用工具的参数
            tools=self.available_tools.to_params(),
            # 工具选择模式
            tool_choice=self.tool_choices,
        )
        # 更新工具调用列表
        self.tool_calls = response.tool_calls

        # 日志响应信息
        logger.info(f"✨ {self.name}'s thoughts: {response.content}")
        logger.info(
            f"🛠️ {self.name} selected {len(response.tool_calls) if response.tool_calls else 0} tools to use"
        )

        if response.tool_calls:
            logger.info(
                f"🧰 Tools being prepared: {[call.function.name for call in response.tool_calls]}"
            )

        # 处理不同的工具选择模式
        try:
            # 选择模式等于 none
            if self.tool_choices == "none":
                # 实验日志
                logger.info(
                        f" this is tool choices {self.tool_choices} ")
                # 如果在不允许使用工具时尝试使用工具，记录警告
                # "嗯，{self.name} 在工具不可用时尝试使用工具!   
                if response.tool_calls:
                    logger.warning(
                        f"🤔 Hmm, {self.name} tried to use tools when they weren't available!"
                    )
                # 如果有响应内容，添加到记忆中并返回 True
                if response.content:
                    self.memory.add_message(Message.assistant_message(response.content))
                    
                    return True
                return False

            
            # 创建并添加助手消息
            assistant_msg = (
                Message.from_tool_calls(
                    content=response.content, tool_calls=self.tool_calls
                )
                if self.tool_calls
                else Message.assistant_message(response.content)
            )
            
            # 添加助手消息到记忆中
            self.memory.add_message(assistant_msg)
            
            # 实验日志,打印 assistant_msg
            # logger.info(f"add assistant message  {assistant_msg} to memory")

            # 如果工具选择模式为"required"且没有工具调用，返回True，将在act()中处理
            if self.tool_choices == "required" and not self.tool_calls:
                return True  # 将在act()中处理

            # 如果工具选择模式为"auto"且没有工具调用，根据是否有响应内容返回
            if self.tool_choices == "auto" and not self.tool_calls:
                return bool(response.content)
            
            # 实验日志,打印记忆最后几条
            logger.info(f" memory is  {self.memory.get_recent_messages}")

            # 如果有工具调用，返回True
            return bool(self.tool_calls)
        except Exception as e:
            # 记录思考过程中的错误"🚨 噢哦！{self.name} 的思维过程遇到了问题：{e}"
            logger.error(f"🚨 Oops! The {self.name}'s thinking process hit a snag: {e}")
            # 记忆体添加消息，"在处理过程中遇到错误：{str(e)}""
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False

    async def act(self) -> str:
        """执行工具调用并处理其结果"""
        # 如果没有工具调用
        if not self.tool_calls:
            # 如果工具选择模式为"required"，抛出异常
            if self.tool_choices == "required":
                raise ValueError(TOOL_CALL_REQUIRED)

            # 返回最后一条消息的内容，如果没有则返回提示信息"没有内容或命令需要执行
            return self.messages[-1].content or "No content or commands to execute"
        # 创建结果列表
        results = []
        # 遍历工具调用列表并执行每个工具
        for command in self.tool_calls:
            result = await self.execute_tool(command)
            # 记录工具执行完成信息
            logger.info(
                f"🎯 Tool '{command.function.name}' completed its mission! Result: {result}"
            )

            # 添加工具响应到记忆中
            tool_msg = Message.tool_message(
                content=result, tool_call_id=command.id, name=command.function.name
            )
            self.memory.add_message(tool_msg)
            results.append(result)

        return "\n\n".join(results)

    async def execute_tool(self, command: ToolCall) -> str:
        """使用健壮的错误处理机制执行单个工具调用"""
        # 检查命令格式是否有效
        if not command or not command.function or not command.function.name:
            return "Error: Invalid command format"

        name = command.function.name
        
        # 检查工具是否在可用工具列表中
        if name not in self.available_tools.tool_map:
            return f"Error: Unknown tool '{name}'"

        try:
            # 解析工具参数
            args = json.loads(command.function.arguments or "{}")

            # 记录激活工具信息
            logger.info(f"🔧 Activating tool: '{name}'...")
            # 执行工具
            result = await self.available_tools.execute(name=name, tool_input=args)

            # 格式化结果用于显示
            observation = (
                f"Observed output of cmd `{name}` executed:\n{str(result)}"
                if result
                else f"Cmd `{name}` completed with no output"
            )

            # 处理特殊的工具，如 `finish`
            await self._handle_special_tool(name=name, result=result)

            # 测试日志
            logger.info(f"🔧 Activating tool result: '{observation}'")

            return observation
        except json.JSONDecodeError:
            # 记录解析参数错误信息
            error_msg = f"Error parsing arguments for {name}: Invalid JSON format"
            logger.error(
                f"📝 Oops! The arguments for '{name}' don't make sense - invalid JSON, arguments:{command.function.arguments}"
            )
            return f"Error: {error_msg}"
        # 记录工具执行错误信息
        except Exception as e:
            error_msg = f"⚠️ Tool '{name}' encountered a problem: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        """处理特殊工具的执行和状态变化"""
        # 检查是否是特殊工具
        if not self._is_special_tool(name):
            return
        # 检查是否应该结束执行
        if self._should_finish_execution(name=name, result=result, **kwargs):
            # 设置代理状态为已完成
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        """确定是否应通过工具执行来结束代理"""
        return True

    def _is_special_tool(self, name: str) -> bool:
        """检查工具名称是否在特殊工具列表中"""
        return name.lower() in [n.lower() for n in self.special_tool_names]

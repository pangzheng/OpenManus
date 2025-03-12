import time
from typing import Dict, List, Literal, Optional

from pydantic import Field, model_validator

from app.agent.toolcall import ToolCallAgent
from app.logger import logger
from app.prompt.planning import NEXT_STEP_PROMPT, PLANNING_SYSTEM_PROMPT
from app.schema import Message, ToolCall
from app.tool import PlanningTool, Terminate, ToolCollection


class PlanningAgent(ToolCallAgent):
    """
    一个创建和管理解决任务计划的代理。
    这个代理使用规划工具来创建和管理结构化的计划，并通过个别步骤跟踪进度直至任务完成
    """
    # 名称
    name: str = "planning"
    # 描述，一个创建和管理解决任务计划的代理。
    description: str = "An agent that creates and manages plans to solve tasks"

    # 用于设置系统提示信息，planning.py 的提示词
    system_prompt: str = PLANNING_SYSTEM_PROMPT
    # 用于设置下一步提示信息，planning.py 的提示词
    next_step_prompt: str = NEXT_STEP_PROMPT

    # 可用工具集合，默认使用PlanningTool和Terminate工具
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(PlanningTool(), Terminate())
    )
    # 工具选择模式，"none", "auto", "required" 之一，默认为 "auto"
    tool_choices: Literal["none", "auto", "required"] = "auto"
    # 特殊工具名称列表，默认为Terminate工具的名称
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    # 已调用工具列表，默认为空列表
    tool_calls: List[ToolCall] = Field(default_factory=list)

    # 当前活动计划的ID，初始为None
    active_plan_id: Optional[str] = Field(default=None)

    # 向字典中添加项以跟踪每个工具调用的步骤状态,用于跟踪每个工具调用的步骤状态的字典
    step_execution_tracker: Dict[str, Dict] = Field(default_factory=dict)
    # 当前步骤索引，初始为None
    current_step_index: Optional[int] = None

    # 最大步骤数
    max_steps: int = 30

    @model_validator(mode="after")
    def initialize_plan_and_verify_tools(self) -> "PlanningAgent":
        """
        使用默认计划ID初始化代理并验证所需工具。
        生成一个以 "plan_" 开头并加上当前时间戳的计划ID
        并确保可用工具中包含计划工具。
        """
        self.active_plan_id = f"plan_{int(time.time())}"

        if "planning" not in self.available_tools.tool_map:
            self.available_tools.add_tool(PlanningTool())

        return self

    async def think(self) -> bool:
        """
        根据计划状态决定下一步行动。
        如果有活动计划 ID，则在提示信息中添加当前计划状态。
        获取当前步骤索引，并在思考后，如果决定执行一个非计划和非特殊工具的调用，则记录其与当前步骤的关联。
        """
        prompt = (
            f"CURRENT PLAN STATUS:\n{await self.get_plan()}\n\n{self.next_step_prompt}"
            if self.active_plan_id
            else self.next_step_prompt
        )
        self.messages.append(Message.user_message(prompt))

        # 在思考之前获取当前步骤索引
        self.current_step_index = await self._get_current_step_index()

        result = await super().think()

        # 思考之后，如果决定执行一个工具且它不是规划工具或特殊工具
        # 将其与当前步骤关联以便跟踪
        if result and self.tool_calls:
            latest_tool_call = self.tool_calls[0]  # 获取最近一次的工具调用
            if (
                latest_tool_call.function.name != "planning"
                and latest_tool_call.function.name not in self.special_tool_names
                and self.current_step_index is not None
            ):
                self.step_execution_tracker[latest_tool_call.id] = {
                    "step_index": self.current_step_index,
                    "tool_name": latest_tool_call.function.name,
                    "status": "pending",  # 将在执行后更新
                }

        return result

    async def act(self) -> str:
        """
        执行一个步骤并跟踪其完成状态。
        执行步骤后，更新计划状态，如果工具调用在跟踪器中，则更新其状态为已完成，并记录结果。
        如果是合适的工具调用，则更新计划状态。
        """
        result = await super().act()

        # 执行工具后，更新计划状态
        if self.tool_calls:
            latest_tool_call = self.tool_calls[0]

            # 将执行状态更新为完成
            if latest_tool_call.id in self.step_execution_tracker:
                self.step_execution_tracker[latest_tool_call.id]["status"] = "completed"
                self.step_execution_tracker[latest_tool_call.id]["result"] = result

                # 如果这是非规划且非特殊工具，则更新计划状态
                if (
                    latest_tool_call.function.name != "planning"
                    and latest_tool_call.function.name not in self.special_tool_names
                ):
                    await self.update_plan_status(latest_tool_call.id)

        return result

    async def get_plan(self) -> str:
        """
        检索当前计划状态。
        """
        # 如果没有活动计划ID，则返回提示信息。
        if not self.active_plan_id:
            return "No active plan. Please create a plan first."
        
        # 否则，通过执行计划工具的“get”命令获取计划状态。
        result = await self.available_tools.execute(
            name="planning",
            tool_input={"command": "get", "plan_id": self.active_plan_id},
        )
        return result.output if hasattr(result, "output") else str(result)

    async def run(self, request: Optional[str] = None) -> str:
        """
        运行代理，可提供一个可选的初始请求。
        """
        # 如果初始请求，则创建初始计划，然后运行代理。
        if request:
            await self.create_initial_plan(request)
        return await super().run()

    async def update_plan_status(self, tool_call_id: str) -> None:
        """
        根据已完成的工具执行更新当前计划进度。
        只有在关联工具成功执行后，才将步骤标记为已完成。
        """

        # 没有活动ID，直接返回
        if not self.active_plan_id:
            return

        # 执行跟踪器中不存在 tool_call_id，直接返回
        if tool_call_id not in self.step_execution_tracker:
            logger.warning(f"No step tracking found for tool call {tool_call_id}")
            return

        # 执行计划工具的 "mark_step" 命令将步骤标记为已完成
        tracker = self.step_execution_tracker[tool_call_id]
        if tracker["status"] != "completed":
            logger.warning(f"Tool call {tool_call_id} has not completed successfully")
            return

        step_index = tracker["step_index"]

        try:
            # 标记步骤为完成
            await self.available_tools.execute(
                name="planning",
                tool_input={
                    "command": "mark_step",
                    "plan_id": self.active_plan_id,
                    "step_index": step_index,
                    "step_status": "completed",
                },
            )
            logger.info(
                f"Marked step {step_index} as completed in plan {self.active_plan_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to update plan status: {e}")

    async def _get_current_step_index(self) -> Optional[int]:
        """
        解析当前计划以确定第一个未完成步骤的索引。
        """
        # 如果未找到活动步骤，则返回None。
        if not self.active_plan_id:
            return None

        plan = await self.get_plan()

        try:
            plan_lines = plan.splitlines()
            steps_index = -1

            # 分割计划字符串为行，查找 "Steps:" 行，然后找到第一个未完成的步骤，
            for i, line in enumerate(plan_lines):
                if line.strip() == "Steps:":
                    steps_index = i
                    break

            if steps_index == -1:
                return None

            # 找到第一个未完成步骤
            for i, line in enumerate(plan_lines[steps_index + 1 :], start=0):
                if "[ ]" in line or "[→]" in line:  # 未开始 not_started 或进行 in_progress
                    # 将当前步骤标记为进行中
                    await self.available_tools.execute(
                        name="planning",
                        tool_input={
                            "command": "mark_step",
                            "plan_id": self.active_plan_id,
                            "step_index": i,
                            "step_status": "in_progress",
                        },
                    )
                    return i

            return None  # 未找到活动步骤
        except Exception as e:
            logger.warning(f"Error finding current step index: {e}")
            return None

    async def create_initial_plan(self, request: str) -> None:
        """
        根据请求创建初始计划。
        记录日志并向记忆中添加用户消息，通过LLM询问工具以创建计划，并将相关消息添加到内存中。
        如果未成功创建计划，则记录警告并添加相应消息到内存。
        """
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")

        # 创建 user message, "分析请求并创建一个计划（带有ID）"
        messages = [
            Message.user_message(
                f"Analyze the request and create a plan with ID {self.active_plan_id}: {request}"
            )
        ]
        # user message 增加到记忆
        self.memory.add_messages(messages)

        # 调用 LLM
        response = await self.llm.ask_tool(
            messages=messages,
            system_msgs=[Message.system_message(self.system_prompt)],
            tools=self.available_tools.to_params(),
            tool_choice="required",
        )

        # 代理返回处理
        assistant_msg = Message.from_tool_calls(
            content=response.content, tool_calls=response.tool_calls
        )

        # 代理请求记录记忆
        self.memory.add_message(assistant_msg)

        # 循环工具响应
        plan_created = False
        for tool_call in response.tool_calls:
            if tool_call.function.name == "planning":
                result = await self.execute_tool(tool_call)
                logger.info(
                    f"Executed tool {tool_call.function.name} with result: {result}"
                )

                # 将工具响应添加到记忆
                tool_msg = Message.tool_message(
                    content=result,
                    tool_call_id=tool_call.id,
                    name=tool_call.function.name,
                )
                self.memory.add_message(tool_msg)
                plan_created = True
                break

        if not plan_created:
            logger.warning("No plan created from initial request")
            tool_msg = Message.assistant_message(
                "Error: Parameter `plan_id` is required for command: create"
            )
            self.memory.add_message(tool_msg)


async def main():
    # 配置并运行代理,帮我计划一次去月球的旅行
    agent = PlanningAgent(available_tools=ToolCollection(PlanningTool(), Terminate()))
    result = await agent.run("Help me plan a trip to the moon")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

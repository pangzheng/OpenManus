import json
import time
from typing import Dict, List, Optional, Union

from pydantic import Field

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow
from app.llm import LLM
from app.logger import logger
from app.schema import AgentState, Message
from app.tool import PlanningTool


class PlanningFlow(BaseFlow):
    """一个流程，用于使用代理管理任务的规划和执行."""

    # LLM 实例，默认通过工厂函数创建
    llm: LLM = Field(default_factory=lambda: LLM())
    # 计划工具实例，默认通过工厂函数创建
    planning_tool: PlanningTool = Field(default_factory=PlanningTool)
    # 执行器KEY列表，默认通过工厂函数创建空列表
    executor_keys: List[str] = Field(default_factory=list)
    # 活动计划ID，默认通过工厂函数创建，格式为 "plan_时间戳"
    active_plan_id: str = Field(default_factory=lambda: f"plan_{int(time.time())}")
    # 当前步骤索引，初始为None
    current_step_index: Optional[int] = None

    def __init__(
        self, agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]], **data
    ):
        # 在super().__init__之前设置执行器key
        if "executors" in data:
            data["executor_keys"] = data.pop("executors")

        # 如果提供了计划ID，则设置计划ID
        if "plan_id" in data:
            data["active_plan_id"] = data.pop("plan_id")

        # 如果未提供规划工具，则初始化规划工具
        if "planning_tool" not in data:
            planning_tool = PlanningTool()
            data["planning_tool"] = planning_tool

        # 使用处理后的数据调用父类的init方法
        super().__init__(agents, **data)

        # 如果未指定执行器key，则将其设置为所有代理的key
        if not self.executor_keys:
            self.executor_keys = list(self.agents.keys())

    def get_executor(self, step_type: Optional[str] = None) -> BaseAgent:
        """
        获取当前步骤的合适执行器代理。
        可以扩展为根据步骤类型/要求选择代理
        """
        
        # 如果提供了步骤类型并且与某个代理键匹配，则使用该代理
        if step_type and step_type in self.agents:
            return self.agents[step_type]

        # 否则，使用第一个可用的执行器或回退到主代理
        for key in self.executor_keys:
            if key in self.agents:
                return self.agents[key]

        # 回退到主代理
        return self.primary_agent

    async def execute(self, input_text: str) -> str:
        """执行使用代理的规划流程"""
        try:
            if not self.primary_agent:
                raise ValueError("No primary agent available")

            # 如果提供了输入，则创建初始计划
            if input_text:
                await self._create_initial_plan(input_text)

                # 验证计划是否成功创建,错误打印日志
                if self.active_plan_id not in self.planning_tool.plans:
                    logger.error(
                        f"Plan creation failed. Plan ID {self.active_plan_id} not found in planning tool."
                    )
                    return f"Failed to create plan for: {input_text}"

            # 创建结果字符串
            result = ""

            while True:
                # 获取要执行的当前步骤
                self.current_step_index, step_info = await self._get_current_step_info()

                # 如果没有更多步骤或计划完成，则退出
                if self.current_step_index is None:
                    result += await self._finalize_plan()
                    break

                # 使用合适的代理执行当前步骤
                step_type = step_info.get("type") if step_info else None
                executor = self.get_executor(step_type)
                step_result = await self._execute_step(executor, step_info)
                result += step_result + "\n"

                # 检查代理是否想要终止
                if hasattr(executor, "state") and executor.state == AgentState.FINISHED:
                    break

            return result
        except Exception as e:
            logger.error(f"Error in PlanningFlow: {str(e)}")
            return f"Execution failed: {str(e)}"

    async def _create_initial_plan(self, request: str) -> None:
        """使用流程的LLM和PlanningTool根据请求创建一个初始计划。"""
        logger.info(f"Creating initial plan with ID: {self.active_plan_id}")

        # 创建用于计划创建的系统消息，"你是规划助手。你的任务是制定详细的计划，包含清晰的步骤。"
        system_message = Message.system_message(
            "You are a planning assistant. Your task is to create a detailed plan with clear steps."
        )

        # 创建包含请求的用户消息,"创建一个详细的计划来完成此任务："
        user_message = Message.user_message(
            f"Create a detailed plan to accomplish this task: {request}"
        )

        # 使用规划工具调用LLM
        response = await self.llm.ask_tool(
            messages=[user_message],
            system_msgs=[system_message],
            tools=[self.planning_tool.to_param()],
            tool_choice="required",
        )

        # 如果存在工具调用，则处理它们
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call.function.name == "planning":
                    # 解析参数
                    args = tool_call.function.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse tool arguments: {args}")
                            continue

                    # 确保正确设置计划ID并执行工具
                    args["plan_id"] = self.active_plan_id

                    # 通过工具集合而不是直接执行工具
                    result = await self.planning_tool.execute(**args)

                    logger.info(f"Plan creation result: {str(result)}")
                    return

        # 如果执行到达这里，则创建默认计划
        logger.warning("Creating default plan")

        # 使用工具集合创建默认计划
        await self.planning_tool.execute(
            **{
                "command": "create",
                "plan_id": self.active_plan_id,
                "title": f"Plan for: {request[:50]}{'...' if len(request) > 50 else ''}",
                "steps": ["Analyze request", "Execute task", "Verify results"],
            }
        )

    async def _get_current_step_info(self) -> tuple[Optional[int], Optional[dict]]:
        """
        解析当前计划以识别第一个未完成步骤的索引和信息。
        如果未找到活动步骤，则返回(None, None)。
        """
        if (
            not self.active_plan_id
            or self.active_plan_id not in self.planning_tool.plans
        ):
            logger.error(f"Plan with ID {self.active_plan_id} not found")
            return None, None

        try:
            # 直接从规划工具存储中访问计划数据
            plan_data = self.planning_tool.plans[self.active_plan_id]
            steps = plan_data.get("steps", [])
            step_statuses = plan_data.get("step_statuses", [])

            # 找到第一个未完成的步骤
            for i, step in enumerate(steps):
                if i >= len(step_statuses):
                    status = "not_started"
                else:
                    status = step_statuses[i]

                if status in ["not_started", "in_progress"]:
                    # 如果可用，提取步骤类型/类别
                    step_info = {"text": step}

                    # 尝试从文本中提取步骤类型（例如，[SEARCH]或[CODE]）
                    import re

                    type_match = re.search(r"\[([A-Z_]+)\]", step)
                    if type_match:
                        step_info["type"] = type_match.group(1).lower()

                    # 将当前步骤标记为“in_progress”
                    try:
                        await self.planning_tool.execute(
                            command="mark_step",
                            plan_id=self.active_plan_id,
                            step_index=i,
                            step_status="in_progress",
                        )
                    except Exception as e:
                        logger.warning(f"Error marking step as in_progress: {e}")
                        # 如果需要，直接更新步骤状态
                        if i < len(step_statuses):
                            step_statuses[i] = "in_progress"
                        else:
                            while len(step_statuses) < i:
                                step_statuses.append("not_started")
                            step_statuses.append("in_progress")

                        plan_data["step_statuses"] = step_statuses

                    return i, step_info

            return None, None  # 未找到活动步骤

        except Exception as e:
            logger.warning(f"Error finding current step index: {e}")
            return None, None

    async def _execute_step(self, executor: BaseAgent, step_info: dict) -> str:
        """使用指定的代理通过 agent.run() 执行当前步骤。"""
        # 使用当前计划状态为代理准备上下文
        plan_status = await self._get_plan_text()
        step_text = step_info.get("text", f"Step {self.current_step_index}")

        # 为代理创建一个提示以执行当前步骤
        step_prompt = f"""
        CURRENT PLAN STATUS:
        {plan_status}

        YOUR CURRENT TASK:
        You are now working on step {self.current_step_index}: "{step_text}"

        Please execute this step using the appropriate tools. When you're done, provide a summary of what you accomplished.
        """

        # 使用agent.run()执行步骤
        try:
            step_result = await executor.run(step_prompt)

            # 成功执行后将步骤标记为已完成
            await self._mark_step_completed()

            return step_result
        except Exception as e:
            logger.error(f"Error executing step {self.current_step_index}: {e}")
            return f"Error executing step {self.current_step_index}: {str(e)}"

    async def _mark_step_completed(self) -> None:
        """将当前步骤标记为已完成。"""
        if self.current_step_index is None:
            return

        try:
            # 将步骤标记为已完成
            await self.planning_tool.execute(
                command="mark_step",
                plan_id=self.active_plan_id,
                step_index=self.current_step_index,
                step_status="completed",
            )
            logger.info(
                f"Marked step {self.current_step_index} as completed in plan {self.active_plan_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to update plan status: {e}")
            # 直接在规划工具存储中更新步骤状态
            if self.active_plan_id in self.planning_tool.plans:
                plan_data = self.planning_tool.plans[self.active_plan_id]
                step_statuses = plan_data.get("step_statuses", [])

                # 确保step_statuses列表足够长
                while len(step_statuses) <= self.current_step_index:
                    step_statuses.append("not_started")

                # 更新状态
                step_statuses[self.current_step_index] = "completed"
                plan_data["step_statuses"] = step_statuses

    async def _get_plan_text(self) -> str:
        """获取当前计划的格式化文本。"""
        try:
            result = await self.planning_tool.execute(
                command="get", plan_id=self.active_plan_id
            )
            return result.output if hasattr(result, "output") else str(result)
        except Exception as e:
            logger.error(f"Error getting plan: {e}")
            return self._generate_plan_text_from_storage()

    def _generate_plan_text_from_storage(self) -> str:
        """如果规划工具失败，则直接从存储中生成计划文本。"""
        try:
            if self.active_plan_id not in self.planning_tool.plans:
                return f"Error: Plan with ID {self.active_plan_id} not found"

            plan_data = self.planning_tool.plans[self.active_plan_id]
            title = plan_data.get("title", "Untitled Plan")
            steps = plan_data.get("steps", [])
            step_statuses = plan_data.get("step_statuses", [])
            step_notes = plan_data.get("step_notes", [])

            # 确保step_statuses和step_notes与步骤数量匹配
            while len(step_statuses) < len(steps):
                step_statuses.append("not_started")
            while len(step_notes) < len(steps):
                step_notes.append("")

            # 按状态统计步骤
            status_counts = {
                "completed": 0,
                "in_progress": 0,
                "blocked": 0,
                "not_started": 0,
            }

            for status in step_statuses:
                if status in status_counts:
                    status_counts[status] += 1

            completed = status_counts["completed"]
            total = len(steps)
            progress = (completed / total) * 100 if total > 0 else 0

            plan_text = f"Plan: {title} (ID: {self.active_plan_id})\n"
            plan_text += "=" * len(plan_text) + "\n\n"

            plan_text += (
                f"Progress: {completed}/{total} steps completed ({progress:.1f}%)\n"
            )
            plan_text += f"Status: {status_counts['completed']} completed, {status_counts['in_progress']} in progress, "
            plan_text += f"{status_counts['blocked']} blocked, {status_counts['not_started']} not started\n\n"
            plan_text += "Steps:\n"

            for i, (step, status, notes) in enumerate(
                zip(steps, step_statuses, step_notes)
            ):
                if status == "completed":
                    status_mark = "[✓]"
                elif status == "in_progress":
                    status_mark = "[→]"
                elif status == "blocked":
                    status_mark = "[!]"
                else:  # 没有开始的
                    status_mark = "[ ]"

                plan_text += f"{i}. {status_mark} {step}\n"
                if notes:
                    plan_text += f"   Notes: {notes}\n"

            return plan_text
        except Exception as e:
            logger.error(f"Error generating plan text from storage: {e}")
            return f"Error: Unable to retrieve plan with ID {self.active_plan_id}"

    async def _finalize_plan(self) -> str:
        """使用流程的LLM直接完成计划并提供总结。"""
        plan_text = await self._get_plan_text()

        # 直接使用流程的LLM创建总结
        try:
            #你是规划助手。你的任务是总结已完成的计划。
            system_message = Message.system_message(
                "You are a planning assistant. Your task is to summarize the completed plan."
            )
            """
            计划已完成。以下是最终计划状态：
            {plan_text}
            请提供已完成工作的总结以及任何最终想法。
            """
            user_message = Message.user_message(
                f"The plan has been completed. Here is the final plan status:\n\n{plan_text}\n\nPlease provide a summary of what was accomplished and any final thoughts."
            )

            response = await self.llm.ask(
                messages=[user_message], system_msgs=[system_message]
            )

            return f"Plan completed:\n\n{response}"
        except Exception as e:
            logger.error(f"Error finalizing plan with LLM: {e}")

            # 回退到使用代理进行总结
            try:
                agent = self.primary_agent
                summary_prompt = f"""
                The plan has been completed. Here is the final plan status:

                {plan_text}

                Please provide a summary of what was accomplished and any final thoughts.
                """
                """
                计划已完成。以下是最终计划状态：
                {plan_text}
                请提供已完成工作的总结以及任何最终想法
                """
                summary = await agent.run(summary_prompt)
                return f"Plan completed:\n\n{summary}"
            except Exception as e2:
                logger.error(f"Error finalizing plan with agent: {e2}")
                return "Plan completed. Error generating summary."

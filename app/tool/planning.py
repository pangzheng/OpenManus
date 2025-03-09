# tool/planning.py
from typing import Dict, List, Literal, Optional

from app.exceptions import ToolError
from app.tool.base import BaseTool, ToolResult


_PLANNING_TOOL_DESCRIPTION = """
A planning tool that allows the agent to create and manage plans for solving complex tasks.
The tool provides functionality for creating plans, updating plan steps, and tracking progress.
"""
# 该工具提供了创建计划、更新计划步骤以及跟踪进度的功能。

class PlanningTool(BaseTool):
    """
    A planning tool that allows the agent to create and manage plans for solving complex tasks.
    The tool provides functionality for creating plans, updating plan steps, and tracking progress.
    """

    # 名称
    name: str = "planning"
    # 描述
    description: str = _PLANNING_TOOL_DESCRIPTION
    # 参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The command to execute. Available commands: create, update, list, get, set_active, mark_step, delete.",
                "enum": [
                    "create",
                    "update",
                    "list",
                    "get",
                    "set_active",
                    "mark_step",
                    "delete",
                ],
                "type": "string",
            },
            # 执行的命令
            # 可用命令：create, update, list, get, set_active, mark_step, delete。
            "plan_id": {
                "description": "Unique identifier for the plan. Required for create, update, set_active, and delete commands. Optional for get and mark_step (uses active plan if not specified).",
                "type": "string",
            },
            # 计划的唯一标识符ID
            # 对于create、update、set_active和delete命令是必需的。对于get和mark_step是可选的（如果不指定则使用当前活动计划）。
            "title": {
                "description": "Title for the plan. Required for create command, optional for update command.",
                "type": "string",
            },
            # 计划的标题
            # 对于create命令是必需的，对于update命令是可选的。
            "steps": {
                "description": "List of plan steps. Required for create command, optional for update command.",
                "type": "array",
                "items": {"type": "string"},
            },
            # 计划步骤列表
            # 对于create命令是必需的，对于update命令是可选的。
            "step_index": {
                "description": "Index of the step to update (0-based). Required for mark_step command.",
                "type": "integer",
            },
            # 要更新的步骤索引（基于0）
            # 对于 mark_step 命令是必需的。
            "step_status": {
                "description": "Status to set for a step. Used with mark_step command.",
                "enum": ["not_started", "in_progress", "completed", "blocked"],
                "type": "string",
            },
            # 要设置的步骤状态，状态包括:"not_started", "in_progress", "completed", "blocked"
            # 用于mark_step命令。
            "step_notes": {
                "description": "Additional notes for a step. Optional for mark_step command.",
                "type": "string",
            },
            # 步骤的附加说明
            # 对于 mark_step 命令是可选的。
        },
        # 必须包含的参数，这里只有command是必须的
        "required": ["command"],
        # 不允许有额外的属性
        "additionalProperties": False,
    }

    # 用于存储计划的字典，键为 plan_id，值为计划的详细信息
    plans: dict = {}  # 
    # 用于跟踪当前活动计划的ID，初始为None
    _current_plan_id: Optional[str] = None 

    # 执行方法
    async def execute(
        self,
        *,
        command: Literal[
            "create", "update", "list", "get", "set_active", "mark_step", "delete"
        ],
        plan_id: Optional[str] = None,
        title: Optional[str] = None,
        steps: Optional[List[str]] = None,
        step_index: Optional[int] = None,
        step_status: Optional[
            Literal["not_started", "in_progress", "completed", "blocked"]
        ] = None,
        step_notes: Optional[str] = None,
        **kwargs,
    ):
        """
        Execute the planning tool with the given command and parameters.

        Parameters:
        - command: The operation to perform
        - plan_id: Unique identifier for the plan
        - title: Title for the plan (used with create command)
        - steps: List of steps for the plan (used with create command)
        - step_index: Index of the step to update (used with mark_step command)
        - step_status: Status to set for a step (used with mark_step command)
        - step_notes: Additional notes for a step (used with mark_step command)
        """
        # 根据给定的命令和参数执行规划工具。

        # 参数:
        # - command: 要执行的操作
        # - plan_id: 计划的唯一标识符
        # - title: 计划的标题（用于创建命令）
        # - steps: 计划的步骤列表（用于创建命令）
        # - step_index: 要更新的步骤索引（用于标记步骤命令）
        # - step_status: 要设置的步骤状态（用于标记步骤命令）
        # - step_notes: 步骤的附加说明（用于标记步骤命令）

        # 根据不同的命令调用相应的内部方法
        if command == "create":
            return self._create_plan(plan_id, title, steps)
        elif command == "update":
            return self._update_plan(plan_id, title, steps)
        elif command == "list":
            return self._list_plans()
        elif command == "get":
            return self._get_plan(plan_id)
        elif command == "set_active":
            return self._set_active_plan(plan_id)
        elif command == "mark_step":
            return self._mark_step(plan_id, step_index, step_status, step_notes)
        elif command == "delete":
            return self._delete_plan(plan_id)
        else:
            # 如果命令不被识别，抛出ToolError异常
            raise ToolError(
                f"Unrecognized command: {command}. Allowed commands are: create, update, list, get, set_active, mark_step, delete"
            )

    # 创建计划
    def _create_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """使用给定的ID、标题和步骤创建一个新计划。"""
        # 检查plan_id是否为空，为空则抛出异常
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: create")

        # 检查 plan_id 是否已存在，存在则抛出异常
        if plan_id in self.plans:
            raise ToolError(
                f"A plan with ID '{plan_id}' already exists. Use 'update' to modify existing plans."
            )
        
        # 检查title是否为空，为空则抛出异常
        if not title:
            raise ToolError("Parameter `title` is required for command: create")
        
        # 检查steps是否符合要求，不符合则抛出异常
        if (
            not steps
            or not isinstance(steps, list)
            or not all(isinstance(step, str) for step in steps)
        ):
            raise ToolError(
                "Parameter `steps` must be a non-empty list of strings for command: create"
            )

        # 创建一个新计划，初始化步骤状态和说明
        plan = {
            "plan_id": plan_id,
            "title": title,
            "steps": steps,
            "step_statuses": ["not_started"] * len(steps),
            "step_notes": [""] * len(steps),
        }

        # 将新计划添加到plans字典中
        self.plans[plan_id] = plan
        # 将新创建的计划设置为当前活动计划
        self._current_plan_id = plan_id  

        return ToolResult(
            output=f"Plan created successfully with ID: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _update_plan(
        self, plan_id: Optional[str], title: Optional[str], steps: Optional[List[str]]
    ) -> ToolResult:
        """使用新的标题或步骤更新现有计划。"""

        # 检查 plan_id 是否为空，为空则抛出异常
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: update")

        # 检查plan_id是否存在，不存在则抛出异常
        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        # 获取 ID
        plan = self.plans[plan_id]

        # 如果提供了title，则更新计划的标题
        if title:
            plan["title"] = title

        # 如果提供了steps，则更新计划的步骤
        if steps:
            if not isinstance(steps, list) or not all(
                isinstance(step, str) for step in steps
            ):
                raise ToolError(
                    "Parameter `steps` must be a list of strings for command: update"
                )

            # 保留未更改步骤的现有状态
            old_steps = plan["steps"]
            old_statuses = plan["step_statuses"]
            old_notes = plan["step_notes"]

            # 创建新的步骤状态和说明列表
            new_statuses = []
            new_notes = []

            for i, step in enumerate(steps):
                # 如果步骤在旧步骤中位置相同，则保留原状态和说明
                if i < len(old_steps) and step == old_steps[i]:
                    new_statuses.append(old_statuses[i])
                    new_notes.append(old_notes[i])
                else:
                    new_statuses.append("not_started")
                    new_notes.append("")

            plan["steps"] = steps
            plan["step_statuses"] = new_statuses
            plan["step_notes"] = new_notes

        return ToolResult(
            output=f"Plan updated successfully: {plan_id}\n\n{self._format_plan(plan)}"
        )

    def _list_plans(self) -> ToolResult:
        """列出所有可用的计划。"""

        # 如果没有计划，返回相应提示
        if not self.plans:
            return ToolResult(
                output="No plans available. Create a plan with the 'create' command."
            )

        output = "Available plans:\n"
        for plan_id, plan in self.plans.items():
            # 标记当前活动计划
            current_marker = " (active)" if plan_id == self._current_plan_id else ""
            # 计算已完成的步骤数
            completed = sum(
                1 for status in plan["step_statuses"] if status == "completed"
            )
            # 计划总数
            total = len(plan["steps"])
            # 进度
            progress = f"{completed}/{total} steps completed"
            # 当前执行情况
            output += f"• {plan_id}{current_marker}: {plan['title']} - {progress}\n"

        return ToolResult(output=output)

    def _get_plan(self, plan_id: Optional[str]) -> ToolResult:
        """获取特定计划的详细信息。"""
        # 如果没有提供plan_id，则使用当前活动计划
        if not plan_id:
            if not self._current_plan_id:
                raise ToolError(
                    "No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id

        # 检查plan_id是否存在，不存在则抛出异常
        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        plan = self.plans[plan_id]
        return ToolResult(output=self._format_plan(plan))

    def _set_active_plan(self, plan_id: Optional[str]) -> ToolResult:
        """将一个计划设置为活动计划。"""
        # 检查plan_id是否为空，为空则抛出异常
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: set_active")
        # 检查plan_id是否存在，不存在则抛出异常
        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        # 设置活动ID为传入ID
        self._current_plan_id = plan_id
        return ToolResult(
            output=f"Plan '{plan_id}' is now the active plan.\n\n{self._format_plan(self.plans[plan_id])}"
        )

    def _mark_step(
        self,
        plan_id: Optional[str],
        step_index: Optional[int],
        step_status: Optional[str],
        step_notes: Optional[str],
    ) -> ToolResult:
        """使用特定状态和可选说明标记一个步骤。"""
        # 如果没有提供plan_id，则使用当前活动计划
        if not plan_id:
            if not self._current_plan_id:
                raise ToolError(
                    "No active plan. Please specify a plan_id or set an active plan."
                )
            plan_id = self._current_plan_id

        # 检查plan_id是否存在，不存在则抛出异常
        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")

        # 检查step_index是否为空，为空则抛出异常
        if step_index is None:
            raise ToolError("Parameter `step_index` is required for command: mark_step")

        plan = self.plans[plan_id]

        # 检查step_index是否有效，无效则抛出异常
        if step_index < 0 or step_index >= len(plan["steps"]):
            raise ToolError(
                f"Invalid step_index: {step_index}. Valid indices range from 0 to {len(plan['steps'])-1}."
            )

        # 检查step_status是否有效，无效则抛出异常
        if step_status and step_status not in [
            "not_started",
            "in_progress",
            "completed",
            "blocked",
        ]:
            raise ToolError(
                f"Invalid step_status: {step_status}. Valid statuses are: not_started, in_progress, completed, blocked"
            )
        # 如果提供了step_status，则更新步骤状态
        if step_status:
            plan["step_statuses"][step_index] = step_status
        # 如果提供了step_notes，则更新步骤说明
        if step_notes:
            plan["step_notes"][step_index] = step_notes

        return ToolResult(
            output=f"Step {step_index} updated in plan '{plan_id}'.\n\n{self._format_plan(plan)}"
        )


    def _delete_plan(self, plan_id: Optional[str]) -> ToolResult:
        """删除一个计划。"""
        # 检查plan_id是否为空，为空则抛出异常
        if not plan_id:
            raise ToolError("Parameter `plan_id` is required for command: delete")
        # 检查plan_id是否存在，不存在则抛出异常
        if plan_id not in self.plans:
            raise ToolError(f"No plan found with ID: {plan_id}")
        # 从plans字典中删除计划
        del self.plans[plan_id]

        # 如果删除的是当前活动计划，则清除当前活动计划ID
        if self._current_plan_id == plan_id:
            self._current_plan_id = None

        return ToolResult(output=f"Plan '{plan_id}' has been deleted.")

    def _format_plan(self, plan: Dict) -> str:
        """格式化计划以进行显示。"""
        output = f"Plan: {plan['title']} (ID: {plan['plan_id']})\n"
        output += "=" * len(output) + "\n\n"

        # 计算进度统计信息
        total_steps = len(plan["steps"])
        completed = sum(1 for status in plan["step_statuses"] if status == "completed")
        in_progress = sum(
            1 for status in plan["step_statuses"] if status == "in_progress"
        )
        blocked = sum(1 for status in plan["step_statuses"] if status == "blocked")
        not_started = sum(
            1 for status in plan["step_statuses"] if status == "not_started"
        )

        output += f"Progress: {completed}/{total_steps} steps completed "
        if total_steps > 0:
            percentage = (completed / total_steps) * 100
            output += f"({percentage:.1f}%)\n"
        else:
            output += "(0%)\n"

        output += f"Status: {completed} completed, {in_progress} in progress, {blocked} blocked, {not_started} not started\n\n"
        output += "Steps:\n"

        # 添加每个步骤及其状态和说明
        for i, (step, status, notes) in enumerate(
            zip(plan["steps"], plan["step_statuses"], plan["step_notes"])
        ):
            status_symbol = {
                "not_started": "[ ]",
                "in_progress": "[→]",
                "completed": "[✓]",
                "blocked": "[!]",
            }.get(status, "[ ]")

            output += f"{i}. {status_symbol} {step}\n"
            if notes:
                output += f"   Notes: {notes}\n"

        return output

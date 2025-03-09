from app.tool.base import BaseTool

# 描述当请求满足或助手无法进一步执行任务时终止交互的情况
_TERMINATE_DESCRIPTION = """Terminate the interaction when the request is met OR if the assistant cannot proceed further with the task."""

# 定义  Terminate 的类，继承自 BaseTool
class Terminate(BaseTool):
    # 名称
    name: str = "terminate"
    # 描述
    description: str = _TERMINATE_DESCRIPTION
    # 参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
            }
            # 交互的完成状态。    
        },
        # 必填参数
        "required": ["status"],
    }

    # 定义execute异步方法，结束当前执行
    # 接受一个字符串类型的 status 参数，返回一个字符串
    async def execute(self, status: str) -> str:
        return f"The interaction has been completed with status: {status}"

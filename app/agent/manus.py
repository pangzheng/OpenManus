from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.manus import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.tool import Terminate, ToolCollection
from app.tool.browser_use_tool import BrowserUseTool
from app.tool.file_saver import FileSaver
from app.tool.google_search import GoogleSearch
from app.tool.python_execute import PythonExecute

# Manus 类继承自 ToolCallAgent 类，是一个多功能的通用代理类
class Manus(ToolCallAgent):
    """
    一个用途广泛的通用代理，使用规划来解决各种任务。
    这个代理扩展了 PlanningAgent，并具备一系列工具和功能，
    包括 Python 执行、网页浏览、文件操作和信息检索，以处理广泛的用户请求。```
    """
    # 名字
    name: str = "Manus"
    # 描述
    description: str = (
        "一个多功能的代理，可以使用多种工具来解决各种任务"
    )
    # 用于设置系统提示信息，manus.py 的提示词
    system_prompt: str = SYSTEM_PROMPT
    # 用于设置下一步提示信息，manus.py 的提示词
    next_step_prompt: str = NEXT_STEP_PROMPT

    # 定义 Manus 类的 available_tools 属性，类型为 ToolCollection，使用 Field 定义，
    # 默认值通过 lambda 函数生成，该 lambda 函数创建了一个包含 PythonExecute、GoogleSearch、
    # BrowserUseTool、FileSaver 和 Terminate 实例的 ToolCollection 对象，
    # 向工具集合中添加通用工具
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            PythonExecute(), GoogleSearch(), BrowserUseTool(), FileSaver(), Terminate()
        )
    )

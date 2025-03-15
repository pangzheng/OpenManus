from typing import List

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.prompt.swe import NEXT_STEP_TEMPLATE, SYSTEM_PROMPT
from app.tool import Bash, StrReplaceEditor, Terminate, ToolCollection

class SWEAgent(ToolCallAgent):
    """一个实现了SWEAgent范式的代理，用于执行代码和进行自然对话"""

    # 代理名字
    name: str = "swe"
    # 代理的描述
    description: str = "一个自主人工智能程序员，直接与计算机交互以解决问题."
    # 系统提示词，位置 swe.py
    system_prompt: str = SYSTEM_PROMPT
    # 下一步提示词，位置 swe.py
    next_step_prompt: str = NEXT_STEP_TEMPLATE

    # 可用工具的集合，通过实例化ToolCollection并传入Bash、StrReplaceEditor、Terminate工具类创建
    # available_tools: ToolCollection = ToolCollection(
    #     Bash(), StrReplaceEditor(), Terminate()
    # )
    # 特殊工具名称的列表，通过Field默认工厂函数创建，初始值为 Terminate 工具的名称
    # special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    # 最大步骤数，整数类型
    max_steps: int = 30

    # bash工具实例，通过Field默认工厂函数创建Bash实例
    # bash: Bash = Field(default_factory=Bash)
    # 工作目录，字符串类型，初始值为当前目录
    working_dir: str = "."

    available_tools: ToolCollection
    special_tool_names: List[str]

    # 初始化方法
    def __init__(self):
        super().__init__()
        self.bash = Bash()
        self.available_tools = ToolCollection(
            self.bash, StrReplaceEditor(), Terminate()
        )
        self.special_tool_names = [Terminate().name]

    async def setup(self):
        """初始化工具"""
        await self.bash.execute(restart=True)  # 初始化沙箱
        self.working_dir = await self.bash.execute("pwd")

    async def think(self) -> bool:
        """定义异步方法think，用于处理当前状态并决定下一步行动"""
        
        # 更新工作目录，通过调用bash工具的execute方法执行"pwd"命令获取当前工作目录
        self.working_dir = await self.bash.execute("pwd")

        # 使用当前工作目录格式化下一步提示模板
        self.next_step_prompt = self.next_step_prompt.format(
            current_dir=self.working_dir
        )
        
        # 调用父类的think方法
        return await super().think()
    
    async def teardown(self):
        """清理资源"""
        await self.bash.cleanup()

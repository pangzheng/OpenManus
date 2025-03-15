import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，以便导入 app 包
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.tool.browser_use_tool import BrowserUseTool

# 定义一个异步函数来调用 execute 方法
async def test_browser_use_tool():
    # 创建 BrowserUseTool 工具实例
    browser_tool = BrowserUseTool()

    # 测试 'navigate' 操作
    navigate_result = await browser_tool.execute(action="navigate", url="https://www.google.com/")
    print(navigate_result)

    # 测试 'click' 操作（假设页面上有一个可点击的元素）
    click_result = await browser_tool.execute(action="click", index=0)
    print(click_result)

    # 清理资源
    await browser_tool.cleanup()

# 运行异步函数
asyncio.run(test_browser_use_tool())
import asyncio
import sys
from pathlib import Path

# 将项目根目录添加到 sys.path，以便导入 app 包
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from app.tool.python_execute import PythonExecute

# 定义一个异步函数来调用 execute 方法
async def test_python_execute():
    # 创建 PythonExecute 工具实例
    python_tool = PythonExecute()

    # 调用 execute 方法，传递要执行的代码和超时时间
    result = await python_tool.execute(code='print("Hello, World!")', timeout=5)
    # 打印执行结果
    print(result)

# 运行异步函数
asyncio.run(test_python_execute())
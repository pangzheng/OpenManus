import threading
from typing import Dict

from app.tool.base import BaseTool


class PythonExecute(BaseTool):
    """一个用于执行受超时和安全限制约束的Python代码的工具。"""
    # 名字
    name: str = "python_execute"
    # 描述，执行Python代码字符串。注意：只有打印输出可见，函数返回值不会被捕获。使用print 语句查看结果
    description: str = "Executes Python code string. Note: Only print outputs are visible, function return values are not captured. Use print statements to see results."

    # 参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            # python 代码执行器
        },
        # 必填参数
        "required": ["code"],
    }

    # 定义execute异步方法，用于执行代码并设置超时
    async def execute(
        self,
        code: str,
        timeout: int = 5,
    ) -> Dict:
        """
        Executes the provided Python code with a timeout.

        Args:
            code (str): The Python code to execute.
            timeout (int): Execution timeout in seconds.

        Returns:
            Dict: Contains 'output' with execution output or error message and 'success' status.
        """
        # 使用超时设置执行提供的 Python 代码。
        # 参数:
        #     code (str): 要执行的Python代码。
        #     timeout (int): 执行超时时间，单位为秒。
        # 返回:
        #     Dict: 包含 'observation'，其值为执行输出或错误消息，以及 'success' 状态。
        result = {"observation": ""}

        # 定义 run_code 内部函数来实际执行代码
        def run_code():
            try:
                # 创建一个安全的全局命名空间，只包含必要的内置函数
                safe_globals = {"__builtins__": dict(__builtins__)}

                import sys
                from io import StringIO

                # 创建一个字符串缓冲区用于捕获输出
                output_buffer = StringIO()
                # 将标准输出重定向到缓冲区
                sys.stdout = output_buffer

                # 执行传入的代码，使用安全的全局命名空间和空的局部命名空间
                exec(code, safe_globals, {})

                # 恢复标准输出
                sys.stdout = sys.__stdout__

                # 将缓冲区中的输出内容赋值给结果字典的 'observation' 键
                result["observation"] = output_buffer.getvalue()

            # 捕获执行过程中的任何异常
            except Exception as e:
                # 将异常信息转换为字符串并赋值给 'observation' 键
                result["observation"] = str(e)
                # 设置 'success' 为 False，表示执行失败
                result["success"] = False

        # 创建一个线程来运行 run_code 函数
        thread = threading.Thread(target=run_code)
        # 启动线程
        thread.start()
        # 等待线程执行，设置超时时间
        thread.join(timeout)

        # 如果线程在超时后仍然存活，说明执行超时
        if thread.is_alive():
            return {
                "observation": f"Execution timeout after {timeout} seconds",
                "success": False,
            }
        # 返回结果字典
        return result

import asyncio
import os
from typing import Optional

from app.exceptions import ToolError
from app.tool.base import BaseTool, CLIResult, ToolResult
"""
在终端中执行一个 bash 命令。
* 长运行命令：对于可能无限期运行的命令，应在后台运行，并将输出重定向到文件中，例如 `command = `python3 app.py > server.log 2>&1 &`。

* 交互式：如果 bash 命令返回退出代码 `-1`，这意味着进程尚未完成。助手必须再发送一个带有空 `command` 的终端调用（这将获取任何额外的日志），或者可以向运行中的进程的STDIN发送附加文本（设置 `command` 为文本），或发送 `command=ctrl+c` 来中断进程。

* 超时：如果命令执行结果说"命令超时。向该进程发送 SIGINT"，助手应该重新尝试在后台运行该命令。
"""
_BASH_DESCRIPTION = """Execute a bash command in the terminal.
* Long running commands: For commands that may run indefinitely, it should be run in the background and the output should be redirected to a file, e.g. command = `python3 app.py > server.log 2>&1 &`.
* Interactive: If a bash command returns exit code `-1`, this means the process is not yet finished. The assistant must then send a second call to terminal with an empty `command` (which will retrieve any additional logs), or it can send additional text (set `command` to the text) to STDIN of the running process, or it can send command=`ctrl+c` to interrupt the process.
* Timeout: If a command execution result says "Command timed out. Sending SIGINT to the process", the assistant should retry running the command in the background.
"""

class _BashSession:
    """创建 bash shells 会话类。"""
    
    # 表示会话是否已启动
    _started: bool
    # 表示运行 bash 进程的对象
    _process: asyncio.subprocess.Process

    # bash 命令路径，默认为 "/bin/bash"
    command: str = "/bin/bash"
    # 防止频繁读取，读取输出前等待的延迟时间，单位为秒
    _output_delay: float = 0.2  # seconds
    # 命令执行的超时时间，单位为秒
    _timeout: float = 120.0  # seconds
    # 用于标识命令输出结束的哨兵字符串
    _sentinel: str = "<<exit>>"

    # 初始化函数，默认是否
    def __init__(self):
        self._started = False
        self._timed_out = False

    # 异步启动
    async def start(self):
        # 如果会话已经启动，则直接返回
        if self._started:
            return

        # 创建一个异步子进程来运行 bash 命令
        self._process = await asyncio.create_subprocess_shell(
            self.command,
            # 设置在子进程启动前调用 os.setsid 函数，用于创建新的进程组
            preexec_fn=os.setsid,
            # 使用 shell 来执行命令
            shell=True,
            # 设置缓冲区大小为 0，即无缓冲
            bufsize=0,
            # 将标准输入、输出、错误设置为管道，以便向进程发送数据
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # 将会话标记为已启动
        self._started = True

    def stop(self):
        """终止 bash shell."""
        # 如果没有启动直接抛出异常
        if not self._started:
            raise ToolError("Session has not started.")
        # 如果进程已经结束，直接返回
        if self._process.returncode is not None:
            return
        # 终止 bash 进程
        self._process.terminate()

    async def run(self, command: str):
        """异步 bash shell 中执行一个命令。"""
        # 检查是否启动
        if not self._started:
            raise ToolError("Session has not started.")
        # 检查进程是否存在
        if self._process.returncode is not None:
            # 直接返回工具调用结果
            return ToolResult(
                # 系统提示工具必须重新启动。
                system="tool must be restarted", 
                # bash以退出码返回
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        # 如果超时为真
        if self._timed_out:
            # 直接返回工具调用结果,提示未在{self._timeout}设定时间返回，必须重启
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            )

        # 断言标准输入、输出和错误流不为 None，因为前面使用了 pipline 创建进程时设置了管道
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # 向将命令和（退出哨兵）字符串写入进程的标准输入
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        # 刷新标准输入缓冲区，确保数据发送
        await self._process.stdin.drain()

        
        # 从进程中读取输出，直到找到哨兵
        try:
            # 尝试在超时时间内读取命令输出
            async with asyncio.timeout(self._timeout):
                while True:
                    # 等待一段时间，避免频繁读取
                    await asyncio.sleep(self._output_delay)
                    # 如果我们直接从 stdout/stderr 读取，它将永远等待EOF。直接从 StreamReader 的缓冲区读取输出，避免等待 EOF
                    output = (
                        self._process.stdout._buffer.decode()
                    )  # pyright: ignore[reportAttributeAccessIssue]
                    # 如果输出含有退出哨兵
                    if self._sentinel in output:
                        # 移除退出哨兵并退出循环
                        output = output[: output.index(self._sentinel)]
                        break
        #     如果超时，设置超时标志并抛出异常        
        except asyncio.TimeoutError:
            self._timed_out = True
            # 直接调用 ToolError 抛出错误信息
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            ) from None

        # 除换行符
        if output.endswith("\n"):
            output = output[:-1]

        # 读取标准错误输出
        error = (
            self._process.stderr._buffer.decode()
        )  # pyright: ignore[reportAttributeAccessIssue]
        
        # 除换行符
        if error.endswith("\n"):
            error = error[:-1]

        # 清空标准输出和标准错误的缓冲区，以便下次正确读取
        # clear the buffers so that the next output can be read correctly
        self._process.stdout._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]
        self._process.stderr._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]

        # 返回包含输出和错误信息的 CLIResult
        return CLIResult(output=output, error=error)

class Bash(BaseTool):
    """用于执行bash命令的工具类"""

    # 名称
    name: str = "bash"
    # 描述
    description: str = _BASH_DESCRIPTION
    # 参数-字典
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute. Can be empty to view additional logs when previous exit code is `-1`. Can be `ctrl+c` to interrupt the currently running process.",
            },
        },
        "required": ["command"],
        # 要求必须提供 "command" 参数
    }

    # 用于存储 _BashSession 实例的变量，初始值为 None
    _session: Optional[_BashSession] = None

    """
    定义异步方法 execute，用于执行 bash 命令
    command 参数：要执行的bash命令，默认为 None
    restart 参数：是否重启会话，默认为 False
    **kwargs：接收其他可能传入的关键字参数
    返回值类型为 CLIResult
    """
    async def execute(
        self, command: str | None = None, restart: bool = False, **kwargs
    ) -> CLIResult:
        # 如果 restart 为 True
        if restart:
            # 如果当前已经有会话实例，停止该会话
            if self._session:
                self._session.stop()
            # 创建一个新的 _BashSession 实例    
            self._session = _BashSession()
            # 异步启动新的会话
            await self._session.start()
            # 返回一个 ToolResult 实例，表示工具已重启
            return ToolResult(system="tool has been restarted.")
        
        # 如果当前没有会话实例
        if self._session is None:
            # 创建一个新的 _BashSession 实例
            self._session = _BashSession()
            # 异步启动新的会话
            await self._session.start()
        
        # 如果传入了 command 参数
        if command is not None:
            # 异步执行会话的 run 方法来运行bash命令，并返回结果
            return await self._session.run(command)
        
        #如果没有传入 command 参数，抛出 ToolError 异常，提示没有提供命令
        raise ToolError("no command provided.")


if __name__ == "__main__":
    # 该脚本作为主程序运行
    bash = Bash()
    # 使用 asyncio.run 运行异步方法 execute，执行 "ls -l" 命令，并获取结果
    rst = asyncio.run(bash.execute("ls -l"))
    print(rst)

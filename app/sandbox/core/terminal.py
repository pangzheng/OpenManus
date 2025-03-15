"""
Asynchronous Docker Terminal
This module provides asynchronous terminal functionality for Docker containers,
allowing interactive command execution with timeout control.
"""

import asyncio
import re
import socket
from typing import Dict, Optional, Tuple, Union

import docker
from docker import APIClient
from docker.errors import APIError
from docker.models.containers import Container


class DockerSession:
    def __init__(self, container_id: str) -> None:
        """Initializes a Docker session.
        Args:
            container_id: ID of the Docker container.
        """
        self.api = APIClient()
        self.container_id = container_id
        self.exec_id = None
        self.socket = None

    async def create(self, working_dir: str, env_vars: Dict[str, str]) -> None:
        """与容器建立一个交互式会话。
        参数：
            working_dir：容器内的工作目录。
            env_vars：要设置的环境变量。
        异常：
            RuntimeError：如果套接字连接失败。
        """
        startup_command = [
            "bash",
            "-c",
            f"cd {working_dir} && "
            "PROMPT_COMMAND='' "
            "PS1='$ ' "
            "exec bash --norc --noprofile",
        ]

        exec_data = self.api.exec_create(
            self.container_id,
            startup_command,
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
            privileged=True,
            user="root",
            environment={**env_vars, "TERM": "dumb", "PS1": "$ ", "PROMPT_COMMAND": ""},
        )
        self.exec_id = exec_data["Id"]

        # 启动一个 exec 实例
        socket_data = self.api.exec_start(
            self.exec_id, socket=True, tty=True, stream=True, demux=True
        )
        
        # if hasattr(socket_data, "_sock"):
        #     self.socket = socket_data._sock
        #     self.socket.setblocking(False)
        # else:
        #     raise RuntimeError("Failed to get socket connection")

        ## 新增
        # 检查 socket_data 是否可作为 socket 使用,兼容 windows docker socket
        if hasattr(socket_data, "setblocking"):
            self.socket = socket_data
        elif hasattr(socket_data, "_sock"):
            self.socket = socket_data._sock
        else:
            print(f"-----------socket_data type------------: {type(socket_data)}")
            print(f"-----------socket_data dir------------: {dir(socket_data)}")
            raise RuntimeError("Failed to get socket connection")
        await self._read_until_prompt()

    async def close(self) -> None:
        """Cleans up session resources.
        1. Sends exit command
        2. Closes socket connection
        3. Checks and cleans up exec instance
        """
        try:
            if self.socket:
                # Send exit command to close bash session
                try:
                    self.socket.sendall(b"exit\n")
                    # Allow time for command execution
                    await asyncio.sleep(0.1)
                except:
                    pass  # Ignore sending errors, continue cleanup

                # Close socket connection
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass  # Some platforms may not support shutdown

                self.socket.close()
                self.socket = None

            if self.exec_id:
                try:
                    # Check exec instance status
                    exec_inspect = self.api.exec_inspect(self.exec_id)
                    if exec_inspect.get("Running", False):
                        # If still running, wait for it to complete
                        await asyncio.sleep(0.5)
                except:
                    pass  # Ignore inspection errors, continue cleanup

                self.exec_id = None

        except Exception as e:
            # Log error but don't raise, ensure cleanup continues
            print(f"Warning: Error during session cleanup: {e}")

    async def _read_until_prompt(self) -> str:
        """Reads output until prompt is found.
        Returns:
            String containing output up to the prompt.
        Raises:
            socket.error: If socket communication fails.
        """
        buffer = b""
        while b"$ " not in buffer:
            try:
                chunk = self.socket.recv(4096)
                if chunk:
                    buffer += chunk
            except socket.error as e:
                if e.errno == socket.EWOULDBLOCK:
                    await asyncio.sleep(0.1)
                    continue
                raise
        return buffer.decode("utf-8")

    async def execute(self, command: str, timeout: Optional[int] = None) -> str:
        """执行命令并返回清理后的输出。
        参数：
            command：要执行的shell命令。
            timeout：最大执行时间（秒）。
        返回：
            去除提示符标记后的命令输出作为字符串。
        异常：
            RuntimeError：如果会话未初始化或执行失败。
            TimeoutError：如果命令执行超时
        """
        # 检查 socket 是否存在
        if not self.socket:
            raise RuntimeError("Session not initialized")

        try:
            # 清理命令以防止shell注入
            sanitized_command = self._sanitize_command(command)
            # 获取清洗后的命令
            # full_command = f"{sanitized_command}\necho $?\n"
            full_command = f"bash -c '{sanitized_command}' && echo $?\n"
            # 发送命令
            self.socket.sendall(full_command.encode())
            print(f"=============Command sent:========== {full_command}")
            # 从 socket 读取输出，直到提示符 $ 出现
            async def read_output() -> str:
                buffer = b""
                result_lines = []
                command_sent = False

                while True:
                    try:
                        # 新增
                        chunk = await asyncio.to_thread(self.socket.recv, 4096)
                        print(f"Received chunk: {chunk}")
                        if not chunk:
                            print(f"-----------------chunk-----------------: {chunk}")
                            if buffer.endswith(b"$ "):
                                break
                            raise RuntimeError("Socket closed unexpectedly")
                        
                        buffer += chunk
                        lines = buffer.split(b"\n")

                        buffer = lines[-1]
                        lines = lines[:-1]

                        for line in lines:
                            line = line.rstrip(b"\r")

                            # 新增
                            print(f"Processing line: {line}")

                            if not command_sent:
                                command_sent = True
                                continue
                            
                            if line.strip() == b"echo $?" or line.strip().isdigit():
                                continue

                            if line.strip():
                                result_lines.append(line)

                        if buffer.endswith(b"$ "):
                            print("Exit code and prompt found, breaking")
                            break

                    except socket.error as e:
                        if e.errno == socket.EWOULDBLOCK:
                            # 新增
                            print("EWOULDBLOCK, waiting...")
                            await asyncio.sleep(0.1)
                            continue
                        raise

                output = b"\n".join(result_lines).decode("utf-8")
                output = re.sub(r"\n\$ echo \$\$?.*$", "", output)

                # 新增
                print(f"Output before return: {output}")

                return output

            if timeout:
                # 如果有 timeout 参数，使用 asyncio.wait_for 限制 read_output 的执行时间
                result = await asyncio.wait_for(read_output(), timeout)
            else:
                result = await read_output()

            return result.strip()

        except asyncio.TimeoutError:
            raise TimeoutError(f"Command execution timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Failed to execute command: {e}")

    def _sanitize_command(self, command: str) -> str:
        """清理命令字符串以防止shell注入。
        参数：
            command：原始命令字符串。
        返回：
            清理后的命令字符串。
        异常：
            ValueError：如果命令包含潜在危险的模式。
        """

        # 针对特定危险命令的额外检查
        risky_commands = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            "dd if=/dev/zero",
            ":(){:|:&};:",
            "chmod -R 777 /",
            "chown -R",
        ]

        for risky in risky_commands:
            if risky in command.lower():
                raise ValueError(
                    f"Command contains potentially dangerous operation: {risky}"
                )

        #return command
        return command.replace("'", "'\\''")


class AsyncDockerizedTerminal:
    def __init__(
        self,
        container: Union[str, Container],
        working_dir: str = "/workspace",
        env_vars: Optional[Dict[str, str]] = None,
        default_timeout: int = 60,
    ) -> None:
        """初始化一个异步终端以用于Docker容器。
        参数：
            container：Docker 容器ID或Container对象。
            working_dir：容器内的工作目录。
            env_vars：要设置的环境变量。
            default_timeout：默认命令执行超时时间（秒）。
        """
        self.client = docker.from_env()
        self.container = (
            container
            if isinstance(container, Container)
            else self.client.containers.get(container)
        )
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.default_timeout = default_timeout
        self.session = None

    async def init(self) -> None:
        """初始化终端环境。
        确保工作目录存在并创建一个交互式会话。
        异常：
            RuntimeError：如果初始化失败。
        """
        await self._ensure_workdir()
        self.session = DockerSession(self.container.id)
        await self.session.create(self.working_dir, self.env_vars)

    async def _ensure_workdir(self) -> None:
        """确保容器中存在工作目录。
        异常：
            RuntimeError：如果目录创建失败。
        """
        try:
            await self._exec_simple(f"mkdir -p {self.working_dir}")
        except APIError as e:
            raise RuntimeError(f"Failed to create working directory: {e}")

    async def _exec_simple(self, cmd: str) -> Tuple[int, str]:
        """使用Docker的exec_run执行一个简单的命令。
        参数：
            cmd：要执行的命令。
        返回：
            元组（退出码，输出）。
        """
        result = await asyncio.to_thread(
            self.container.exec_run, cmd, environment=self.env_vars
        )
        return result.exit_code, result.output.decode("utf-8")

    async def run_command(self, cmd: str, timeout: Optional[int] = None) -> str:
        """在容器中带超时地运行一个命令。
        参数：
            cmd：要执行的shell命令。
            timeout：最大执行时间（秒）。
        返回：
            命令输出作为字符串。
        异常：
            RuntimeError：如果终端未初始化。
        """
        if not self.session:
            raise RuntimeError("Terminal not initialized")

        return await self.session.execute(cmd, timeout=timeout or self.default_timeout)

    async def close(self) -> None:
        """关闭终端会话。"""
        if self.session:
            await self.session.close()

    async def __aenter__(self) -> "AsyncDockerizedTerminal":
        """异步上下文管理器入口。"""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器退出"""
        await self.close()
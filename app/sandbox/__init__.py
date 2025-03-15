"""
Docker 沙箱模块
提供一个带有资源限制和隔离的安全容器化执行环境，用于运行不可信代码。
"""
from app.sandbox.client import (
    BaseSandboxClient,
    LocalSandboxClient,
    create_sandbox_client,
)
from app.sandbox.core.exceptions import (
    SandboxError,
    SandboxResourceError,
    SandboxTimeoutError,
)
from app.sandbox.core.manager import SandboxManager
from app.sandbox.core.sandbox import DockerSandbox


__all__ = [
    "DockerSandbox",
    "SandboxManager",
    "BaseSandboxClient",
    "LocalSandboxClient",
    "create_sandbox_client",
    "SandboxError",
    "SandboxTimeoutError",
    "SandboxResourceError",
]
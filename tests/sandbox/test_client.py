import tempfile
from pathlib import Path
from typing import AsyncGenerator
import sys


# 将项目根目录添加到 sys.path，以便导入 app 包
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

import pytest
import pytest_asyncio

from app.config import SandboxConfig
from app.sandbox.client import LocalSandboxClient, create_sandbox_client


@pytest_asyncio.fixture(scope="function")
async def local_client() -> AsyncGenerator[LocalSandboxClient, None]:
    """创建一个本地沙箱客户端用于测试。"""
    client = await create_sandbox_client()
    try:
        yield client
    finally:
        await client.cleanup()


@pytest.fixture(scope="function")
def temp_dir() -> Path:
    """为测试创建一个临时目录。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.mark.asyncio
async def test_sandbox_creation(local_client: LocalSandboxClient):
    """使用特定配置测试沙箱的创建。"""
    config = SandboxConfig(
        image="python:3.10-slim",
        work_dir="/workspace",
        memory_limit="512m",
        cpu_limit=0.5,
    )

    await local_client.create(config)

    result = await local_client.run_command("python3 --version")
    print(f"---------------------------------------: {result}")
    assert "Python 3.10" in result


@pytest.mark.asyncio
async def test_local_command_execution(local_client: LocalSandboxClient):
    """在本地沙箱中测试命令执行。"""
    await local_client.create()

    # 测试沙箱运行 echo 命令
    result = await local_client.run_command("echo 'test'")
    assert result.strip() == "test"

    # 测试沙箱运行 sleep 命令，并触发超时
    with pytest.raises(Exception):
        await local_client.run_command("sleep 10", timeout=1)


@pytest.mark.asyncio
async def test_local_file_operations(local_client: LocalSandboxClient, temp_dir: Path):
    """在本地沙箱中测试文件操作"""
    await local_client.create()

    # Test write and read operations
    test_content = "Hello, World!"
    await local_client.write_file("/workspace/test.txt", test_content)
    content = await local_client.read_file("/workspace/test.txt")
    assert content.strip() == test_content

    # Test copying file to container
    src_file = temp_dir / "src.txt"
    src_file.write_text("Copy to container")
    await local_client.copy_to(str(src_file), "/workspace/copied.txt")
    content = await local_client.read_file("/workspace/copied.txt")
    assert content.strip() == "Copy to container"

    # Test copying file from container
    dst_file = temp_dir / "dst.txt"
    await local_client.copy_from("/workspace/test.txt", str(dst_file))
    assert dst_file.read_text().strip() == test_content


@pytest.mark.asyncio
async def test_local_volume_binding(local_client: LocalSandboxClient, temp_dir: Path):
    """在本地沙箱中测试卷绑定。"""
    bind_path = str(temp_dir)
    volume_bindings = {bind_path: "/data"}

    await local_client.create(volume_bindings=volume_bindings)

    test_file = temp_dir / "test.txt"
    test_file.write_text("Volume test")

    content = await local_client.read_file("/data/test.txt")
    assert "Volume test" in content


@pytest.mark.asyncio
async def test_local_error_handling(local_client: LocalSandboxClient):
    """在本地沙箱中测试错误处理。"""
    await local_client.create()

    with pytest.raises(Exception) as exc:
        await local_client.read_file("/nonexistent.txt")
    assert "not found" in str(exc.value).lower()

    with pytest.raises(Exception) as exc:
        await local_client.copy_from("/nonexistent.txt", "local.txt")
    assert "not found" in str(exc.value).lower()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
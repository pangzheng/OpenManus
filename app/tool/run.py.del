"""一个用于异步运行shell命令并设置超时的实用程序。"""

# 导入 asyncio 库，用于异步 I/O 操作
import asyncio

# TRUNCATED_MESSAGE，当输出内容过长被截断时，会在截断处添加此消息
# 仅显示了文件部分内容，应该使用 `grep -n` 搜索文件以找到所需行号后再次尝试此工具
TRUNCATED_MESSAGE: str = "<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>"
# MAX_RESPONSE_LEN，用于指定最大响应长度
MAX_RESPONSE_LEN: int = 16000


def maybe_truncate(content: str, truncate_after: int | None = MAX_RESPONSE_LEN):
    """
    如果内容超过指定长度，截断内容并追加通知消息
    :param content: 要检查和可能截断的字符串内容
    :param truncate_after: 截断的长度阈值，默认为 MAX_RESPONSE_LEN
    :return: 截断后的内容（如果需要）或原始内容
    """
    return (
        content
        # 如果 truncate_after 为 None 或者 content 的长度小于等于 truncate_after，返回原始 content
        if not truncate_after or len(content) <= truncate_after
        # 否则，返回截断到 truncate_after 长度的 content 加上截断通知消息 TRUNCATED_MESSAGE
        else content[:truncate_after] + TRUNCATED_MESSAGE
    )


async def run(
    cmd: str,
    timeout: float | None = 120.0,  # seconds
    truncate_after: int | None = MAX_RESPONSE_LEN,
):
    """
    # 异步运行 shell 命令并设置超时时间
    :param cmd: 要运行的 shell 命令字符串
    :param timeout: 命令运行的超时时间，单位为秒，默认为 120 秒
    :param truncate_after: 输出内容截断的长度阈值，默认为 MAX_RESPONSE_LEN
    :return: 一个包含返回码、可能截断后的标准输出、可能截断后的标准错误输出的元组
    """

    # 使用 asyncio.create_subprocess_shell 创建一个异步子进程来执行 shell 命令
    # 将标准输出和标准错误输出都设置为管道，以便后续读取
    process = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    try:
        # 等待子进程完成，并设置超时时间
        # communicate 方法会等待子进程结束，并返回标准输出和标准错误输出
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        # 返回一个元组，包含子进程的返回码（如果为 None 则设为 0）
        # 以及经过可能截断处理后的标准输出和标准错误输出
        return (
            process.returncode or 0,
            maybe_truncate(stdout.decode(), truncate_after=truncate_after),
            maybe_truncate(stderr.decode(), truncate_after=truncate_after),
        )
    except asyncio.TimeoutError as exc:
        # 如果超时，尝试终止子进程
        try:
            process.kill()
        # 如果子进程已经不存在（例如已经提前结束），忽略此异常
        except ProcessLookupError:
            pass
        # 抛出一个自定义的 TimeoutError 异常，并附带超时的命令和超时时间信息
        # 同时将原始的 asyncio.TimeoutError 作为异常的上下文
        raise TimeoutError(
            f"Command '{cmd}' timed out after {timeout} seconds"
        ) from exc

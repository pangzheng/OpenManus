from collections import defaultdict
from pathlib import Path
from typing import Literal, get_args

from app.exceptions import ToolError
from app.tool import BaseTool
from app.tool.base import CLIResult, ToolResult
from app.tool.run import run

# 定义Command类型，它是一个字面量类型，包含几个特定的命令字符串
Command = Literal[
    "view",
    "create",
    "str_replace",
    "insert",
    "undo_edit",
]
# 定义常量SNIPPET_LINES，用于表示代码片段的行数
SNIPPET_LINES: int = 4

# 定义常量MAX_RESPONSE_LEN，用于表示最大响应长度
MAX_RESPONSE_LEN: int = 16000

# 定义常量TRUNCATED_MESSAGE，用于表示截断响应时附加的提示信息,仅显示了文件部分内容，
# 您应该使用 `grep -n` 搜索文件以找到所需行号后再次尝试此工具。
TRUNCATED_MESSAGE: str = "<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>"

"""
<响应截断><注意>为了节省上下文，仅显示了此文件的部分内容。您应该在使用`grep -n`搜索文件后再重新尝试此工具，以便找到您要查找的行号。
"""

_STR_REPLACE_EDITOR_DESCRIPTION = """Custom editing tool for viewing, creating and editing files
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
* The `new_str` parameter should contain the edited lines that should replace the `old_str`
"""

"""
自定义文件查看、创建和编辑工具:
* 状态在命令调用和与用户的讨论中保持持久化
* 如果`path`是一个文件，`view`将显示应用 `cat -n` 的结果。
* 如果`path`是一个目录，`view`将列出非隐藏文件和最多2级深的目录
* 如果指定的`path`已经存在为文件，则不能使用`create`命令
* 如果`command`生成了长输出，它将被截断并标记为 `<response clipped>`
* `undo_edit` 命令将撤销对`path`文件所做的最后一次编辑

关于使用`str_replace`命令的注意事项：
* `old_str`参数应完全匹配原文件中的一个或多个连续行。注意空白符！
* 如果`old_str`参数在文件中不唯一，则不会进行替换。确保在`old_str`中包含足够的上下文以使其独特
* `new_str`参数应包含用于替换`old_str`的编辑行```
"""

# 定义 maybe_truncate 函数，如果内容超过指定长度，则截断内容并附加一条通知。
def maybe_truncate(content: str, truncate_after: int | None = MAX_RESPONSE_LEN):
    """Truncate content and append a notice if content exceeds the specified length."""
    return (
        content
        if not truncate_after or len(content) <= truncate_after
        else content[:truncate_after] + TRUNCATED_MESSAGE
    )

# 定义StrReplaceEditor类，继承自BaseTool，
class StrReplaceEditor(BaseTool):
    """用于执行bash命令的工具类"""

    #名称
    name: str = "str_replace_editor"
    # 描述
    description: str = _STR_REPLACE_EDITOR_DESCRIPTION
    # 参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.",
                "enum": ["view", "create", "str_replace", "insert", "undo_edit"],
                "type": "string",
            },
            # 运行的命令。
            # 允许的选项是：`view`, `create`, `str_replace`, `insert`,`undo_edit`。
            "path": {
                "description": "Absolute path to file or directory.",
                "type": "string",
            },
            # 文件或目录的绝对路径
            "file_text": {
                "description": "Required parameter of `create` command, with the content of the file to be created.",
                "type": "string",
            },
            # create`命令所需的参数，包含要创建的文件的内容。
            "old_str": {
                "description": "Required parameter of `str_replace` command containing the string in `path` to replace.",
                "type": "string",
            },
            # str_replace 命令所需的参数，包含在path`中进行替换的字符串。
            "new_str": {
                "description": "Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.",
                "type": "string",
            },
            # str_replace 命令的可选参数，包含新字符串（如果没有给出，则不会添加任何字符串）。insert`命令所需的参数，包含要插入的字符串
            "insert_line": {
                "description": "Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.",
                "type": "integer",
            },
            # insert命令所需的参数。new_str将在path的insert_line`行之后插入。
            "view_range": {
                "description": "Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.",
                "items": {"type": "integer"},
                "type": "array",
            },
            ## view 命令的可选参数，当 path`指向文件时。
            # 如果没有提供，则显示整个文件。
            # 如果提供了，则将显示指示的行号范围内的文件内容，
            # 例如[11, 12]将显示第11和12行。从索引1开始计数。设置[start_line, -1]将从start_line 到文件末尾显示所有行。
        },
        # 必填参数
        "required": ["command", "path"],
    }

    # 定义类属性_file_history，用于存储文件的历史内容，使用defaultdict创建默认值为列表的字典
    _file_history: list = defaultdict(list)

    # 定义execute方法，用于执行工具的具体操作，接受命令、路径等参数
    async def execute(
        self,
        *,
        command: Command,
        path: str,
        file_text: str | None = None,
        view_range: list[int] | None = None,
        old_str: str | None = None,
        new_str: str | None = None,
        insert_line: int | None = None,
        **kwargs,
    ) -> str:
        # 将路径字符串转换为Path对象
        _path = Path(path)
        # 验证路径和命令的组合是否有效
        self.validate_path(command, _path)
        # 根据不同的命令执行相应的操作
        if command == "view":
            result = await self.view(_path, view_range)
        elif command == "create":
            # 如果创建命令时没有提供文件内容，抛出工具错误 
            if file_text is None:
                raise ToolError("Parameter `file_text` is required for command: create")
            # 写入文件内容
            self.write_file(_path, file_text)
            # 将文件内容添加到历史记录中
            self._file_history[_path].append(file_text)
            # 返回创建成功的结果
            result = ToolResult(output=f"File created successfully at: {_path}")
        elif command == "str_replace":
            # 如果替换命令时没有提供旧字符串，抛出工具错误
            if old_str is None:
                raise ToolError(
                    "Parameter `old_str` is required for command: str_replace"
                )
            # 执行字符串替换操作
            result = self.str_replace(_path, old_str, new_str)
        elif command == "insert":
            # 如果插入命令时没有提供插入行号，抛出工具错误
            if insert_line is None:
                raise ToolError(
                    "Parameter `insert_line` is required for command: insert"
                )
             # 如果插入命令时没有提供新字符串，抛出工具错误
            if new_str is None:
                raise ToolError("Parameter `new_str` is required for command: insert")
            # 执行插入操作
            result = self.insert(_path, insert_line, new_str)
        elif command == "undo_edit":
            # 执行撤销编辑操作
            result = self.undo_edit(_path)
        else:
            # 如果命令不被识别，抛出工具错误，提示允许的命令
            raise ToolError(
                f'Unrecognized command {command}. The allowed commands for the {self.name} tool are: {", ".join(get_args(Command))}'
            )
        # 返回操作结果的字符串表示
        return str(result)
    
    # 定义validate_path方法，用于验证路径和命令的组合是否有效
    def validate_path(self, command: str, path: Path):
        # 检查是否是绝对路径，如果不是，抛出工具错误并提示可能的正确路径
        if not path.is_absolute():
            suggested_path = Path("") / path
            raise ToolError(
                f"The path {path} is not an absolute path, it should start with `/`. Maybe you meant {suggested_path}?"
            )
        # 检查路径是否存在，如果不存在且不是创建命令，抛出工具错误
        if not path.exists() and command != "create":
            raise ToolError(
                f"The path {path} does not exist. Please provide a valid path."
            )
        # 检查路径存在且是创建命令，如果是冲突，抛出工具错误
        if path.exists() and command == "create":
            raise ToolError(
                f"File already exists at: {path}. Cannot overwrite files using command `create`."
            )
        # 检查路径是否指向目录，如果是且不是查看命令，抛出工具错误
        if path.is_dir():
            if command != "view":
                raise ToolError(
                    f"The path {path} is a directory and only the `view` command can be used on directories"
                )
    # 定义view方法，实现查看命令的功能
    async def view(self, path: Path, view_range: list[int] | None = None):
        # 如果路径指向目录
        if path.is_dir():
            # 如果提供了view_range参数，抛出工具错误
            if view_range:
                raise ToolError(
                    "The `view_range` parameter is not allowed when `path` points to a directory."
                )
            # 运行外部命令，查找目录下不超过2层深度且不包含隐藏文件的绝对路径
            _, stdout, stderr = await run(
                rf"find {path} -maxdepth 2 -not -path '*/\.*'"
            )
            # 如果没有错误，格式化输出内容，
            # 在{path}中最多2级深的文件和目录，不包括隐藏项：\n{stdout}
            if not stderr:
                stdout = f"Here's the files and directories up to 2 levels deep in {path}, excluding hidden items:\n{stdout}\n"
            return CLIResult(output=stdout, error=stderr)

        # 读取文件内容
        file_content = self.read_file(path)
        # 初始化行号为1
        init_line = 1
        # 如果提供了view_range参数
        if view_range:
            # 检查view_range参数格式是否正确，如果不正确，抛出工具错误
            if len(view_range) != 2 or not all(isinstance(i, int) for i in view_range):
                raise ToolError(
                    "Invalid `view_range`. It should be a list of two integers."
                )
            # 将文件内容按行分割
            file_lines = file_content.split("\n")
            # 获取文件的行数
            n_lines_file = len(file_lines)
            # 获取起始行号和结束行号
            init_line, final_line = view_range
            # 检查起始行号是否有效，如果无效，抛出工具错误
            if init_line < 1 or init_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its first element `{init_line}` should be within the range of lines of the file: {[1, n_lines_file]}"
                )
            # 检查结束行号是否有效，如果无效，抛出工具错误
            if final_line > n_lines_file:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be smaller than the number of lines in the file: `{n_lines_file}`"
                )
             # 检查结束行号是否小于起始行号，如果是，抛出工具错误
            if final_line != -1 and final_line < init_line:
                raise ToolError(
                    f"Invalid `view_range`: {view_range}. Its second element `{final_line}` should be larger or equal than its first `{init_line}`"
                )
            # 如果结束行号为-1，截取从起始行到文件末尾的内容
            if final_line == -1:
                file_content = "\n".join(file_lines[init_line - 1 :])
            else:
                # 否则，截取指定行号范围内的内容
                file_content = "\n".join(file_lines[init_line - 1 : final_line])

        # 返回命令行结果，包含格式化后的文件内容
        return CLIResult(
            output=self._make_output(file_content, str(path), init_line=init_line)
        )

    # 定义str_replace方法，在文件内容中将old_str替换为new_str
    def str_replace(self, path: Path, old_str: str, new_str: str | None):
        # 读取文件内容并展开制表符
        file_content = self.read_file(path).expandtabs()
        # 展开旧字符串的制表符
        old_str = old_str.expandtabs()
        # 如果新字符串存在，展开制表符，否则为空字符串
        new_str = new_str.expandtabs() if new_str is not None else ""

        # 检查旧字符串在文件中出现的次数
        occurrences = file_content.count(old_str)
        # 如果旧字符串未出现，抛出工具错误
        if occurrences == 0:
            raise ToolError(
                f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {path}."
            )
        # 如果旧字符串出现多次，抛出工具错误并提示行号
        # 没有进行任何替换。在多行{lines}中出现了多次old_str `{old_str}`。请确保它是唯一的
        elif occurrences > 1:
            file_content_lines = file_content.split("\n")
            lines = [
                idx + 1
                for idx, line in enumerate(file_content_lines)
                if old_str in line
            ]
            raise ToolError(
                f"No replacement was performed. Multiple occurrences of old_str `{old_str}` in lines {lines}. Please ensure it is unique"
            )

        # 替换文件内容中的旧字符串为新字符串
        new_file_content = file_content.replace(old_str, new_str)

        # 将新内容写入文件
        self.write_file(path, new_file_content)

        # 将旧内容保存到历史记录中
        self._file_history[path].append(file_content)

        # 创建编辑部分的代码片段
        replacement_line = file_content.split(old_str)[0].count("\n")
        start_line = max(0, replacement_line - SNIPPET_LINES)
        end_line = replacement_line + SNIPPET_LINES + new_str.count("\n")
        snippet = "\n".join(new_file_content.split("\n")[start_line : end_line + 1])

        # 准备成功消息
        success_msg = f"The file {path} has been edited. "
        success_msg += self._make_output(
            snippet, f"a snippet of {path}", start_line + 1
        )
        success_msg += "Review the changes and make sure they are as expected. Edit the file again if necessary."

        # 返回命令行结果，包含成功消息
        return CLIResult(output=success_msg)

    # 定义insert方法，在文件内容中的指定行插入new_str。
    def insert(self, path: Path, insert_line: int, new_str: str):
        # 读取文件内容并展开制表符
        file_text = self.read_file(path).expandtabs()
        # 展开新字符串的制表符
        new_str = new_str.expandtabs()
        # 将文件内容按行分割
        file_text_lines = file_text.split("\n")
        # 获取文件的行数
        n_lines_file = len(file_text_lines)
        
        # 检查插入行号是否有效，如果无效，抛出工具错误
        if insert_line < 0 or insert_line > n_lines_file:
            raise ToolError(
                f"Invalid `insert_line` parameter: {insert_line}. It should be within the range of lines of the file: {[0, n_lines_file]}"
            )
        
        # 将新字符串按行分割
        new_str_lines = new_str.split("\n")
        # 构建插入新字符串后的文件内容行列表
        new_file_text_lines = (
            file_text_lines[:insert_line]
            + new_str_lines
            + file_text_lines[insert_line:]
        )
        # 构建插入部分的代码片段行列表
        snippet_lines = (
            file_text_lines[max(0, insert_line - SNIPPET_LINES) : insert_line]
            + new_str_lines
            + file_text_lines[insert_line : insert_line + SNIPPET_LINES]
        )
        # 将新的文件内容行列表合并为字符串
        new_file_text = "\n".join(new_file_text_lines)
        # 将代码片段行列表合并为字符串
        snippet = "\n".join(snippet_lines)
        
        # 将新内容写入文件
        self.write_file(path, new_file_text)
        self._file_history[path].append(file_text)
        # 成功信息拼装
        success_msg = f"The file {path} has been edited. "
        success_msg += self._make_output(
            snippet,
            "a snippet of the edited file",
            max(1, insert_line - SNIPPET_LINES + 1),
        )
        success_msg += "Review the changes and make sure they are as expected (correct indentation, no duplicate lines, etc). Edit the file again if necessary."
        return CLIResult(output=success_msg)

    def undo_edit(self, path: Path):
        """实现undo_edit命令。"""
        # 检查文件是否有编辑历史
        if not self._file_history[path]:
            raise ToolError(f"No edit history found for {path}.")
        # 获取并移除最后一次编辑的旧内容
        old_text = self._file_history[path].pop()
        # 将旧内容写回文件
        self.write_file(path, old_text)
        # 返回撤销成功的消息
        return CLIResult(
            output=f"Last edit to {path} undone successfully. {self._make_output(old_text, str(path))}"
        )

    def read_file(self, path: Path):
        """从给定路径读取文件的内容；如果发生错误则抛出ToolError。"""
        try:
            # 尝试读取文件内容
            return path.read_text()
        # 如果读取过程中出现异常，抛出ToolError，并附带异常信息
        except Exception as e:
            raise ToolError(f"Ran into {e} while trying to read {path}") from None

    def write_file(self, path: Path, file: str):
        """从给定路径写入文件的内容；如果发生错误则抛出ToolError。"""
        try:
            # 尝试将内容写入文件
            path.write_text(file)
        except Exception as e:
            # 如果写入过程中出现异常，抛出ToolError，并附带异常信息
            raise ToolError(f"Ran into {e} while trying to write to {path}") from None

    def _make_output(
        self,
        file_content: str,
        file_descriptor: str,
        init_line: int = 1,
        expand_tabs: bool = True,
    ):
        """根据文件内容生成基于CLI的输出。"""
        # 对文件内容进行截断处理
        file_content = maybe_truncate(file_content)
        # 如果需要展开制表符
        if expand_tabs:
            file_content = file_content.expandtabs()
        # 为文件内容的每一行添加行号，并格式化输出
        file_content = "\n".join(
            [
                f"{i + init_line:6}\t{line}"
                for i, line in enumerate(file_content.split("\n"))
            ]
        )
        # 返回格式化后的输出字符串，包含文件描述信息
        return (
            f"Here's the result of running `cat -n` on {file_descriptor}:\n"
            + file_content
            + "\n"
        )

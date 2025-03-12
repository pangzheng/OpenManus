import asyncio
import os

import aiofiles

from app.tool.base import BaseTool

# 定义 FileSaver 的类，继承 BaseTool
class FileSaver(BaseTool):
    # 名称
    name: str = "file_saver"
    # 描述
    description: str = """Save content to a local file at a specified path.
    Use this tool when you need to save text, code, or generated content to a file on the local filesystem.
    The tool accepts content and a file path, and saves the content to that location.
    """
    # 在需要将文本、代码或生成的内容保存到本地文件系统中的文件时使用此工具。
    # 该工具接受内容和文件路径，并将内容保存到该位置。
    
    # 定义参数结构(字典)
    parameters: dict = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "(required) The content to save to the file.",
            },
            # content 参数，必填，类型为字符串，描述为要保存到文件中的内容
            "file_path": {
                "type": "string",
                "description": "(required) The path where the file should be saved, including filename and extension.",
            },
            # file_path参数，必填，类型为字符串，描述为文件应保存的路径，包括文件名和扩展名
            "mode": {
                "type": "string",
                "description": "(optional) The file opening mode. Default is 'w' for write. Use 'a' for append.",
                "enum": ["w", "a"],
                "default": "w",
            },
            # mode参数，选填，类型为字符串，描述为文件打开模式，默认是'w'（写入），也可使用'a'（追加）
        },
        # 定义必填参数为content和file_path
        "required": ["content", "file_path"],
    }

    # 
    async def execute(self, content: str, file_path: str, mode: str = "w") -> str:
        """
        定义一个异步执行方法，用于将内容保存到指定路径的文件中

        Args:
            content (str): 要保存到文件的内容。
            file_path (str): 文件应保存的路径。
            mode (str, optional): 文件打开模式。默认为写入模式'w'。使用'a'进行追加。
        Returns:
            str: 操作结果的消息。
        """
       
        try:
            # # 获取文件路径中的目录部分
            directory = os.path.dirname(file_path)
            
            # 如果目录不存在，则创建该目录（包括所有必要的父目录）
            if directory and not os.path.exists(directory):
                os.makedirs(directory)

            # 使用异步文件操作，以指定模式和UTF - 8编码打开文件
            async with aiofiles.open(file_path, mode, encoding="utf-8") as file:
                # 异步地将内容写入文件
                await file.write(content)

            # 返回保存成功的消息
            return f"Content successfully saved to {file_path}"
        
        # 如果在保存过程中发生任何异常
        except Exception as e:
            # 返回包含错误信息的消息
            return f"Error saving file: {str(e)}"


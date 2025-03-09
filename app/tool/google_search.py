# 导入asyncio库，用于支持异步编程
import asyncio
# 从typing模块导入List，用于类型提示，表示列表类型
from typing import List
# 从googlesearch库导入search函数，用于执行谷歌搜索
from googlesearch import search
# 从app.tool.base模块导入BaseTool类，这可能是所有工具类的基类
from app.tool.base import BaseTool

# 定义GoogleSearch类，继承自BaseTool类
class GoogleSearch(BaseTool):
    # 名称
    name: str = "google_search"
    # 描述
    description: str = """Perform a Google search and return a list of relevant links.
Use this tool when you need to find information on the web, get up-to-date data, or research specific topics.
The tool returns a list of URLs that match the search query.
"""
    # 在需要在网上查找信息、获取最新数据或研究特定主题时使用此工具。
    # 该工具返回与搜索查询匹配的URL列表。

    # 定义参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "(required) The search query to submit to Google.",
            },
            # （必填）要提交给Google的搜索查询。
            "num_results": {
                "type": "integer",
                "description": "(optional) The number of search results to return. Default is 10.",
                "default": 10,
            },
            # (可选)返回的搜索结果数量。默认为10。
        },
        "required": ["query"],
    }

    # 定义异步执行的 execute 方法 ，接收搜索查询字符串query和结果数量num_results（默认10），返回字符串列表
    async def execute(self, query: str, num_results: int = 10) -> List[str]:
        """
        Execute a Google search and return a list of URLs.

        Args:
            query (str): The search query to submit to Google.
            num_results (int, optional): The number of search results to return. Default is 10.

        Returns:
            List[str]: A list of URLs matching the search query.
        """
        # Args:
        #     query (str): 要提交给Google的搜索查询。
        #     num_results (int, optional): 返回的搜索结果数量。默认为10。
        # Returns:
        #     List[str]: 匹配搜索查询的URL列表。

        # 获取当前的事件循环
        loop = asyncio.get_event_loop()
        # 在一个线程池中运行search函数，以避免阻塞事件循环
        # 这里使用 lambda 表达式将 search 函数包装成一个可调用对象，
        # 并传入查询和结果数量参数，等待线程池执行完毕并返回搜索结果链接列表
        links = await loop.run_in_executor(
            None, lambda: list(search(query, num_results=num_results))
        )

        # 返回搜索得到的链接列表
        return links

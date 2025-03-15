import asyncio
import json
from typing import Optional

from browser_use import Browser as BrowserUseBrowser
from browser_use import BrowserConfig
from browser_use.browser.context import BrowserContext
from browser_use.dom.service import DomService
from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo
from app.tool.base import BaseTool, ToolResult

# 与web浏览器交互以执行各种操作，如导航、元素、内容提取和标签管理。支持的操作包括:
# - 'navigate'：访问特定URL
# - 'click'：通过索引点击元素
# - 'input_text'：向元素输入文本
# - 'screenshot'：捕获屏幕截图
# - 'get_html'：获取页面HTML内容
# - 'execute_js'：执行JavaScript代码
# - 'scroll'：滚动页面
# - 'switch_tab'：切换到特定标签页
# - 'new_tab'：打开新标签页
# - 'close_tab'：关闭当前标签页
# - 'refresh'：刷新当前页面

_BROWSER_DESCRIPTION = """
Interact with a web browser to perform various actions such as navigation, element interaction,
content extraction, and tab management. Supported actions include:
- 'navigate': Go to a specific URL
- 'click': Click an element by index
- 'input_text': Input text into an element
- 'screenshot': Capture a screenshot
- 'get_html': Get page HTML content
- 'get_text': Get text content of the page
- 'read_links': Get all links on the page
- 'execute_js': Execute JavaScript code
- 'scroll': Scroll the page
- 'switch_tab': Switch to a specific tab
- 'new_tab': Open a new tab
- 'close_tab': Close the current tab
- 'refresh': Refresh the current page
"""

# 定义了 BrowserUseTool ，继承 BaseTool
class BrowserUseTool(BaseTool):
    # 名字
    name: str = "browser_use"
    # 描述
    description: str = _BROWSER_DESCRIPTION
    # 参数，字典
    parameters: dict = {
        "type": "object",
        "properties": {
            # 操作类型，字符串类型，只能是指定枚举值之一
            "action": {
                "type": "string",
                "enum": [
                    "navigate",  # 导航到指定URL
                    "click", # 点击指定索引的元素
                    "input_text",  # 在指定索引的元素中输入文本
                    "screenshot", # 截取屏幕截图
                    "get_html", # 获取页面HTML
                    "get_text", # 获取页面文本
                    "execute_js", # 执行JavaScript代码
                    "scroll",  # 滚动页面
                    "switch_tab", # 切换到指定ID的标签页
                    "new_tab", # 打开新的标签页
                    "close_tab", # 关闭当前标签页
                    "refresh", # 刷新当前页面
                ],
                "description": "The browser action to perform",},
                # 游览器可执行操作
            "url": {
                "type": "string",
                "description": "URL for 'navigate' or 'new_tab' actions",},
                # 用于'navigate'或'new_tab'操作的URL
            "index": {
                "type": "integer",
                "description": "Element index for 'click' or 'input_text' actions",},
                # 用于'click'或'input_text'操作的元素索引
            "text": {
                "type": "string", "description": "Text for 'input_text' action"},
                # 用于'input_text'操作的文本
            "script": {
                "type": "string",
                "description": "JavaScript code for 'execute_js' action",},
                # 用于'execute_js'操作的JavaScript代码
            "scroll_amount": {
                "type": "integer",
                "description": "Pixels to scroll (positive for down, negative for up) for 'scroll' action",},
                # 用于'scroll'操作的滚动像素数（正数表示向下，负数表示向上）
            "tab_id": {
                "type": "integer",
                "description": "Tab ID for 'switch_tab' action",},
                # 标签页ID，用于切换标签页操作
        },
        # 必须包含action参数
        "required": ["action"],
        # 操作与参数的依赖关系
        "dependencies": {
            "navigate": ["url"],
            "click": ["index"],
            "input_text": ["index", "text"],
            "execute_js": ["script"],
            "switch_tab": ["tab_id"],
            "new_tab": ["url"],
            "scroll": ["scroll_amount"],
        },
    }

    # 定义异步锁，用于线程安全地访问共享资源
    lock: asyncio.Lock = Field(default_factory=asyncio.Lock)
    # 浏览器对象，初始为 None，exclude=True 表示在某些序列化操作中排除该字段
    browser: Optional[BrowserUseBrowser] = Field(default=None, exclude=True)
    # 浏览器上下文对象，初始为None，exclude=True表示在某些序列化操作中排除该字段
    context: Optional[BrowserContext] = Field(default=None, exclude=True)
    # DOM服务对象，初始为None，exclude=True表示在某些序列化操作中排除该字段
    dom_service: Optional[DomService] = Field(default=None, exclude=True)

    # 参数验证器，在参数验证之前执行
    @field_validator("parameters", mode="before")
    def validate_parameters(cls, v: dict, info: ValidationInfo) -> dict:
        # 如果参数为空，抛出异常
        if not v:
            raise ValueError("Parameters cannot be empty")
        # 正常返回验证后的参数    
        return v

    async def _ensure_browser_initialized(self) -> BrowserContext:
        """确保浏览器和上下文已初始化的异步方法"""
        # 如果浏览器对象为空，则创建一个新的浏览器对象
        if self.browser is None:
            self.browser = BrowserUseBrowser(BrowserConfig(headless=False))
        # 如果上下文对象为空，则创建一个新的上下文对象，并初始化DOM服务
        if self.context is None:
            self.context = await self.browser.new_context()
            self.dom_service = DomService(await self.context.get_current_page())
        # 返回上下文对象    
        return self.context

    # 执行指定浏览器操作的异步方法
    async def execute(
        self,
        action: str,
        url: Optional[str] = None,
        index: Optional[int] = None,
        text: Optional[str] = None,
        script: Optional[str] = None,
        scroll_amount: Optional[int] = None,
        tab_id: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        """
        执行指定的浏览器操作。
        Args:
            action: 要执行的浏览器操作
            url: 导航或新标签页的URL
            index: 点击或输入动作的元素索引
            text: 输入动作的文本
            script: 执行的动作的JavaScript代码
            scroll_amount: 滚动动作的像素数
            tab_id: 切换标签页动作的标签ID
            **kwargs: 额外的参数
        Returns:
            包含操作输出或错误的ToolResult
        """
        
        # 使用异步锁确保线程安全
        async with self.lock:
            try:
                # 确保浏览器和上下文已初始化
                context = await self._ensure_browser_initialized()

                # 如果操作是导航
                if action == "navigate":
                    # 如果URL为空，返回错误结果
                    if not url:
                        return ToolResult(error="URL is required for 'navigate' action")
                    # 执行导航操作
                    await context.navigate_to(url)
                    # 返回成功结果
                    return ToolResult(output=f"Navigated to {url}")

                # 如果操作是点击
                elif action == "click":
                    # 如果索引为空，返回错误结果
                    if index is None:
                        return ToolResult(error="Index is required for 'click' action")
                    # 获取指定索引的DOM元素
                    element = await context.get_dom_element_by_index(index)
                    # 如果元素不存在，返回错误结果
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                     # 点击元素并获取可能的下载路径
                    download_path = await context._click_element_node(element)
                    # 构建输出信息
                    output = f"Clicked element at index {index}"
                    if download_path:
                        output += f" - Downloaded file to {download_path}"
                    # 返回成功结果
                    return ToolResult(output=output)
                
                # 如果操作是输入文本
                elif action == "input_text":
                    # 如果索引或文本为空，返回错误结果
                    if index is None or not text:
                        return ToolResult(
                            error="Index and text are required for 'input_text' action"
                        )
                    # 获取指定索引的DOM元素
                    element = await context.get_dom_element_by_index(index)
                    # 如果元素不存在，返回错误结果
                    if not element:
                        return ToolResult(error=f"Element with index {index} not found")
                    # 在元素中输入文本
                    await context._input_text_element_node(element, text)
                    # 返回成功结果
                    return ToolResult(
                        output=f"Input '{text}' into element at index {index}"
                    )
                
                # 如果操作是截取屏幕截图
                elif action == "screenshot":
                    # 截取全屏截图
                    screenshot = await context.take_screenshot(full_page=True)
                     # 返回成功结果，包含截图信息
                    return ToolResult(
                        output=f"Screenshot captured (base64 length: {len(screenshot)})",
                        system=screenshot,
                    )
                
                # 如果操作是获取页面HTML
                elif action == "get_html":
                    # 获取页面HTML
                    html = await context.get_page_html()
                    # 如果HTML过长，截断并添加省略号
                    truncated = html[:2000] + "..." if len(html) > 2000 else html
                    # 返回成功结果
                    return ToolResult(output=truncated)

                # 如果操作是获取页面文本
                elif action == "get_text":
                    text = await context.execute_javascript("document.body.innerText")
                    return ToolResult(output=text)

                # 如果操作是获取页面所有链接
                elif action == "read_links":
                    links = await context.execute_javascript(
                        "document.querySelectorAll('a[href]').forEach((elem) => {if (elem.innerText) {console.log(elem.innerText, elem.href)}})"
                    )
                    return ToolResult(output=links)
                
                # 如果操作是执行JavaScript代码
                elif action == "execute_js":
                    # 如果脚本为空，返回错误结果
                    if not script:
                        return ToolResult(
                            error="Script is required for 'execute_js' action"
                        )
                    # 执行JavaScript代码并获取结果
                    result = await context.execute_javascript(script)
                    # 返回成功结果
                    return ToolResult(output=str(result))

                # 如果操作是滚动页面
                elif action == "scroll":
                    # 如果滚动距离为空，返回错误结果
                    if scroll_amount is None:
                        return ToolResult(
                            error="Scroll amount is required for 'scroll' action"
                        )
                    # 执行滚动操作
                    await context.execute_javascript(
                        f"window.scrollBy(0, {scroll_amount});"
                    )
                    # 确定滚动方向
                    direction = "down" if scroll_amount > 0 else "up"
                    # 返回成功结果
                    return ToolResult(
                        output=f"Scrolled {direction} by {abs(scroll_amount)} pixels"
                    )
                # 如果操作是切换标签页
                elif action == "switch_tab":
                    # 如果标签页ID为空，返回错误结果
                    if tab_id is None:
                        return ToolResult(
                            error="Tab ID is required for 'switch_tab' action"
                        )
                    # 切换到指定标签页
                    await context.switch_to_tab(tab_id)
                    # 返回成功结果
                    return ToolResult(output=f"Switched to tab {tab_id}")

                # 如果操作是打开新标签页
                elif action == "new_tab":
                    # 如果URL为空，返回错误结果
                    if not url:
                        return ToolResult(error="URL is required for 'new_tab' action")
                    # 打开新标签页
                    await context.create_new_tab(url)
                    # 返回成功结果
                    return ToolResult(output=f"Opened new tab with URL {url}")
                
                # 如果操作是关闭当前标签页
                elif action == "close_tab":
                    # 关闭当前标签页
                    await context.close_current_tab()
                    # 返回成功结果
                    return ToolResult(output="Closed current tab")

                # 如果操作是刷新当前页面
                elif action == "refresh":
                    # 刷新当前页面
                    await context.refresh_page()
                    # 返回成功结果
                    return ToolResult(output="Refreshed current page")
                
                # 如果是未知操作，返回错误结果
                else:
                    return ToolResult(error=f"Unknown action: {action}")
             # 捕获异常并返回错误结果
            except Exception as e:
                return ToolResult(error=f"Browser action '{action}' failed: {str(e)}")
     
    async def get_current_state(self) -> ToolResult:
        """获取当前浏览器状态作为ToolResult"""
        # 使用异步锁确保线程安全
        async with self.lock:
            try:
                # 确保浏览器和上下文已初始化
                context = await self._ensure_browser_initialized()
                # 获取浏览器状态
                state = await context.get_state()
                # 构建状态信息字典
                state_info = {
                    "url": state.url,
                    "title": state.title,
                    "tabs": [tab.model_dump() for tab in state.tabs],
                    "interactive_elements": state.element_tree.clickable_elements_to_string(),
                }
                # 返回成功结果，包含状态信息的JSON字符串
                return ToolResult(output=json.dumps(state_info))
            # 捕获异常并返回错误结果
            except Exception as e:
                return ToolResult(error=f"Failed to get browser state: {str(e)}")
    
    async def cleanup(self):
        """清理浏览器资源的异步方法"""
         # 使用异步锁确保线程安全
        async with self.lock:
            # 如果上下文对象存在，关闭上下文并清空相关对象
            if self.context is not None:
                await self.context.close()
                self.context = None
                self.dom_service = None
            # 如果浏览器对象存在，关闭浏览器并清空对象
            if self.browser is not None:
                await self.browser.close()
                self.browser = None

    def __del__(self):
        """对象销毁时的析构函数，确保资源清理"""
         # 如果浏览器或上下文对象存在
        if self.browser is not None or self.context is not None:
            # 尝试运行清理方法
            try:
                asyncio.run(self.cleanup())
            # 如果当前事件循环不可用，创建新的事件循环并运行清理方法
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.cleanup())
                loop.close()

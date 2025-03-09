from typing import Dict, List, Literal, Optional, Union

from openai import (
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
    AsyncAzureOpenAI
)
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.config import LLMSettings, config
from app.logger import logger  # Assuming a logger is set up in your app
from app.schema import Message

# LLM类，用于与大语言模型进行交互
class LLM:
    # 类属性，用于存储LLM类的实例，以实现单例模式
    _instances: Dict[str, "LLM"] = {}
    
    # 定义__new__方法，实现单例模式的创建逻辑
    def __new__(
        cls, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        # 如果指定名称的实例不存在
        if config_name not in cls._instances:
            # 创建新的实例
            instance = super().__new__(cls)
            # 初始化新实例
            instance.__init__(config_name, llm_config)
            # 将新实例存入_instances字典
            cls._instances[config_name] = instance
        # 返回已有的或新创建的实例
        return cls._instances[config_name]

    # 初始化方法，用于设置LLM的相关配置和创建客户端
    def __init__(
        self, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        # 如果实例还没有client属性
        if not hasattr(self, "client"):  # 仅在未初始化时进行初始化
            # 如果没有传入llm_config，则使用全局配置中的llm部分
            llm_config = llm_config or config.llm
            # 获取指定config_name的配置，如果不存在则使用默认配置
            llm_config = llm_config.get(config_name, llm_config["default"])
            # 设置模型名称
            self.model = llm_config.model
            # 设置最大生成令牌数
            self.max_tokens = llm_config.max_tokens
            # 设置温度参数，用于控制生成的随机性
            self.temperature = llm_config.temperature
            # 设置API类型，例如"azure"或其他
            self.api_type = llm_config.api_type
            # 设置API密钥
            self.api_key = llm_config.api_key
            # 设置API版本
            self.api_version = llm_config.api_version
            # 设置基础URL
            self.base_url = llm_config.base_url
            # 如果API类型是"azure"，则创建AsyncAzureOpenAI客户端
            if self.api_type == "azure":
                self.client = AsyncAzureOpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    api_version=self.api_version
                )
            # 否则，创建AsyncOpenAI客户端
            else:
                self.client = AsyncOpenAI(
                api_key=self.api_key, base_url=self.base_url
            )

    @staticmethod
    # 静态方法，用于将消息格式化为OpenAI所需的格式
    def format_messages(messages: List[Union[dict, Message]]) -> List[dict]:
        """
        Format messages for LLM by converting them to OpenAI message format.

        Args:
            messages: List of messages that can be either dict or Message objects

        Returns:
            List[dict]: List of formatted messages in OpenAI format

        Raises:
            ValueError: If messages are invalid or missing required fields
            TypeError: If unsupported message types are provided

        Examples:
            >>> msgs = [
            ...     Message.system_message("You are a helpful assistant"),
            ...     {"role": "user", "content": "Hello"},
            ...     Message.user_message("How are you?")
            ... ]
            >>> formatted = LLM.format_messages(msgs)
        """

        """
        将消息格式化为LLM可识别的OpenAl消息格式
        Args:
            messages: 消息列表，可以是字典或Message对象
        Returns:
            List[dict]: 格式化的消息列表，在OpenAI格式中
        Raises:
            ValueError: 如果消息无效或缺少必需字段
            TypeError: 如果提供了不支持的消息类型
        示例：
            >>> msgs = [
            ...     Message.system_message("You are a helpful assistant"),
            ...     {"role": "user", "content": "Hello"},
            ...     Message.user_message("How are you?")
            ... ]
            >>> formatted = LLM.format_messages(msgs)
        """
        # 初始化一个空列表，用于存储格式化后的消息
        formatted_messages = []
        
        # 遍历输入的消息列表
        for message in messages:
            # 如果消息是字典类型
            if isinstance(message, dict):
                # 如果消息已经是字典，则确保它包含必需包含"role"字段
                if "role" not in message:
                    raise ValueError("Message dict must contain 'role' field")
                # 将字典形式的消息直接添加到格式化后的消息列表
                formatted_messages.append(message)
            # 如果消息是Message对象类型
            elif isinstance(message, Message):
                # 将Message对象转换为字典并添加到格式化后的消息列表
                formatted_messages.append(message.to_dict())
            else:
                # 非对象和字典是不支持的消息类型
                raise TypeError(f"Unsupported message type: {type(message)}")

        # 验证所有格式化后的消息都包含必要的字段
        for msg in formatted_messages:
            if msg["role"] not in ["system", "user", "assistant", "tool"]:
                raise ValueError(f"Invalid role: {msg['role']}")
            if "content" not in msg and "tool_calls" not in msg:
                raise ValueError(
                    "Message must contain either 'content' or 'tool_calls'"
                )
        # 返回格式化后的消息列表
        return formatted_messages

    # 使用retry装饰器，设置重试策略
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    # 异步方法，用于向LLM发送请求并获取响应
    async def ask(
        self,
        messages: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        stream: bool = True,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Send a prompt to the LLM and get the response.

        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            stream (bool): Whether to stream the response
            temperature (float): Sampling temperature for the response

        Returns:
            str: The generated response

        Raises:
            ValueError: If messages are invalid or response is empty
            OpenAIError: If API call fails after retries
            Exception: For unexpected errors
        """

        """
        将提示发送给LLM并获取响应。
        Args:
            messages: 会话消息列表
            system_msgs: 可选的系统消息，用于前置
            stream (bool): 是否流式传输响应
            temperature (float): 响应的采样温度
        Returns:
            str: 生成的响应
        Raises:
            ValueError: 如果消息无效或响应为空
            OpenAIError: 如果API调用在重试后失败
            Exception: 对于意外错误
        """
        try:
            # # 格式化系统消息和用户消息
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                messages = system_msgs + self.format_messages(messages)
            else:
                messages = self.format_messages(messages)

            # 如果不是流式传输
            if not stream:
                # 进行非流式请求
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=temperature or self.temperature,
                    stream=False,
                )
                # 如果响应的选择列表为空或第一个选择的消息内容为空
                if not response.choices or not response.choices[0].message.content:
                    raise ValueError("Empty or invalid response from LLM")
                # 返回响应的内容
                return response.choices[0].message.content

            # 进行流式请求
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=temperature or self.temperature,
                stream=True,
            )

            # 初始化一个空列表，用于收集流式响应的内容
            collected_messages = []
            # 异步遍历流式响应
            async for chunk in response:
                # 获取每个响应块中的消息内容
                chunk_message = chunk.choices[0].delta.content or ""
                 # 将消息内容添加到收集列表
                collected_messages.append(chunk_message)
                # 打印消息内容，不换行并立即刷新输出
                print(chunk_message, end="", flush=True)

            # 打印换行符，流式传输后的换行符
            print() 
            # 将收集到的消息内容拼接成完整的响应并去除两端空白
            full_response = "".join(collected_messages).strip()
            # 如果完整响应为空
            if not full_response:
                raise ValueError("Empty response from streaming LLM")
            # 返回完整响应
            return full_response
        
        # 如果发生值错误
        except ValueError as ve:
            logger.error(f"Validation error: {ve}")
            raise
        # 如果发生OpenAI API相关错误
        except OpenAIError as oe:
            logger.error(f"OpenAI API error: {oe}")
            raise
        # 如果发生其他异常
        except Exception as e:
            logger.error(f"Unexpected error in ask: {e}")
            raise
    
    # 使用retry装饰器，设置重试策略
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    # 异步方法，用于使用工具向LLM提问并返回响应
    async def ask_tool(
        self,
        messages: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        timeout: int = 60,
        tools: Optional[List[dict]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        temperature: Optional[float] = None,
        **kwargs,
    ):
        """
        Ask LLM using functions/tools and return the response.

        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            timeout: Request timeout in seconds
            tools: List of tools to use
            tool_choice: Tool choice strategy
            temperature: Sampling temperature for the response
            **kwargs: Additional completion arguments

        Returns:
            ChatCompletionMessage: The model's response

        Raises:
            ValueError: If tools, tool_choice, or messages are invalid
            OpenAIError: If API call fails after retries
            Exception: For unexpected errors
        """

        """
        使用函数/工具询问LLM并返回响应
        Args:
            messages: 会话消息列表
            system_msgs: 可选的系统消息，用于前置
            timeout: 请求超时（秒）
            tools: 要使用的工具列表
            tool_choice: 工具选择策略
            temperature: 响应的采样温度
            **kwargs: 其他完成参数
        Returns:
            ChatCompletionMessage: 模型的响应
        Raises:
            ValueError: 如果工具、工具选择或消息无效
            OpenAIError: 如果API调用在重试后失败
            Exception: 对于意外错误
        """
        try:
            # # 验证 tool_choice 是否有效
            if tool_choice not in ["none", "auto", "required"]:
                raise ValueError(f"Invalid tool_choice: {tool_choice}")

            # 格式化消息
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                messages = system_msgs + self.format_messages(messages)
            else:
                messages = self.format_messages(messages)

            # 如果提供工具，则进行验证
            if tools:
                # 验证每个工具是否是有效的字典且包含"type"字段
                for tool in tools:
                    if not isinstance(tool, dict) or "type" not in tool:
                        raise ValueError("Each tool must be a dict with 'type' field")

            # 设置完成请求
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                timeout=timeout,
                **kwargs,
            )

            # 检查响应是否有效
            if not response.choices or not response.choices[0].message:
                print(response)
                raise ValueError("Invalid or empty response from LLM")
            
            # 返回响应的消息
            return response.choices[0].message

        # 如果发生值错误
        except ValueError as ve:
            logger.error(f"Validation error in ask_tool: {ve}")
            raise
        # 如果发生OpenAI API相关错误
        except OpenAIError as oe:
            if isinstance(oe, AuthenticationError):
                logger.error("Authentication failed. Check API key.")
            elif isinstance(oe, RateLimitError):
                logger.error("Rate limit exceeded. Consider increasing retry attempts.")
            elif isinstance(oe, APIError):
                logger.error(f"API error: {oe}")
            raise
        # 如果发生其他异常
        except Exception as e:
            logger.error(f"Unexpected error in ask_tool: {e}")
            raise

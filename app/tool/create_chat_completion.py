from typing import Any, List, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, Field

from app.tool import BaseTool

# 定义 CreateChatCompletion 的类，继承自BaseTool
class CreateChatCompletion(BaseTool):
    # 工具名称
    name: str = "create_chat_completion"
    # 工具描述，创建具有指定输出格式的结构化完成
    description: str = (
        "Creates a structured completion with specified output formatting."
    )

    # 用于JSON模式的类型映射字典，将 Python 类型映射到 JSON 类型
    type_mapping: dict = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        dict: "object",
        list: "array",
    }
    
    # 响应类型，初始为None
    response_type: Optional[Type] = None

    # 必需的字段列表，默认必须包含'response'
    required: List[str] = Field(default_factory=lambda: ["response"])

    # 类的初始化方法，使用特定响应类型初始化，接受一个可选的 response_type 参数，默认为 str 类型
    def __init__(self, response_type: Optional[Type] = str):
        """Initialize with a specific response type."""
        # 调用父类的初始化方法
        super().__init__()
         # 设置响应类型
        self.response_type = response_type
        # 构建参数
        self.parameters = self._build_parameters()

    # 构建参数模式的方法，根据响应类型构建参数模式
    def _build_parameters(self) -> dict:
        """Build parameters schema based on response type."""
        # 如果响应类型是字符串，应交付给用户的响应字符串
        if self.response_type == str:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "string",
                        "description": "The response text that should be delivered to the user.",
                    },
                },
                "required": self.required,
            }
        
        # 如果响应类型是一个类且是 BaseModel 的子类
        if isinstance(self.response_type, type) and issubclass(
            self.response_type, BaseModel
        ):
            schema = self.response_type.model_json_schema()
            return {
                "type": "object",
                "properties": schema["properties"],
                "required": schema.get("required", self.required),
            }
        
        # 如果不是上述两种情况，调用_create_type_schema方法创建类型模式
        return self._create_type_schema(self.response_type)

    # 创建给定类型的JSON模式的方法
    def _create_type_schema(self, type_hint: Type) -> dict:
        """Create a JSON schema for the given type."""
        # 获取类型提示的原始类型
        origin = get_origin(type_hint)
        # 获取类型提示的参数
        args = get_args(type_hint)


        # 如果原始类型为 None，说明是基本类型
        if origin is None:
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": self.type_mapping.get(type_hint, "string"),
                        "description": f"Response of type {type_hint.__name__}",
                    }
                },
                "required": self.required,
            }

        # 如果原始类型是list
        if origin is list:
            item_type = args[0] if args else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "array",
                        "items": self._get_type_info(item_type),
                    }
                },
                "required": self.required,
            }

        # 如果原始类型是dict
        if origin is dict:
            value_type = args[1] if len(args) > 1 else Any
            return {
                "type": "object",
                "properties": {
                    "response": {
                        "type": "object",
                        "additionalProperties": self._get_type_info(value_type),
                    }
                },
                "required": self.required,
            }

        # 如果原始类型是Union
        if origin is Union:
            return self._create_union_schema(args)
        
        # 如果都不匹配，递归调用_build_parameters方法
        return self._build_parameters()

    # 获取单个类型的类型信息。
    def _get_type_info(self, type_hint: Type) -> dict:
        """Get type information for a single type."""
        # 如果类型提示是一个类且是BaseModel的子类
        if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
            return type_hint.model_json_schema()

        return {
            "type": self.type_mapping.get(type_hint, "string"),
            "description": f"Value of type {getattr(type_hint, '__name__', 'any')}",
        }
    
    # 创建Union类型模式的方法
    def _create_union_schema(self, types: tuple) -> dict:
        """Create schema for Union types."""
        return {
            "type": "object",
            "properties": {
                "response": {"anyOf": [self._get_type_info(t) for t in types]}
            },
            "required": self.required,
        }

    # 执行聊天完成并进行类型转换的异步方法
    async def execute(self, required: list | None = None, **kwargs) -> Any:
        """Execute the chat completion with type conversion.

        Args:
            required: List of required field names or None
            **kwargs: Response data

        Returns:
            Converted response based on response_type
        """
        # Args:
        #     required: 需求字段名称列表或None
        #     **kwargs: 响应数据
        # Returns:
        #     根据response_type转换后的响应
        
        # 如果required为None，使用类的默认required字段
        required = required or self.required

        # 如果 required 是一个列表且长度大于0，处理 required 为列表的情况
        if isinstance(required, list) and len(required) > 0:
            if len(required) == 1:
                required_field = required[0]
                result = kwargs.get(required_field, "")
            else:
                # 返回多个字段组成的字典
                return {field: kwargs.get(field, "") for field in required}
        else:
            required_field = "response"
            result = kwargs.get(required_field, "")

        # 类型转换逻辑
        if self.response_type == str:
            return result
        
        # 如果响应类型是一个类且是BaseModel的子类
        if isinstance(self.response_type, type) and issubclass(
            self.response_type, BaseModel
        ):
            return self.response_type(**kwargs) # 假设结果已经是正确的格式

        # 如果响应类型的原始类型是list或dict
        if get_origin(self.response_type) in (list, dict):
            return result  # 假设 result 已处于正确格式

        try:
            return self.response_type(result)
        except (ValueError, TypeError):
            return result
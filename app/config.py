import threading
import tomllib
from pathlib import Path
from typing import Dict

from pydantic import BaseModel, Field


def get_project_root() -> Path:
    """获取项目根目录"""
    # 返回项目根目录的路径对象
    return Path(__file__).resolve().parent.parent

# 获取项目根目录
PROJECT_ROOT = get_project_root()
# 工作区根目录，位于项目根目录下的workspace文件夹
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

# LLM 设置，继承 BaseModel
class LLMSettings(BaseModel):
    # 模型名称
    model: str = Field(..., description="Model name")
    # API基础URL
    base_url: str = Field(..., description="API base URL")
    # API密钥
    api_key: str = Field(..., description="API key")
    # 每个请求的最大令牌数，默认为4096
    max_tokens: int = Field(4096, description="Maximum number of tokens per request")
    # 采样温度，默认为1.0
    temperature: float = Field(1.0, description="Sampling temperature")
    # API类型，如AzureOpenai或Openai
    api_type: str = Field(..., description="AzureOpenai or Openai")
    # 如果是AzureOpenai，对应的版本号
    api_version: str = Field(..., description="Azure Openai version if AzureOpenai")

# APP 设置，继承 BaseModel
class AppConfig(BaseModel):
    # 包含不同LLM设置的字典
    llm: Dict[str, LLMSettings]

# 配置类
class Config:
    # 单例实例
    _instance = None
    # 线程锁，用于线程安全的单例创建
    _lock = threading.Lock()
    # 标记是否已初始化
    _initialized = False

    def __new__(cls):
        # 如果单例实例尚未创建
        if cls._instance is None:
            # 使用线程锁确保线程安全
            with cls._lock:
                # 再次检查，防止多个线程同时进入上面的条件
                if cls._instance is None:
                    # 创建单例实例
                    cls._instance = super().__new__(cls)
        # 返回单例实例            
        return cls._instance

    def __init__(self):
        # 如果尚未初始化
        if not self._initialized:
            # 使用线程锁确保线程安全
            with self._lock:
                # 再次检查，防止多个线程同时进入上面的条件
                if not self._initialized:
                    # 配置对象初始化为None
                    self._config = None
                    # 加载初始配置
                    self._load_initial_config()
                    # 标记为已初始化
                    self._initialized = True

    @staticmethod
    # 获取配置文件路径
    def _get_config_path() -> Path:
        # 获取项目根目录
        root = PROJECT_ROOT
        # 配置文件路径
        config_path = root / "config" / "config.toml"
        # 如果存在
        if config_path.exists():
            return config_path
        # 示例配置文件路径
        example_path = root / "config" / "config.example.toml"
        # 如果示例配置文件存在
        if example_path.exists():
            return example_path
        raise FileNotFoundError("No configuration file found in config directory")
    
    # 载入配置文件
    def _load_config(self) -> dict:
        # 获取配置文件路径
        config_path = self._get_config_path()
        # 以二进制读取模式打开配置文件
        with config_path.open("rb") as f:
            # 使用tomllib加载配置文件内容
            return tomllib.load(f)

    # 载入初始化配置
    def _load_initial_config(self):
        # 加载配置文件内容
        raw_config = self._load_config()
        # 获取配置文件中llm部分的基础设置
        base_llm = raw_config.get("llm", {})
        # 获取配置文件中llm部分的覆盖设置（如果有）
        llm_overrides = {
            k: v for k, v in raw_config.get("llm", {}).items() if isinstance(v, dict)
        }
        # 默认配置
        default_settings = {
            "model": base_llm.get("model"),
            "base_url": base_llm.get("base_url"),
            "api_key": base_llm.get("api_key"),
            "max_tokens": base_llm.get("max_tokens", 4096),
            "temperature": base_llm.get("temperature", 1.0),
            "api_type": base_llm.get("api_type", ""),
            "api_version": base_llm.get("api_version", ""),

        }
        # 配置字典，包含默认设置和覆盖设置
        config_dict = {
            "llm": {
                "default": default_settings,
                **{
                    name: {**default_settings, **override_config}
                    for name, override_config in llm_overrides.items()
                },
            }
        }
        # 使用配置字典初始化AppConfig对象
        self._config = AppConfig(**config_dict)

    @property
    def llm(self) -> Dict[str, LLMSettings]:
        # 返回配置中的LLM设置
        return self._config.llm

# 创建配置单例对象
config = Config()

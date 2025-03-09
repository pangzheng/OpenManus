from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel

from app.agent.base import BaseAgent


class FlowType(str, Enum):
    PLANNING = "planning"

class BaseFlow(BaseModel, ABC):
    """
    定义一个名为BaseFlow的抽象类，它继承自BaseModel
    ABC作为支持多个代理的执行流程的基类
    """

    # 定义一个属性 agents，类型为 Dict[str, BaseAgent]，表示代理的字典，键为字符串，值为BaseAgent类型
    agents: Dict[str, BaseAgent]
    # 定义一个属性tools，类型为Optional[List]，表示工具列表，可为空
    tools: Optional[List] = None
    # 定义一个属性 primary_agent_key，类型为 Optional[str]，表示主代理的键，可为空
    primary_agent_key: Optional[str] = None

    class Config:
        # 允许任意类型，这在Pydantic模型中有时用于处理复杂或自定义类型
        arbitrary_types_allowed = True

    # 定义构造函数，接受 agents 和其他关键字参数
    def __init__(
        self, agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]], **data
    ):
        # 如果 agents 是BaseAgent类型，处理不同方式提供的代理
        if isinstance(agents, BaseAgent):
            # 创建一个以"default"为键，agents 为值的字典
            agents_dict = {"default": agents}
        # 如果 agents 是列表类型
        elif isinstance(agents, list):
            # 使用enumerate同时获取索引和代理实例，创建字典，键为“agent_索引”，值为代理实例
            agents_dict = {f"agent_{i}": agent for i, agent in enumerate(agents)}
        else:
            # 直接使用传入的agents字典
            agents_dict = agents

        # 获取主key参数中指定的主代理key
        primary_key = data.get("primary_agent_key")
        # 如果没有指定主代理key且代理字典不为空
        if not primary_key and agents_dict:
            # 获取代理字典的第一个key作为主代理key
            primary_key = next(iter(agents_dict))
            # 将主代理key添加到主代理key参数中
            data["primary_agent_key"] = primary_key

        # 设置代理字典
        data["agents"] = agents_dict

        # 使用BaseModel的构造函数进行初始化
        super().__init__(**data)

    # 定义属性 primary_agent，用于获取流程的主代理
    @property
    def primary_agent(self) -> Optional[BaseAgent]:
        """获取流程的主代理"""
        # 根据主代理key从代理字典中获取主代理，如果key不存在则返回None
        return self.agents.get(self.primary_agent_key)

    # 定义get_agent方法，根据key获取特定的代理
    def get_agent(self, key: str) -> Optional[BaseAgent]:
        """获取一个特定代理的key"""
        # 根据传入的key从代理字典中获取代理，如果key不存在则返回None
        return self.agents.get(key)
    
    # 定义add_agent方法，用于向流程中添加新的代理
    def add_agent(self, key: str, agent: BaseAgent) -> None:
        """添加一个新代理到流程"""
        # 将新代理添加到代理字典中，key为传入的key，值为传入的代理实例
        self.agents[key] = agent

    # 定义抽象方法 execute，该方法必须在子类中实现
    @abstractmethod
    async def execute(self, input_text: str) -> str:
        """用于使用给定的输入执行流程"""

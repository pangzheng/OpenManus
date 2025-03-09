from typing import Dict, List, Union

from app.agent.base import BaseAgent
from app.flow.base import BaseFlow, FlowType
from app.flow.planning import PlanningFlow


class FlowFactory:
    """
    用于创建不同类型流程的工厂类，支持多个代理。
    该类提供了一种创建不同类型流程对象的集中式方法，
    通过传入流程类型和代理等参数，根据流程类型从预定义的映射中获取相应的流程类并实例化
    """

    # 创建流程
    @staticmethod
    def create_flow(
        # 流程类型，是FlowType枚举中的一种
        flow_type: FlowType, 
        # 代理，可以是单个BaseAgent实例、BaseAgent实例列表或字典（键为字符串，值为BaseAgent实例）
        agents: Union[BaseAgent, List[BaseAgent], Dict[str, BaseAgent]],
        # 其他关键字参数，用于传递给流程类的构造函数
        **kwargs,
    ) -> BaseFlow:
        # 定义一个字典 flows，将流程类型映射到对应的流程类。这里只包含了PlanningFlow 的映射
        flows = {
            FlowType.PLANNING: PlanningFlow,
        }

        # 根据传入的 flow_type 从 flows 字典中获取对应的流程类
        flow_class = flows.get(flow_type)
        # 如果获取不到对应的流程类，则抛出ValueError异常，并提示未知的流程类型
        if not flow_class:
            raise ValueError(f"Unknown flow type: {flow_type}")

        # 如果获取到了对应的流程类，则使用传入的agents和kwargs实例化该流程类并返回
        return flow_class(agents, **kwargs)

# 定义 ToolError 的自定义异常类，它继承自内置的 Exception 类
class ToolError(Exception):
    """Raised when a tool encounters an error."""

    # 构造函数，用于初始化异常实例
    def __init__(self, message):
        # 将传入的错误信息保存到实例属性 message 中
        self.message = message

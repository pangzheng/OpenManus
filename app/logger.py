import sys
from datetime import datetime
from loguru import logger as _logger
from app.config import PROJECT_ROOT

_print_level = "INFO"

# 定义 define_log_level 函数 ，用于调整日志级别
def define_log_level(print_level="INFO", logfile_level="DEBUG", name: str = None):
    """将日志级别调整为高于当前级别"""
    # 使用global关键字声明在函数内部修改全局变量_print_level
    global _print_level
    # 更新全局变量_print_level为传入的print_level参数值
    _print_level = print_level

    # 获取当前的日期和时间
    current_date = datetime.now()
    formatted_date = current_date.strftime("%Y%m%d")
    # 根据是否传入name参数，生成日志文件名。如果传入name，则格式为"name_YYYYMMDD"，否则为"YYYYMMDD"
    log_name = (
        f"{name}_{formatted_date}" if name else formatted_date
    )  # name a log with prefix name

    # 移除_logger中已有的所有日志处理器
    _logger.remove()
    # 为_logger添加一个日志处理器，将日志输出到标准错误流（控制台），日志级别为print_level
    _logger.add(sys.stderr, level=print_level)
    # 为_logger添加另一个日志处理器，将日志输出到项目根目录下logs文件夹中，文件名为log_name.log，日志级别为logfile_level
    _logger.add(PROJECT_ROOT / f"logs/{log_name}.log", level=logfile_level)
    # 返回配置好的_logger对象
    return _logger

# 调用define_log_level函数，使用默认参数配置日志，并将返回的_logger对象赋值给logger
logger = define_log_level()

# 如果该脚本作为主程序直接运行（而不是被导入到其他模块中）
if __name__ == "__main__":
    logger.info("Starting application")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")

    try:
        # 故意引发一个ValueError异常，用于测试异常处理
        raise ValueError("Test error")
    except Exception as e:
        # 使用logger记录异常信息，包括异常发生的堆栈跟踪和错误描述
        logger.exception(f"An error occurred: {e}")

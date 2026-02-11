"""
项目自定义异常统一管理文件
规范：
1. 所有自定义异常继承自项目基类 BaseAppError
2. 各业务模块异常继承自对应业务基类（如 MessageStreamBaseError）
3. 每个异常包含 error_code 和 msg，便于错误分类和排查
"""

class BaseAppError(Exception):
    """项目通用异常基类（所有自定义异常的父类）"""
    def __init__(self, msg: str, error_code: int = 500):
        self.msg = msg          # 可读的错误信息
        self.error_code = error_code  # 错误码（便于前端/日志识别）
        super().__init__(f"[{error_code}] {msg}")  # 父类初始化，保留默认异常信息

class MessageStreamBaseError(BaseAppError):
    """消息流模块通用异常基类（专属业务异常的父类）"""
    def __init__(self, msg: str, error_code: int = 1000):
        super().__init__(msg, error_code)

# ------------------------------
# 消息流模块具体业务异常（细分场景）
# ------------------------------
class MessageStreamParamError(MessageStreamBaseError):
    """消息流参数错误（如传入非法的保留数量、消息ID）"""
    def __init__(self, msg: str):
        super().__init__(msg, error_code=1001)

class MessageStreamEmptyError(MessageStreamBaseError):
    """消息流为空（如清理空消息流、获取空消息）"""
    def __init__(self, msg: str = "当前消息流无任何消息"):
        super().__init__(msg, error_code=1002)

class MessageStreamDuplicateIdError(MessageStreamBaseError):
    """消息ID重复（重复添加相同ID的消息）"""
    def __init__(self, msg_id: int):
        super().__init__(f"消息ID {msg_id} 已存在，无法重复添加", error_code=1003)

class MessageStreamDeleteError(MessageStreamBaseError):
    """消息删除失败（如清理消息时出现未知错误）"""
    def __init__(self, msg: str):
        super().__init__(msg, error_code=1004)
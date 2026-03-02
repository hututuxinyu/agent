"""日志服务模块"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class LoggerService:
    """日志服务，用于记录会话信息和关键操作"""
    
    _instance: Optional['LoggerService'] = None
    _initialized = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志服务"""
        if LoggerService._initialized:
            return
        
        # 创建logs目录
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 配置日志文件路径（使用日期作为文件名）
        log_date = datetime.now().strftime("%Y%m%d")
        log_file = log_dir / f"agent_{log_date}.log"
        
        # 配置logger
        self.logger = logging.getLogger("agent_logger")
        self.logger.setLevel(logging.INFO)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 创建文件处理器
            file_handler = logging.FileHandler(
                log_file,
                encoding='utf-8',
                mode='a'
            )
            file_handler.setLevel(logging.INFO)
            
            # 创建格式化器
            # 格式: 时间戳 | session_id | 级别 | 类型 | 内容
            formatter = logging.Formatter(
                '%(asctime)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # 添加处理器
            self.logger.addHandler(file_handler)
        
        LoggerService._initialized = True
    
    def log_session_message(
        self,
        session_id: str,
        message_type: str,
        content: str,
        level: str = "INFO"
    ):
        """
        记录会话消息
        
        Args:
            session_id: 会话ID
            message_type: 消息类型（USER_MSG, AI_REPLY, TOOL_CALL等）
            content: 消息内容
            level: 日志级别（INFO, WARNING, ERROR）
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        log_message = f"{session_id} | {level} | {message_type} | {content}"
        
        # 如果内容过长，进行截断（保留前2000个字符）
        if len(log_message) > 3000:
            log_message = log_message[:3000] + "... [内容已截断]"
        
        self.logger.log(log_level, log_message)
    
    def log_operation(
        self,
        session_id: str,
        operation: str,
        details: Optional[str] = None,
        level: str = "INFO"
    ):
        """
        记录关键操作
        
        Args:
            session_id: 会话ID
            operation: 操作名称（SESSION_CREATED, SESSION_DESTROYED, TOOL_EXECUTED等）
            details: 操作详情（可选）
            level: 日志级别（INFO, WARNING, ERROR）
        """
        log_level = getattr(logging, level.upper(), logging.INFO)
        log_message = f"{session_id} | {level} | {operation}"
        if details:
            log_message += f" | {details}"
        
        self.logger.log(log_level, log_message)
    
    def log_error(
        self,
        session_id: str,
        error_type: str,
        error_message: str,
        exception: Optional[Exception] = None
    ):
        """
        记录错误信息
        
        Args:
            session_id: 会话ID
            error_type: 错误类型
            error_message: 错误消息
            exception: 异常对象（可选）
        """
        log_message = f"{session_id} | ERROR | {error_type} | {error_message}"
        
        if exception:
            import traceback
            traceback_str = traceback.format_exc()
            log_message += f"\n{traceback_str}"
        
        self.logger.error(log_message)
    
    def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        tool_args: dict,
        success: bool,
        result: Optional[str] = None
    ):
        """
        记录工具调用
        
        Args:
            session_id: 会话ID
            tool_name: 工具名称
            tool_args: 工具参数
            success: 是否成功
            result: 工具返回结果（可选）
        """
        import json
        args_str = json.dumps(tool_args, ensure_ascii=False)
        status = "SUCCESS" if success else "FAILED"
        
        log_message = f"{session_id} | INFO | TOOL_CALL | {tool_name} | {status} | 参数: {args_str}"
        if result:
            # 如果结果过长，截断
            if len(result) > 1000:
                result = result[:1000] + "... [结果已截断]"
            log_message += f" | 结果: {result}"
        
        self.logger.info(log_message)

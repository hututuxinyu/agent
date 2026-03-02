"""请求模型"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求模型"""
    model_ip: str = Field(..., description="模型资源接口IP")
    session_id: str = Field(..., description="会话ID")
    message: str = Field(..., description="用户消息")

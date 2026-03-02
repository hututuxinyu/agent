"""响应模型"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """工具调用结果"""
    name: str = Field(..., description="工具名称")
    success: bool = Field(..., description="是否成功")
    output: str = Field(..., description="工具输出")


class ChatResponse(BaseModel):
    """聊天响应模型"""
    session_id: str = Field(..., description="会话ID")
    response: str = Field(..., description="Agent回复")
    status: str = Field(..., description="处理状态")
    tool_results: List[ToolResult] = Field(default_factory=list, description="工具调用结果")
    timestamp: int = Field(..., description="时间戳")
    duration_ms: int = Field(..., description="处理耗时(毫秒)")

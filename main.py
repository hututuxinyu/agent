"""FastAPI应用入口"""
import time
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from models.request import ChatRequest
from models.response import ChatResponse
from services.session_manager import SessionManager
from services.agent_service import AgentService
from config import AGENT_PORT

app = FastAPI(title="租房AI Agent", version="1.0.0")

# 全局Session管理器
session_manager = SessionManager()


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口
    
    Args:
        request: 聊天请求
    
    Returns:
        聊天响应
    """
    try:
        # 创建Agent服务
        agent_service = AgentService(
            model_ip=request.model_ip,
            session_manager=session_manager
        )
        
        # 处理消息
        result = await agent_service.process_message(
            session_id=request.session_id,
            message=request.message
        )
        
        # 构建响应
        response = ChatResponse(
            session_id=request.session_id,
            response=result["response"],
            status=result["status"],
            tool_results=result["tool_results"],
            timestamp=int(time.time()),
            duration_ms=result["duration_ms"]
        )
        
        return response
        
    except Exception as e:
        # 错误处理
        error_response = ChatResponse(
            session_id=request.session_id if hasattr(request, 'session_id') else "",
            response=f"处理请求时发生错误: {str(e)}",
            status="error",
            tool_results=[],
            timestamp=int(time.time()),
            duration_ms=0
        )
        return JSONResponse(
            status_code=500,
            content=error_response.model_dump()
        )


@app.get("/health")
async def health():
    """健康检查接口"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)

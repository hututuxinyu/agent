"""LLM客户端"""
import httpx
from typing import List, Dict, Any, Optional
from config import MODEL_PORT, LLM_TIMEOUT


class LLMClient:
    """LLM客户端，封装模型调用逻辑"""
    
    def __init__(self, model_ip: str):
        """
        初始化客户端
        
        Args:
            model_ip: 模型资源接口IP
        """
        self.model_ip = model_ip
        self.base_url = f"http://{model_ip}:{MODEL_PORT}"
        self.timeout = httpx.Timeout(LLM_TIMEOUT)
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用聊天完成接口
        
        Args:
            messages: 消息列表
            tools: 工具定义列表
            tool_choice: 工具选择策略
        
        Returns:
            模型响应
        """
        try:
            # 构建请求体
            payload = {
                "model": "",  # 模型可以为空
                "messages": messages,
                "stream": False
            }
            
            if tools:
                payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice
            
            # 使用httpx异步调用
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v2/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()
                return result
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP错误 {e.response.status_code}: {e.response.text}"
            raise Exception(f"LLM调用失败: {error_msg}")
        except httpx.TimeoutException:
            raise Exception(f"LLM调用超时（超过{LLM_TIMEOUT}秒）")
        except Exception as e:
            raise Exception(f"LLM调用失败: {str(e)}")

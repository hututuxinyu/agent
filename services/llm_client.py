"""LLM客户端"""
import requests
import json
import asyncio
from typing import List, Dict, Any, Optional
from config import MODEL_PORT


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
    
    def _chat_completion_sync(
        self,
        messages: List[Dict[str, str]],
        session_id: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        同步调用聊天完成接口（内部方法）
        
        Args:
            messages: 消息列表
            session_id: 评测会话ID
            tools: 工具定义列表
            tool_choice: 工具选择策略
        
        Returns:
            模型响应
        """
        # 在函数开始就定义这些变量，确保异常处理中可以访问
        request_url = f"{self.base_url}/v1/chat/completions"
        
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
        
        # 请求头（参考API接口说明.md，需要包含Session-ID）
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Python-requests/2.31.0",
            "Connection": "close",  # 避免长连接问题
            "Session-ID": session_id  # 评测会话ID（由评测接口生成）
        }
        
        # 打印请求信息（参考test_llm_api.py）
        print("=" * 80)
        print("【LLM请求详情】")
        print(f"URL: {request_url}")
        print(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
        print(f"Payload长度: {len(json.dumps(payload))} 字符")
        print("=" * 80)
        
        try:
            # 发送POST请求（参考test_llm_api.py，设置60秒超时）
            response = requests.post(
                url=request_url,
                headers=headers,
                json=payload,  # 自动序列化并处理特殊字符
                timeout=60.0   # 设置合理超时
            )
            
            # 打印响应信息
            print("=" * 80)
            print("【LLM响应详情】")
            print(f"状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}")
            print(f"响应内容（前1000字符）: {response.text[:1000]}...")
            if len(response.text) > 1000:
                print(f"... (总长度: {len(response.text)} 字符)")
            print("=" * 80)
            
            # 检查状态码
            response.raise_for_status()
            
            # 解析响应结果
            result = response.json()
            print("【调用成功】最终响应结果:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            # 检查是否有错误字段（某些API会在200状态码下返回错误）
            if isinstance(result, dict) and "error" in result:
                error_info = result.get("error", {})
                if isinstance(error_info, dict):
                    error_msg = error_info.get("message", str(error_info))
                else:
                    error_msg = str(error_info)
                raise Exception(f"LLM调用失败: {error_msg}")
            
            return result
            
        except requests.exceptions.HTTPError as e:
            # HTTP状态码错误
            if hasattr(e, 'response') and e.response is not None:
                error_msg = f"HTTP错误 - 状态码: {e.response.status_code}, 内容: {e.response.text}"
            else:
                error_msg = f"HTTP错误: {str(e)}"
            print(f"\n❌ 调用失败: {error_msg}")
            raise Exception(f"LLM调用失败: {error_msg}")
        
        except requests.exceptions.Timeout:
            error_msg = "请求超时（60秒），请检查接口是否正常或网络是否通畅"
            print(f"\n❌ 调用失败: {error_msg}")
            raise Exception(f"LLM调用失败: {error_msg}")
        
        except requests.exceptions.ConnectionError:
            error_msg = "连接失败，请检查IP/端口是否可达，或防火墙是否放行"
            print(f"\n❌ 调用失败: {error_msg}")
            raise Exception(f"LLM调用失败: {error_msg}")
        
        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            print(f"\n❌ 调用失败: {error_msg}")
            print("=" * 80)
            print("【LLM请求异常 - 其他异常】")
            print(f"请求URL: {request_url}")
            print(f"请求Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
            print(f"请求Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            print(f"异常类型: {type(e).__name__}")
            print(f"异常信息: {str(e)}")
            import traceback
            print(f"堆栈跟踪:\n{traceback.format_exc()}")
            print("=" * 80)
            raise Exception(f"LLM调用失败: {error_msg}")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        session_id: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        调用聊天完成接口（异步包装）
        
        Args:
            messages: 消息列表
            session_id: 评测会话ID
            tools: 工具定义列表
            tool_choice: 工具选择策略
        
        Returns:
            模型响应
        """
        # 在线程池中运行同步方法，保持异步接口兼容性
        return await asyncio.to_thread(
            self._chat_completion_sync,
            messages,
            session_id,
            tools,
            tool_choice
        )

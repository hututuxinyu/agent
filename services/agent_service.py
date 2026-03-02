"""Agent核心逻辑"""
import json
import time
import httpx
from typing import Dict, Any, List, Optional
from services.llm_client import LLMClient
from services.session_manager import SessionManager
from services.house_api_client import HouseAPIClient
from tools.house_tools import TOOLS_DEFINITION, TOOL_FUNCTIONS


class AgentService:
    """Agent核心服务，处理消息、调用LLM、执行工具、生成回复"""
    
    def __init__(self, model_ip: str, session_manager: SessionManager):
        """
        初始化Agent服务
        
        Args:
            model_ip: 模型IP
            session_manager: Session管理器
        """
        self.llm_client = LLMClient(model_ip)
        self.session_manager = session_manager
        self.max_iterations = 10  # 最大工具调用轮数
    
    async def process_message(
        self,
        session_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            session_id: 会话ID
            message: 用户消息
        
        Returns:
            处理结果，包含response、tool_results等
        """
        start_time = time.time()
        tool_results = []
        
        try:
            # 获取或创建Session
            client = self.session_manager.get_or_create_session(session_id)
            
            # 如果是新Session，初始化（调用房源重置）
            if session_id not in self.session_manager.sessions:
                await self.session_manager.init_session(session_id)
            
            # 添加用户消息到历史
            self.session_manager.add_message(session_id, "user", message)
            
            # 获取对话历史
            messages = self.session_manager.get_messages(session_id)
            
            # 多轮工具调用循环
            iteration = 0
            final_response = None
            
            while iteration < self.max_iterations:
                iteration += 1
                
                # 调用LLM
                llm_response = await self.llm_client.chat_completion(
                    messages=messages,
                    session_id=session_id,
                    tools=TOOLS_DEFINITION
                )
                
                # 提取助手消息
                choice = llm_response["choices"][0]
                assistant_message = choice["message"]
                
                # 添加助手消息到历史
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.get("content"),
                    "tool_calls": assistant_message.get("tool_calls", [])
                })
                
                # 检查是否有工具调用
                tool_calls = assistant_message.get("tool_calls", [])
                
                if not tool_calls:
                    # 没有工具调用，生成最终回复
                    final_response = assistant_message.get("content", "")
                    break
                
                # 执行工具调用
                tool_messages = []
                for tool_call in tool_calls:
                    tool_name = tool_call["function"]["name"]
                    tool_args_str = tool_call["function"]["arguments"]
                    tool_call_id = tool_call["id"]
                    
                    try:
                        # 解析工具参数
                        tool_args = json.loads(tool_args_str)
                        
                        # 获取工具函数
                        tool_func = TOOL_FUNCTIONS.get(tool_name)
                        if not tool_func:
                            raise ValueError(f"未知的工具: {tool_name}")
                        
                        # 执行工具
                        tool_result = await tool_func(client, **tool_args)
                        
                        # 格式化工具结果
                        if tool_result.get("success"):
                            # 直接使用data，保持原始结构
                            data = tool_result.get("data", {})
                            tool_output = json.dumps(data, ensure_ascii=False)
                        else:
                            tool_output = json.dumps({"error": tool_result.get("error", "未知错误")}, ensure_ascii=False)
                        
                        # 添加工具消息
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_output
                        })
                        
                        # 记录工具结果
                        tool_results.append({
                            "name": tool_name,
                            "success": tool_result.get("success", False),
                            "output": tool_output
                        })
                        
                    except Exception as e:
                        # 工具执行失败
                        error_output = json.dumps({"error": str(e)}, ensure_ascii=False)
                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": error_output
                        })
                        tool_results.append({
                            "name": tool_name,
                            "success": False,
                            "output": error_output
                        })
                
                # 添加工具消息到历史
                messages.extend(tool_messages)
            
            # 如果达到最大迭代次数，使用最后一次的回复
            if final_response is None:
                # 再次调用LLM生成最终回复
                llm_response = await self.llm_client.chat_completion(
                    messages=messages,
                    session_id=session_id,
                    tools=None  # 不再需要工具
                )
                choice = llm_response["choices"][0]
                final_response = choice["message"].get("content", "")
            
            # 格式化响应（如果是房源查询，需要JSON格式）
            formatted_response = self._format_response(final_response, tool_results)
            
            # 添加最终回复到历史
            self.session_manager.add_message(session_id, "assistant", formatted_response)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return {
                "response": formatted_response,
                "status": "success",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
            
        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "response": "请求超时，请稍后重试",
                "status": "error",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "response": f"HTTP错误 {e.response.status_code}: {str(e)}",
                "status": "error",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            import traceback
            error_msg = str(e)
            # 记录详细错误信息（用于调试）
            print(f"处理消息时发生错误: {error_msg}")
            print(traceback.format_exc())
            return {
                "response": f"处理消息时发生错误: {error_msg}",
                "status": "error",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
    
    def _format_response(self, response: str, tool_results: List[Dict[str, Any]]) -> str:
        """
        格式化响应
        
        关键逻辑：如果执行了房源查询工具，response必须是JSON字符串格式
        
        Args:
            response: LLM生成的原始回复
            tool_results: 工具调用结果列表
        
        Returns:
            格式化后的响应
        """
        # 检查是否有房源查询相关的工具调用
        search_tools = ["search_houses", "get_nearby_houses"]
        has_search = any(
            result.get("name") in search_tools and result.get("success", False)
            for result in tool_results
        )
        
        if has_search:
            # 从工具结果中提取房源ID列表
            house_ids = []
            for result in tool_results:
                if result.get("name") in search_tools and result.get("success"):
                    try:
                        output_data = json.loads(result["output"])
                        
                        # 尝试从不同可能的响应结构中提取房源ID
                        # 可能的格式：
                        # 1. {"data": {"items": [...]}}
                        # 2. {"items": [...]}
                        # 3. {"data": [...]}
                        # 4. 直接是列表 [...]
                        
                        items = []
                        if isinstance(output_data, dict):
                            if "data" in output_data:
                                data = output_data["data"]
                                if isinstance(data, dict) and "items" in data:
                                    items = data["items"]
                                elif isinstance(data, list):
                                    items = data
                            elif "items" in output_data:
                                items = output_data["items"]
                        elif isinstance(output_data, list):
                            items = output_data
                        
                        # 从items中提取house_id
                        for item in items:
                            if isinstance(item, dict):
                                house_id = (
                                    item.get("house_id") or 
                                    item.get("id") or 
                                    item.get("houseId")
                                )
                                if house_id:
                                    house_ids.append(str(house_id))
                    except Exception as e:
                        # 解析失败，记录但不中断
                        print(f"警告: 解析工具结果失败: {e}")
                        pass
            
            # 如果提取到了房源ID，格式化为JSON字符串
            if house_ids:
                # 去重并保持顺序
                house_ids = list(dict.fromkeys(house_ids))
                
                # 生成消息（从原始回复中提取，或使用默认消息）
                message = response.strip() if response else ""
                if not message or len(message) < 5:
                    message = "为您找到以下符合条件的房源："
                
                # 格式化为JSON字符串
                return json.dumps({
                    "message": message,
                    "houses": house_ids
                }, ensure_ascii=False)
        
        # 非房源查询，返回原始回复
        return response

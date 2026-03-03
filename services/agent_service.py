"""Agent核心逻辑"""
import json
import time
import httpx
from typing import Dict, Any, List, Optional
from services.llm_client import LLMClient
from services.session_manager import SessionManager
from services.house_api_client import HouseAPIClient
from services.logger_service import LoggerService
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
        self.logger = LoggerService()
        self.max_iterations = 5  # 最大工具调用轮数（大多数用例只需要1-2轮）
        self.system_prompt = self._get_system_prompt()
        # 存储最近查询的房源信息，用于租房操作
        self.recent_house_results: Dict[str, List[Dict[str, Any]]] = {}
        # 存储每个session的查询状态，用于多轮对话上下文理解
        self.session_query_states: Dict[str, Dict[str, Any]] = {}
    
    def _get_system_prompt(self) -> str:
        """
        获取System Prompt，明确Agent角色、任务和关键规则
        
        Returns:
            System prompt字符串
        """
        return """你是租房助手Agent，帮助用户查找和租赁房源。

## 核心规则
1. 近地铁：距离≤800米
2. 输出格式：{"message": "描述", "houses": ["HF_xxx", ...]}，最多5套
3. 房源ID：必须以"HF_"开头
4. 无房源时：{"message": "没有", "houses": []}

## 工具使用
- 优先使用search_houses查询
- 查询前确保条件明确（区域、价格等）
- 支持排序（价格、面积、地铁距离）

## 租房操作
当用户表达租房意图（"就租"、"我要租"、"可以租吗"等）时：
1. 提取房源ID和平台信息
2. 调用rent_house工具
3. 确认结果

## 租房回复规则（重要）
**禁止**：未调用rent_house工具就回复"已成功租下房源"等成功信息。
**必须**：只有调用rent_house成功后才能回复成功信息。"""
    
    def _compress_search_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        压缩查询结果，只保留关键字段以减少token消耗
        
        Args:
            data: 原始查询结果数据
        
        Returns:
            压缩后的数据
        """
        if not isinstance(data, dict):
            return data
        
        compressed = {}
        
        # 保留分页信息
        if "total" in data:
            compressed["total"] = data["total"]
        if "page" in data:
            compressed["page"] = data["page"]
        if "page_size" in data:
            compressed["page_size"] = data["page_size"]
        
        # 压缩items，只保留关键字段
        items = []
        if "items" in data:
            items = data["items"]
        elif "data" in data and isinstance(data["data"], dict) and "items" in data["data"]:
            items = data["data"]["items"]
        
        compressed_items = []
        for item in items[:10]:  # 最多保留10条
            if isinstance(item, dict):
                # 进一步压缩，只保留最核心字段：house_id, price, subway_distance
                compressed_item = {
                    "house_id": item.get("house_id") or item.get("id") or item.get("houseId"),
                    "price": item.get("price"),
                    "subway_distance": item.get("subway_distance")
                }
                # 移除None值
                compressed_item = {k: v for k, v in compressed_item.items() if v is not None}
                compressed_items.append(compressed_item)
        
        compressed["items"] = compressed_items
        
        # 保留提示信息
        if "_hint" in data:
            compressed["_hint"] = data["_hint"]
        
        return compressed
    
    def _detect_rent_intent(self, message: str) -> bool:
        """
        检测用户消息中是否包含租房意图
        
        Args:
            message: 用户消息
        
        Returns:
            是否包含租房意图
        """
        # 排除查询相关词汇，避免误判
        query_keywords = ["找", "查询", "搜索", "筛选", "看看", "看看有", "看看能", "看看要"]
        message_lower = message.lower()
        
        # 如果用户消息是查询类（包含查询关键词），不触发租房意图
        if any(keyword in message for keyword in query_keywords):
            return False
        
        # 排除"租金"等价格相关词汇（这些是查询条件，不是租房动作）
        # 排除包含"租金"、"租房"等查询相关词汇的情况
        if "租金" in message and not any(action in message for action in ["租这个", "租那套", "租最近", "租第一", "就租", "要租", "我要租"]):
            return False
        
        # 只检测明确的租房动作词汇
        rent_action_keywords = [
            "就租", "要租", "租这个", "租那套", "租最近", "租第一",
            "租了", "租下", "确定租", "决定租", "选择租",
            "可以租吗", "能租吗", "想租", "我要租", "帮我租",
            "租下来", "租它", "租一套", "租一间"
        ]
        
        # 检查是否包含明确的租房动作
        return any(keyword in message for keyword in rent_action_keywords)
    
    def _resolve_reference(self, message: str, session_id: str) -> str:
        """
        指代消解：解析用户消息中的指代（如"最近的那套"、"其他的"等）
        
        Args:
            message: 用户消息
            session_id: 会话ID
        
        Returns:
            消解后的消息
        """
        # 获取最近的查询状态
        query_state = self.session_query_states.get(session_id, {})
        recent_houses = query_state.get("recent_houses", [])
        
        # 处理"最近的那套"、"第一套"等指代
        if "最近" in message or "第一" in message or "第一个" in message:
            if recent_houses:
                house_id = recent_houses[0].get("house_id") if isinstance(recent_houses[0], dict) else recent_houses[0]
                message = message.replace("最近的那套", f"房源{house_id}").replace("第一套", f"房源{house_id}").replace("第一个", f"房源{house_id}")
        
        # 处理"其他的"、"还有其他的吗"等指代
        if "其他" in message or "还有" in message:
            # 标记需要查询更多房源
            query_state["need_more"] = True
            self.session_query_states[session_id] = query_state
        
        return message
    
    def _update_query_state(self, session_id: str, tool_results: List[Dict[str, Any]]):
        """
        更新查询状态，用于多轮对话上下文理解
        
        Args:
            session_id: 会话ID
            tool_results: 工具调用结果列表
        """
        if session_id not in self.session_query_states:
            self.session_query_states[session_id] = {
                "recent_houses": [],
                "query_conditions": {},
                "need_more": False
            }
        
        query_state = self.session_query_states[session_id]
        
        # 更新最近查询的房源
        search_tools = ["search_houses", "get_nearby_houses"]
        for result in tool_results:
            if result.get("name") in search_tools and result.get("success"):
                house_ids = self._extract_house_ids_from_tool_result(result)
                # 更新最近房源列表（保留最多10个）
                query_state["recent_houses"] = house_ids[:10]
                break
    
    def _extract_rent_info_from_context(
        self, 
        session_id: str, 
        tool_results: List[Dict[str, Any]],
        messages: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        从对话上下文和工具结果中提取租房所需信息（房源ID和平台）
        
        Args:
            session_id: 会话ID
            tool_results: 工具调用结果列表
            messages: 对话历史
        
        Returns:
            包含house_id和listing_platform的字典，如果无法提取则返回None
        """
        import re
        house_id = None
        listing_platform = None
        
        # 1. 优先从get_house_detail工具结果中提取房源ID和平台信息
        for result in reversed(tool_results):  # 从最新开始查找
            if result.get("name") == "get_house_detail" and result.get("success"):
                try:
                    output_data = json.loads(result.get("output", "{}"))
                    # 从详情结果中提取房源ID
                    if isinstance(output_data, dict):
                        house_id = (
                            output_data.get("house_id") or 
                            output_data.get("id") or 
                            output_data.get("houseId")
                        )
                        # 从详情结果中提取平台信息
                        listing_platform = output_data.get("listing_platform")
                        if house_id:
                            house_id = str(house_id)
                            # 验证房源ID格式
                            if house_id.startswith("HF_"):
                                break
                except:
                    pass
        
        # 2. 从用户消息中直接提取房源ID（如"HF_277"）
        if not house_id:
            # 从最新的用户消息中查找
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    # 尝试匹配HF_开头的ID
                    hf_match = re.search(r'HF_\d+', content)
                    if hf_match:
                        house_id = hf_match.group(0)
                        break
        
        # 3. 从最近的查询结果中提取房源ID（search_houses或get_nearby_houses）
        if not house_id:
            search_tools = ["search_houses", "get_nearby_houses"]
            for result in reversed(tool_results):  # 从最新开始查找
                if result.get("name") in search_tools and result.get("success"):
                    house_ids = self._extract_house_ids_from_tool_result(result)
                    if house_ids:
                        # 取第一套房源（通常是用户最可能想租的）
                        house_id = house_ids[0]
                        # 尝试从工具结果中提取平台信息
                        try:
                            output_data = json.loads(result.get("output", "{}"))
                            # 从items中查找平台信息
                            if isinstance(output_data, dict):
                                items = output_data.get("items", [])
                                if items and isinstance(items, list) and len(items) > 0:
                                    first_item = items[0]
                                    if isinstance(first_item, dict):
                                        listing_platform = first_item.get("listing_platform")
                        except:
                            pass
                        break
        
        # 4. 从对话历史中提取房源ID和平台信息
        if not house_id:
            # 从最近的助手消息中查找房源ID
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    # 尝试解析JSON格式的回复
                    try:
                        if content.strip().startswith("{"):
                            parsed = json.loads(content)
                            if "houses" in parsed and isinstance(parsed["houses"], list):
                                if parsed["houses"]:
                                    house_id = parsed["houses"][0]
                    except:
                        pass
                    # 尝试直接匹配HF_开头的ID
                    if not house_id:
                        hf_match = re.search(r'HF_\d+', content)
                        if hf_match:
                            house_id = hf_match.group(0)
                    if house_id:
                        break
        
        # 5. 从查询状态中获取最近房源
        query_state = self.session_query_states.get(session_id, {})
        if not house_id and query_state.get("recent_houses"):
            house_id = query_state["recent_houses"][0] if isinstance(query_state["recent_houses"][0], str) else query_state["recent_houses"][0].get("house_id")
        
        # 6. 从对话历史中提取平台信息（如果还没有找到）
        if not listing_platform:
            platform_keywords = ["链家", "安居客", "58同城"]
            for msg in reversed(messages):
                content = msg.get("content", "")
                for platform in platform_keywords:
                    if platform in content:
                        listing_platform = platform
                        break
                if listing_platform:
                    break
        
        # 如果没有找到平台，默认使用安居客
        if house_id and not listing_platform:
            listing_platform = "安居客"
        
        if house_id and listing_platform:
            return {
                "house_id": house_id,
                "listing_platform": listing_platform
            }
        
        return None
    
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
            # 检查是否为新Session（在创建之前检查）
            is_new_session = session_id not in self.session_manager.sessions
            
            # 获取或创建Session
            client = self.session_manager.get_or_create_session(session_id)
            
            # 如果是新Session，初始化（调用房源重置）
            if is_new_session:
                await self.session_manager.init_session(session_id)
            
            # 指代消解：处理用户消息中的指代
            resolved_message = self._resolve_reference(message, session_id)
            
            # 记录用户消息
            self.logger.log_session_message(session_id, "USER_MSG", resolved_message)
            
            # 添加用户消息到历史
            self.session_manager.add_message(session_id, "user", resolved_message)
            
            # 获取对话历史（限制长度以节省token）
            # 保留system message和最近10条消息（约5轮对话）
            messages = self.session_manager.get_messages(session_id, max_messages=10)
            
            # 如果是首次对话或新session，添加system prompt
            if not messages or all(msg.get("role") != "system" for msg in messages):
                messages.insert(0, {
                    "role": "system",
                    "content": self.system_prompt
                })
            
            # 如果消息仍然过多，进一步压缩
            if len(messages) > 15:
                messages = self.session_manager.compress_messages(session_id, keep_recent=5)
                # 确保system prompt存在
                if not any(msg.get("role") == "system" for msg in messages):
                    messages.insert(0, {
                        "role": "system",
                        "content": self.system_prompt
                    })
            
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
                        
                        # 需求验证：对于查询工具，验证关键参数
                        if tool_name in ["search_houses", "get_nearby_houses"]:
                            # 验证page_size，如果未设置或过大，设置为合理值
                            if "page_size" not in tool_args or tool_args.get("page_size", 0) > 10:
                                tool_args["page_size"] = 10
                        
                        # 获取工具函数
                        tool_func = TOOL_FUNCTIONS.get(tool_name)
                        if not tool_func:
                            raise ValueError(f"未知的工具: {tool_name}")
                        
                        # 执行工具
                        tool_result = await tool_func(client, **tool_args)
                        
                        # 智能重试：如果查询无结果，尝试放宽条件
                        if tool_name == "search_houses" and not tool_result.get("success", True):
                            # 查询失败，记录错误但不重试（避免无限循环）
                            pass
                        elif tool_name == "search_houses" and tool_result.get("success"):
                            # 检查是否有房源
                            house_ids = self._extract_house_ids_from_tool_result({
                                "success": True,
                                "output": json.dumps(tool_result.get("data", {}), ensure_ascii=False)
                            })
                            # 提前终止：如果查询到足够房源（≥5套），立即返回结果
                            if len(house_ids) >= 5:
                                # 标记可以提前终止
                                final_response = "查询完成"
                                break
                            # 如果没有房源且是第一次查询，可以考虑放宽条件（这里先记录，由LLM决定是否重试）
                            if not house_ids and iteration == 1:
                                # 在工具结果中添加提示信息
                                data = tool_result.get("data", {})
                                if isinstance(data, dict):
                                    data["_hint"] = "查询无结果，建议放宽条件（如扩大价格范围、增加区域）重新查询"
                                    tool_result["data"] = data
                        
                        # 格式化工具结果（压缩以减少token消耗）
                        if tool_result.get("success"):
                            # 对于查询工具，只保留关键字段以减少token
                            data = tool_result.get("data", {})
                            if tool_name in ["search_houses", "get_nearby_houses"]:
                                # 压缩工具结果，只保留关键信息
                                compressed_data = self._compress_search_result(data)
                                tool_output = json.dumps(compressed_data, ensure_ascii=False)
                            else:
                                # 其他工具保持原始结构
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
                        
                        # 记录工具调用日志
                        self.logger.log_tool_call(
                            session_id,
                            tool_name,
                            tool_args,
                            tool_result.get("success", False),
                            tool_output if len(tool_output) < 1000 else tool_output[:1000] + "..."
                        )
                        
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
                        
                        # 记录工具调用错误日志
                        self.logger.log_tool_call(
                            session_id,
                            tool_name,
                            tool_args,
                            False,
                            error_output
                        )
                        self.logger.log_error(session_id, "TOOL_EXECUTION_ERROR", str(e), e)
                
                # 添加工具消息到历史
                messages.extend(tool_messages)
                
                # 更新查询状态（用于多轮对话上下文理解）
                self._update_query_state(session_id, tool_results)
                
                # 智能终止检查：如果查询到足够房源（≥5套）或查询成功且有结果，提前终止
                search_tools = ["search_houses", "get_nearby_houses"]
                should_terminate = False
                for result in tool_results:
                    if result.get("name") in search_tools and result.get("success"):
                        house_ids = self._extract_house_ids_from_tool_result(result)
                        # 如果查询到足够房源（≥5套），提前终止
                        if len(house_ids) >= 5:
                            should_terminate = True
                            break
                        # 如果查询成功且有房源（即使少于5套），也可以提前终止（避免不必要的后续调用）
                        elif len(house_ids) > 0 and iteration >= 1:
                            should_terminate = True
                            break
                
                if should_terminate:
                    # 提前终止，生成最终回复
                    final_response = "查询完成"
                    break
            
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
            
            # 检查当前轮次是否有search_houses工具调用且成功
            # 如果有查询操作，优先返回查询结果，不触发自动租房
            has_search_houses = any(
                result.get("name") == "search_houses" and result.get("success")
                for result in tool_results
            )
            
            # 只有在没有查询操作或查询失败时，才检查租房意图
            # 如果当前轮次有search_houses工具调用，优先返回查询结果
            if has_search_houses:
                # 有查询操作，不触发自动租房，直接返回查询结果
                pass
            elif self._detect_rent_intent(message):
                rent_info = self._extract_rent_info_from_context(session_id, tool_results, messages)
                if rent_info:
                    try:
                        # 调用rent_house工具
                        rent_result = await TOOL_FUNCTIONS["rent_house"](
                            client,
                            house_id=rent_info["house_id"],
                            listing_platform=rent_info["listing_platform"]
                        )
                        # 记录租房操作结果
                        tool_results.append({
                            "name": "rent_house",
                            "success": rent_result.get("success", False),
                            "output": json.dumps(rent_result.get("data", {}), ensure_ascii=False) if rent_result.get("success") else json.dumps({"error": rent_result.get("error", "未知错误")}, ensure_ascii=False)
                        })
                        # 如果租房成功，更新最终回复
                        if rent_result.get("success"):
                            final_response = f"已成功租下房源 {rent_info['house_id']}（平台：{rent_info['listing_platform']}）"
                        else:
                            final_response = f"租房操作失败：{rent_result.get('error', '未知错误')}"
                    except Exception as e:
                        print(f"警告: 自动调用租房工具失败: {e}")
                        self.logger.log_error(session_id, "AUTO_RENT_ERROR", f"自动调用租房工具失败: {str(e)}", e)
                        # 继续使用原始回复
            
            # 检查回复是否包含租房成功信息但没有rent_house调用，强制触发自动租房逻辑
            # 但如果当前轮次有查询操作，不触发自动租房
            rent_success_keywords = ["已成功租下房源", "租下", "成功租", "已租", "租好了", "租到了"]
            has_rent_success_keyword = any(keyword in final_response for keyword in rent_success_keywords)
            has_rent_house_call = any(
                result.get("name") == "rent_house" 
                for result in tool_results
            )
            
            if has_rent_success_keyword and not has_rent_house_call and not has_search_houses:
                # 检测到租房意图，尝试自动租房（只有在没有查询操作时）
                if self._detect_rent_intent(message):
                    rent_info = self._extract_rent_info_from_context(session_id, tool_results, messages)
                    if rent_info:
                        try:
                            # 调用rent_house工具
                            rent_result = await TOOL_FUNCTIONS["rent_house"](
                                client,
                                house_id=rent_info["house_id"],
                                listing_platform=rent_info["listing_platform"]
                            )
                            # 记录租房操作结果
                            tool_results.append({
                                "name": "rent_house",
                                "success": rent_result.get("success", False),
                                "output": json.dumps(rent_result.get("data", {}), ensure_ascii=False) if rent_result.get("success") else json.dumps({"error": rent_result.get("error", "未知错误")}, ensure_ascii=False)
                            })
                            # 如果租房成功，更新最终回复
                            if rent_result.get("success"):
                                final_response = f"已成功租下房源 {rent_info['house_id']}（平台：{rent_info['listing_platform']}）"
                            else:
                                final_response = f"租房操作失败：{rent_result.get('error', '未知错误')}"
                        except Exception as e:
                            print(f"警告: 强制触发自动租房失败: {e}")
                            self.logger.log_error(session_id, "FORCE_RENT_ERROR", f"强制触发自动租房失败: {str(e)}", e)
                            # 如果自动租房失败，拒绝原始回复
                            final_response = "无法完成租房操作：无法提取房源信息或租房工具调用失败。请先选择房源并确保房源信息完整。"
                    else:
                        # 无法提取房源信息，拒绝原始回复
                        final_response = "无法完成租房操作：无法提取房源信息。请先选择房源并确保房源信息完整。"
                else:
                    # 没有检测到租房意图，但回复包含租房成功信息，拒绝回复
                    final_response = "需要先调用rent_house工具才能完成租房操作。请先选择房源并调用租房工具。"
            
            # 格式化响应（如果是房源查询，需要JSON格式）
            formatted_response = self._format_response(final_response, tool_results, session_id)
            
            # 添加最终回复到历史
            self.session_manager.add_message(session_id, "assistant", formatted_response)
            
            # 记录AI回复
            self.logger.log_session_message(session_id, "AI_REPLY", formatted_response)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return {
                "response": formatted_response,
                "status": "success",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
            
        except httpx.TimeoutException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.log_error(session_id, "TIMEOUT_ERROR", "请求超时", e)
            return {
                "response": "请求超时，请稍后重试",
                "status": "error",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
        except httpx.HTTPStatusError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.logger.log_error(session_id, "HTTP_ERROR", f"HTTP错误 {e.response.status_code}: {str(e)}", e)
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
            self.logger.log_error(session_id, "PROCESS_MESSAGE_ERROR", error_msg, e)
            return {
                "response": f"处理消息时发生错误: {error_msg}",
                "status": "error",
                "tool_results": tool_results,
                "duration_ms": duration_ms
            }
    
    def _extract_house_ids_from_tool_result(self, tool_result: Dict[str, Any]) -> List[str]:
        """
        从工具结果中提取房源ID列表，支持多种API响应格式
        
        Args:
            tool_result: 工具调用结果
        
        Returns:
            房源ID列表
        """
        house_ids = []
        if not tool_result.get("success"):
            return house_ids
        
        try:
            output_data = json.loads(tool_result["output"])
            
            # 尝试从不同可能的响应结构中提取房源ID
            # 可能的格式：
            # 1. {"data": {"items": [...]}}
            # 2. {"data": {"data": {"items": [...]}}}  # 嵌套结构
            # 3. {"items": [...]}
            # 4. {"data": [...]}
            # 5. 直接是列表 [...]
            
            items = []
            if isinstance(output_data, dict):
                # 递归查找items
                def find_items(obj):
                    if isinstance(obj, list):
                        return obj
                    if isinstance(obj, dict):
                        if "items" in obj:
                            return obj["items"] if isinstance(obj["items"], list) else []
                        if "data" in obj:
                            return find_items(obj["data"])
                    return []
                
                items = find_items(output_data)
            elif isinstance(output_data, list):
                items = output_data
            
            # 从items中提取house_id
            for item in items:
                if isinstance(item, dict):
                    # 尝试多种可能的字段名
                    house_id = (
                        item.get("house_id") or 
                        item.get("id") or 
                        item.get("houseId") or
                        item.get("houseID")
                    )
                    if house_id:
                        house_id_str = str(house_id)
                        # 验证房源ID格式（必须以HF_开头）
                        if house_id_str.startswith("HF_"):
                            house_ids.append(house_id_str)
        except Exception as e:
            # 解析失败，记录但不中断
            print(f"警告: 解析工具结果失败: {e}")
        
        return house_ids
    
    def _extract_house_ids_from_llm_response(self, response: str) -> List[str]:
        """
        从LLM回复中提取房源ID（当工具结果解析失败时使用）
        
        Args:
            response: LLM生成的回复
        
        Returns:
            房源ID列表
        """
        house_ids = []
        import re
        
        # 尝试从JSON格式中提取
        try:
            # 查找JSON对象
            json_match = re.search(r'\{[^{}]*"houses"[^{}]*\[[^\]]*\][^{}]*\}', response)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                if "houses" in data and isinstance(data["houses"], list):
                    house_ids.extend([str(hid) for hid in data["houses"] if str(hid).startswith("HF_")])
        except:
            pass
        
        # 尝试直接匹配HF_开头的ID
        hf_pattern = r'HF_\d+'
        matches = re.findall(hf_pattern, response)
        house_ids.extend(matches)
        
        return list(dict.fromkeys(house_ids))  # 去重
    
    def _sort_houses(
        self, 
        house_ids: List[str], 
        tool_results: List[Dict[str, Any]],
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> List[str]:
        """
        对房源ID列表进行智能排序
        
        Args:
            house_ids: 房源ID列表
            tool_results: 工具调用结果列表
            sort_by: 用户指定的排序字段（price/area/subway）
            sort_order: 用户指定的排序顺序（asc/desc）
        
        Returns:
            排序后的房源ID列表
        """
        if not house_ids or len(house_ids) <= 1:
            return house_ids
        
        # 从工具结果中提取房源详细信息
        house_info_map = {}
        search_tools = ["search_houses", "get_nearby_houses"]
        
        for result in tool_results:
            if result.get("name") in search_tools and result.get("success"):
                try:
                    output_data = json.loads(result["output"])
                    items = []
                    
                    # 提取items
                    if isinstance(output_data, dict):
                        if "items" in output_data:
                            items = output_data["items"]
                        elif "data" in output_data:
                            data = output_data["data"]
                            if isinstance(data, dict) and "items" in data:
                                items = data["items"]
                            elif isinstance(data, list):
                                items = data
                    elif isinstance(output_data, list):
                        items = output_data
                    
                    # 构建房源信息映射
                    for item in items:
                        if isinstance(item, dict):
                            house_id = (
                                item.get("house_id") or 
                                item.get("id") or 
                                item.get("houseId")
                            )
                            if house_id and str(house_id) in house_ids:
                                # 从压缩后的数据中提取信息（只包含house_id, price, subway_distance）
                                # 注意：压缩后的数据可能不包含area，所以使用0作为默认值
                                house_info_map[str(house_id)] = {
                                    "price": item.get("price", 0),
                                    "area": item.get("area_sqm", 0) or item.get("area", 0),  # 使用 area_sqm（面积）或 area
                                    "subway_distance": item.get("subway_distance", float('inf'))
                                }
                except Exception as e:
                    print(f"警告: 提取房源信息用于排序失败: {e}")
                    pass
        
        # 如果没有房源信息，返回原始顺序
        if not house_info_map:
            return house_ids
        
        # 根据排序字段和顺序排序
        def get_sort_key(house_id: str):
            info = house_info_map.get(house_id, {})
            if sort_by == "price":
                return info.get("price", 0)
            elif sort_by == "area":
                return info.get("area", 0)
            elif sort_by == "subway":
                return info.get("subway_distance", float('inf'))
            else:
                # 默认按匹配度排序：优先价格合理、面积合适、地铁距离近的
                price = info.get("price", 0)
                area = info.get("area", 0)
                subway = info.get("subway_distance", float('inf'))
                # 匹配度评分：价格越低越好，面积适中，地铁距离越近越好
                # 这里使用简单的评分机制
                return (subway, price, -area)  # 地铁距离优先，然后价格，最后面积（大的优先）
        
        # 排序
        reverse = (sort_order == "desc") if sort_order else False
        if sort_by:
            # 根据用户指定的排序字段和顺序排序
            sorted_ids = sorted(house_ids, key=get_sort_key, reverse=reverse)
        else:
            # 默认按匹配度排序（地铁距离近、价格低优先）
            sorted_ids = sorted(house_ids, key=get_sort_key, reverse=False)
        
        # 确保排序后的列表包含所有房源ID（处理信息缺失的情况）
        # 将没有信息的房源ID追加到末尾
        missing_ids = [hid for hid in house_ids if hid not in sorted_ids]
        if missing_ids:
            sorted_ids.extend(missing_ids)
        
        return sorted_ids
    
    def _extract_sort_preference(self, message: str, messages: List[Dict[str, Any]]) -> tuple[Optional[str], Optional[str]]:
        """
        从用户消息和对话历史中提取排序偏好
        
        Args:
            message: 当前用户消息
            messages: 对话历史
        
        Returns:
            (sort_by, sort_order) 元组
        """
        sort_by = None
        sort_order = None
        
        # 检查当前消息
        text = message.lower()
        
        # 优先检测明确的排序表达（如"按...排"、"按...排序"）
        if "按" in text and ("排" in text or "排序" in text):
            if "价格" in text or "租金" in text:
                sort_by = "price"
                if "从低到高" in text or "升序" in text or "便宜" in text or "低" in text:
                    sort_order = "asc"
                elif "从高到低" in text or "降序" in text or "贵" in text or "高" in text:
                    sort_order = "desc"
            elif "面积" in text:
                sort_by = "area"
                if "从大到小" in text or "降序" in text or "大" in text:
                    sort_order = "desc"
                elif "从小到大" in text or "升序" in text or "小" in text:
                    sort_order = "asc"
            elif "地铁" in text or "距离" in text or "离地铁" in text:
                sort_by = "subway"
                if "从近到远" in text or "升序" in text or "近" in text:
                    sort_order = "asc"
                elif "从远到近" in text or "降序" in text or "远" in text:
                    sort_order = "desc"
                else:
                    # 如果没有明确指定顺序，默认从近到远
                    sort_order = "asc"
        
        # 如果没有检测到明确的排序表达，检查一般关键词
        if not sort_by:
            if "价格" in text or "租金" in text:
                sort_by = "price"
                if "从低到高" in text or "升序" in text or "便宜" in text:
                    sort_order = "asc"
                elif "从高到低" in text or "降序" in text or "贵" in text:
                    sort_order = "desc"
            elif "面积" in text:
                sort_by = "area"
                if "从大到小" in text or "降序" in text:
                    sort_order = "desc"
                elif "从小到大" in text or "升序" in text:
                    sort_order = "asc"
            elif "地铁" in text or "距离" in text or "离地铁" in text:
                sort_by = "subway"
                # 默认从近到远（升序）
                if "从近到远" in text or "升序" in text or "近" in text:
                    sort_order = "asc"
                elif "从远到近" in text or "降序" in text or "远" in text:
                    sort_order = "desc"
                else:
                    # 如果没有明确指定顺序，默认从近到远
                    sort_order = "asc"
        
        # 检查对话历史
        if not sort_by:
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "").lower()
                    if "按" in content and ("排" in content or "排序" in content):
                        if "价格" in content or "租金" in content:
                            sort_by = "price"
                            if "从低到高" in content or "升序" in content:
                                sort_order = "asc"
                            elif "从高到低" in content or "降序" in content:
                                sort_order = "desc"
                            break
                        elif "面积" in content:
                            sort_by = "area"
                            if "从大到小" in content or "降序" in content:
                                sort_order = "desc"
                            elif "从小到大" in content or "升序" in content:
                                sort_order = "asc"
                            break
                        elif "地铁" in content or "距离" in content or "离地铁" in content:
                            sort_by = "subway"
                            if "从近到远" in content or "升序" in content:
                                sort_order = "asc"
                            elif "从远到近" in content or "降序" in content:
                                sort_order = "desc"
                            else:
                                sort_order = "asc"
                            break
                    elif "价格" in content or "租金" in content:
                        sort_by = "price"
                        break
                    elif "面积" in content:
                        sort_by = "area"
                        break
                    elif "地铁" in content or "距离" in content:
                        sort_by = "subway"
                        sort_order = "asc"  # 默认从近到远
                        break
        
        return (sort_by, sort_order)
    
    def _generate_search_message(
        self,
        user_message: str,
        tool_results: List[Dict[str, Any]],
        house_ids: List[str]
    ) -> str:
        """
        根据查询条件和结果生成符合用例要求的message
        
        Args:
            user_message: 用户消息
            tool_results: 工具调用结果列表
            house_ids: 房源ID列表
        
        Returns:
            生成的message字符串
        """
        if not house_ids:
            return "没有"
        
        # 从工具结果中提取查询条件
        query_conditions = []
        search_tools = ["search_houses", "get_nearby_houses"]
        
        for result in tool_results:
            if result.get("name") in search_tools and result.get("success"):
                try:
                    output_data = json.loads(result.get("output", "{}"))
                    if isinstance(output_data, dict):
                        items = output_data.get("items", [])
                        if items and len(items) > 0:
                            # 从第一个房源中提取关键信息
                            first_item = items[0]
                            if isinstance(first_item, dict):
                                district = first_item.get("district")
                                bedrooms = first_item.get("bedrooms")
                                subway_distance = first_item.get("subway_distance")
                                price = first_item.get("price")
                                
                                if district:
                                    query_conditions.append(district)
                                if bedrooms:
                                    query_conditions.append(f"{bedrooms}居")
                                if subway_distance is not None:
                                    if subway_distance <= 800:
                                        query_conditions.append("近地铁")
                                    else:
                                        query_conditions.append(f"地铁{int(subway_distance)}米")
                                if price:
                                    query_conditions.append(f"{price}元")
                except:
                    pass
                break
        
        # 如果从工具结果中无法提取，从用户消息中提取关键信息
        if not query_conditions:
            # 提取区域信息
            districts = ["海淀", "朝阳", "丰台", "大兴", "昌平", "通州", "房山", "顺义", "石景山", "门头沟"]
            for district in districts:
                if district in user_message:
                    query_conditions.append(district)
                    break
            
            # 提取户型信息
            if "一居" in user_message or "1居" in user_message:
                query_conditions.append("1居")
            elif "两居" in user_message or "2居" in user_message:
                query_conditions.append("2居")
            elif "三居" in user_message or "3居" in user_message:
                query_conditions.append("3居")
            
            # 提取价格信息
            import re
            price_match = re.search(r'(\d+)元', user_message)
            if price_match:
                query_conditions.append(f"{price_match.group(1)}元")
        
        # 生成message
        if query_conditions:
            message = "为您找到" + "".join(query_conditions) + "的房源"
        else:
            message = "为您找到以下符合条件的房源"
        
        return message
    
    def _format_response(self, response: str, tool_results: List[Dict[str, Any]], session_id: str) -> str:
        """
        格式化响应
        
        关键逻辑：如果执行了房源查询工具，response必须是JSON字符串格式
        
        Args:
            response: LLM生成的原始回复
            tool_results: 工具调用结果列表
            session_id: 会话ID，用于获取对话历史
        
        Returns:
            格式化后的响应
        """
        # 验证租房回复：如果回复包含租房成功信息但没有rent_house工具调用，拒绝回复并提示错误
        rent_success_keywords = ["已成功租下房源", "租下", "成功租", "已租", "租好了", "租到了"]
        has_rent_success_keyword = any(keyword in response for keyword in rent_success_keywords)
        has_rent_house_call = any(
            result.get("name") == "rent_house" 
            for result in tool_results
        )
        
        if has_rent_success_keyword and not has_rent_house_call:
            # 拒绝回复，提示错误
            return "需要先调用rent_house工具才能完成租房操作。请先选择房源并调用租房工具。"
        
        # 检查是否有房源查询相关的工具调用
        search_tools = ["search_houses", "get_nearby_houses"]
        has_search = any(
            result.get("name") in search_tools
            for result in tool_results
        )
        
        if has_search:
            # 优先从search_houses工具结果中提取房源ID
            house_ids = []
            search_success = False
            search_result = None
            
            # 优先查找search_houses的结果
            for result in tool_results:
                if result.get("name") == "search_houses" and result.get("success"):
                    search_success = True
                    search_result = result
                    extracted_ids = self._extract_house_ids_from_tool_result(result)
                    house_ids.extend(extracted_ids)
                    break
            
            # 如果没有search_houses，尝试get_nearby_houses
            if not house_ids:
                for result in tool_results:
                    if result.get("name") == "get_nearby_houses" and result.get("success"):
                        search_success = True
                        search_result = result
                        extracted_ids = self._extract_house_ids_from_tool_result(result)
                        house_ids.extend(extracted_ids)
                        break
            
            # 如果从工具结果中未提取到ID，尝试从LLM回复中提取
            if not house_ids:
                house_ids = self._extract_house_ids_from_llm_response(response)
            
            # 去重并保持顺序
            house_ids = list(dict.fromkeys(house_ids))
            
            # 智能排序：从对话历史中提取排序偏好
            messages = self.session_manager.get_messages(session_id)
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            sort_by, sort_order = self._extract_sort_preference(user_message, messages)
            if house_ids:
                house_ids = self._sort_houses(house_ids, tool_results, sort_by, sort_order)
            
            # 限制最多5套
            house_ids = house_ids[:5]
            
            # 生成消息（优先使用生成的message，包含关键信息）
            message = ""
            
            # 尝试从LLM回复中提取message（如果是JSON格式）
            try:
                json_match = response.strip()
                if json_match.startswith("{") and json_match.endswith("}"):
                    parsed = json.loads(json_match)
                    if "message" in parsed:
                        message = parsed["message"]
            except:
                pass
            
            # 检查消息中是否包含"没有"、"无"等关键词，表示没有房源
            no_result_keywords = ["没有", "无", "找不到", "未找到", "暂无"]
            if any(keyword in message for keyword in no_result_keywords):
                house_ids = []
                message = "没有"
            elif not house_ids and search_success:
                # 查询成功但没有房源
                message = "没有"
            elif not message or len(message) < 3:
                # 使用生成的message，包含关键信息
                if house_ids:
                    message = self._generate_search_message(user_message, tool_results, house_ids)
                else:
                    message = "没有"
            
            # 确保始终返回JSON格式
            return json.dumps({
                "message": message,
                "houses": house_ids
            }, ensure_ascii=False)
        
        # 检查是否已经是JSON格式（可能是租房操作等）
        try:
            if response.strip().startswith("{") and response.strip().endswith("}"):
                parsed = json.loads(response.strip())
                # 如果已经是正确的JSON格式，直接返回
                if "message" in parsed and "houses" in parsed:
                    return response.strip()
        except:
            pass
        
        # 非房源查询，返回原始回复
        return response

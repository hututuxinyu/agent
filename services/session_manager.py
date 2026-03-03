"""Session管理器"""
from typing import Dict, List, Optional
from utils.helpers import extract_user_id_from_session_id
from services.house_api_client import HouseAPIClient
from services.logger_service import LoggerService


class SessionManager:
    """Session管理器，管理对话历史和Session状态"""
    
    def __init__(self):
        """初始化Session管理器"""
        # 存储每个session的对话历史
        # 格式: {session_id: [{"role": "user", "content": "..."}, ...]}
        self.sessions: Dict[str, List[Dict[str, str]]] = {}
        # 存储每个session的user_id
        self.session_user_ids: Dict[str, str] = {}
        # 存储每个session的API客户端
        self.session_clients: Dict[str, HouseAPIClient] = {}
        # 日志服务
        self.logger = LoggerService()
    
    def get_or_create_session(self, session_id: str) -> HouseAPIClient:
        """
        获取或创建Session，如果是新Session则调用房源重置接口
        
        Args:
            session_id: 会话ID
        
        Returns:
            HouseAPIClient实例
        """
        # 提取user_id
        user_id = "h00613474"
        
        # 如果是新Session，初始化
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            self.session_user_ids[session_id] = user_id
            # 创建API客户端
            client = HouseAPIClient(user_id)
            self.session_clients[session_id] = client
            # 记录Session创建
            self.logger.log_operation(session_id, "SESSION_CREATED", f"user_id: {user_id}")
            # 新Session时自动调用房源重置接口
            # 注意：这里不await，因为这是同步方法，重置会在异步上下文中调用
            return client
        
        return self.session_clients[session_id]
    
    def get_messages(self, session_id: str, max_messages: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取Session的对话历史，支持压缩以节省token
        
        Args:
            session_id: 会话ID
            max_messages: 最大消息数，如果超过则压缩历史
        
        Returns:
            消息列表
        """
        messages = self.sessions.get(session_id, [])
        
        # 如果设置了最大消息数且超过限制，进行压缩
        if max_messages and len(messages) > max_messages:
            # 保留system message和最近的对话
            compressed = []
            # 保留system message
            for msg in messages:
                if msg.get("role") == "system":
                    compressed.append(msg)
                    break
            
            # 保留最近的N条消息
            recent_messages = messages[-max_messages:]
            compressed.extend(recent_messages)
            return compressed
        
        return messages
    
    def compress_messages(self, session_id: str, keep_recent: int = 10) -> List[Dict[str, str]]:
        """
        压缩对话历史，只保留关键信息
        
        Args:
            session_id: 会话ID
            keep_recent: 保留最近N轮对话
        
        Returns:
            压缩后的消息列表
        """
        if session_id not in self.sessions:
            return []
        
        messages = self.sessions[session_id]
        compressed = []
        
        # 保留system message
        for msg in messages:
            if msg.get("role") == "system":
                compressed.append(msg)
                break
        
        # 分离最近的消息和更早的消息
        recent_count = keep_recent * 2  # 每轮包含user和assistant
        recent_messages = messages[-recent_count:] if len(messages) > recent_count else messages
        older_messages = messages[:-recent_count] if len(messages) > recent_count else []
        
        # 压缩更早的消息，只保留关键信息
        for msg in older_messages:
            role = msg.get("role")
            content = msg.get("content", "")
            
            if role == "tool":
                # 工具消息：只保留工具名称和关键结果（房源ID列表）
                try:
                    import json
                    data = json.loads(content)
                    # 尝试提取房源ID
                    house_ids = []
                    if isinstance(data, dict):
                        items = data.get("items", [])
                        if items:
                            for item in items:
                                if isinstance(item, dict):
                                    house_id = item.get("house_id") or item.get("id") or item.get("houseId")
                                    if house_id:
                                        house_ids.append(str(house_id))
                    
                    if house_ids:
                        compressed.append({
                            "role": "tool",
                            "tool_call_id": msg.get("tool_call_id", ""),
                            "content": json.dumps({"house_ids": house_ids[:5]}, ensure_ascii=False)
                        })
                    else:
                        # 如果没有房源ID，只保留成功/失败状态
                        success = data.get("total", 0) > 0 if isinstance(data, dict) else False
                        compressed.append({
                            "role": "tool",
                            "tool_call_id": msg.get("tool_call_id", ""),
                            "content": json.dumps({"success": success}, ensure_ascii=False)
                        })
                except:
                    # 解析失败，保留原始内容但截断
                    compressed.append({
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", ""),
                        "content": content[:200] if len(content) > 200 else content
                    })
            elif role == "assistant":
                # Assistant消息：如果包含JSON格式的房源查询结果，压缩为摘要
                try:
                    import json
                    if content.strip().startswith("{") and content.strip().endswith("}"):
                        parsed = json.loads(content)
                        if "houses" in parsed:
                            house_ids = parsed.get("houses", [])
                            if house_ids:
                                # 压缩为摘要
                                compressed.append({
                                    "role": "assistant",
                                    "content": json.dumps({
                                        "message": parsed.get("message", "")[:50],
                                        "houses": house_ids[:5]
                                    }, ensure_ascii=False)
                                })
                            else:
                                compressed.append(msg)
                        else:
                            compressed.append(msg)
                    else:
                        # 非JSON格式，保留但截断
                        compressed.append({
                            "role": "assistant",
                            "content": content[:300] if len(content) > 300 else content
                        })
                except:
                    # 解析失败，保留但截断
                    compressed.append({
                        "role": "assistant",
                        "content": content[:300] if len(content) > 300 else content
                    })
            elif role == "user":
                # 用户消息：保留完整内容
                compressed.append(msg)
        
        # 保留最近的对话（完整保留）
        compressed.extend(recent_messages)
        
        return compressed
    
    def add_message(self, session_id: str, role: str, content: str):
        """
        添加消息到对话历史
        
        Args:
            session_id: 会话ID
            role: 角色（user/assistant/tool）
            content: 消息内容
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        
        self.sessions[session_id].append({
            "role": role,
            "content": content
        })
    
    def add_tool_message(self, session_id: str, tool_call_id: str, content: str):
        """
        添加工具消息到对话历史
        
        Args:
            session_id: 会话ID
            tool_call_id: 工具调用ID
            content: 工具返回内容
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        
        self.sessions[session_id].append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content
        })
    
    def get_user_id(self, session_id: str) -> str:
        """
        获取Session对应的user_id
        
        Args:
            session_id: 会话ID
        
        Returns:
            user_id
        """
        return self.session_user_ids.get(session_id, extract_user_id_from_session_id(session_id))
    
    async def init_session(self, session_id: str):
        """
        初始化Session（调用房源重置接口）
        
        Args:
            session_id: 会话ID
        """
        client = self.get_or_create_session(session_id)
        try:
            await client.init_houses()
            self.logger.log_operation(session_id, "SESSION_INITIALIZED", "房源重置成功")
        except Exception as e:
            # 如果重置失败，记录错误但不阻止继续
            print(f"警告: Session {session_id} 房源重置失败: {e}")
            self.logger.log_error(session_id, "SESSION_INIT_ERROR", f"房源重置失败: {str(e)}", e)
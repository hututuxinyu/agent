"""辅助函数"""
import re
from typing import Optional


def extract_user_id_from_session_id(session_id: str) -> str:
    """
    从session_id中提取user_id
    
    例如: "EV-43" -> "EV-43"
    如果session_id本身就是user_id，直接返回
    """
    # 如果session_id格式为 "EV-43" 这样的格式，直接返回
    # 否则尝试提取
    if re.match(r'^[A-Z]+-\d+$', session_id):
        return session_id
    
    # 尝试从其他格式中提取
    match = re.search(r'([A-Z]+-\d+)', session_id)
    if match:
        return match.group(1)
    
    # 如果无法提取，返回原值
    return session_id

"""配置管理模块"""
import os
from typing import Optional

# 房源API基础URL
HOUSE_API_BASE_URL = os.getenv("HOUSE_API_BASE_URL", "http://7.225.29.223:8080")

# Agent监听端口
AGENT_PORT = int(os.getenv("AGENT_PORT", "8192"))

# 模型端口（固定）
MODEL_PORT = 8888

# 超时设置（秒）
REQUEST_TIMEOUT = 5.0
LLM_TIMEOUT = 30.0

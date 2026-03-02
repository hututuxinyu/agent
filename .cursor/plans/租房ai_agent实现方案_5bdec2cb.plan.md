---
name: 租房AI Agent实现方案
overview: 使用Python + FastAPI构建租房AI Agent，实现需求理解、房源查询、多轮对话和租房操作等核心功能，通过工具调用机制连接LLM和房源API。
todos:
  - id: init_project
    content: 创建项目结构，初始化requirements.txt和基础配置文件
    status: completed
  - id: api_server
    content: 实现FastAPI应用和POST /api/v1/chat接口框架
    status: completed
    dependencies:
      - init_project
  - id: session_manager
    content: 实现Session管理器，支持对话历史存储和新session时调用房源重置
    status: completed
    dependencies:
      - init_project
  - id: api_clients
    content: 实现LLM客户端和房源API客户端，封装所有API调用
    status: completed
    dependencies:
      - init_project
  - id: tools_system
    content: 定义所有房源相关工具函数（查询、租房、退租等）
    status: completed
    dependencies:
      - api_clients
  - id: agent_core
    content: 实现Agent核心逻辑：处理消息、调用LLM、执行工具、生成回复
    status: completed
    dependencies:
      - session_manager
      - api_clients
      - tools_system
  - id: response_format
    content: 实现房源查询结果的JSON格式化逻辑
    status: completed
    dependencies:
      - agent_core
  - id: error_handling
    content: 完善错误处理和超时控制
    status: completed
    dependencies:
      - agent_core
  - id: testing
    content: 使用提供的3个用例进行集成测试和调试
    status: completed
    dependencies:
      - response_format
      - error_handling
---

# 租房AI Agent实现方案

## 技术栈选择

**后端框架**: Python + FastAPI

- Python在AI/LLM领域生态最丰富
- FastAPI轻量、高性能、支持异步
- 自动生成API文档，便于调试

**LLM调用**: OpenAI SDK (openai库)

- 接口兼容OpenAI格式，可直接使用
- 支持function calling/tools机制
- 简单易用，文档完善

**HTTP客户端**: httpx

- 异步HTTP客户端，性能好
- 用于调用房源API和模型API

**Session管理**: 内存字典

- 简单场景足够，存储对话历史
- 支持多轮对话上下文管理

## 项目结构

```
.
├── main.py                 # FastAPI应用入口
├── config.py               # 配置管理
├── models/                 # 数据模型
│   ├── __init__.py
│   ├── request.py          # 请求模型
│   └── response.py         # 响应模型
├── services/               # 业务服务层
│   ├── __init__.py
│   ├── session_manager.py  # Session管理
│   ├── llm_client.py       # LLM客户端
│   ├── house_api_client.py # 房源API客户端
│   └── agent_service.py   # Agent核心逻辑
├── tools/                  # 工具定义
│   ├── __init__.py
│   └── house_tools.py      # 房源相关工具
├── utils/                  # 工具函数
│   ├── __init__.py
│   └── helpers.py          # 辅助函数
├── requirements.txt        # 依赖列表
└── README.md              # 项目说明
```

## 核心实现要点

### 1. API接口实现 (`main.py`)

- 实现 `POST /api/v1/chat` 接口
- 接收 `model_ip`, `session_id`, `message` 参数
- 返回标准响应格式（包含response、status、tool_results等）

### 2. Session管理 (`services/session_manager.py`)

- 使用内存字典存储每个session的对话历史
- 新session时自动调用房源重置接口
- 从session_id提取user_id（用于X-User-ID请求头）
- 管理对话上下文，支持多轮对话

### 3. LLM客户端 (`services/llm_client.py`)

- 封装模型调用逻辑（model_ip:8888/v2/chat/completions）
- 支持tools/function calling
- 处理模型响应，提取工具调用

### 4. 房源API客户端 (`services/house_api_client.py`)

- 封装所有房源API调用（15个接口）
- 自动添加X-User-ID请求头
- 处理API错误和异常

### 5. 工具系统 (`tools/house_tools.py`)

定义以下工具函数：

- `search_houses`: 房源查询（支持多条件筛选）
- `get_house_detail`: 获取房源详情
- `search_landmarks`: 搜索地标
- `get_nearby_houses`: 地标附近房源
- `rent_house`: 租房操作
- `terminate_rent`: 退租操作
- `offline_house`: 下架操作
- `get_house_stats`: 房源统计

### 6. Agent核心逻辑 (`services/agent_service.py`)

- 处理用户消息
- 调用LLM（带工具定义）
- 执行工具调用
- 处理工具结果，决定是否需要继续调用
- 生成最终回复
- **关键**: 房源查询完成后，response必须是JSON字符串格式：`{"message": "...", "houses": [...]}`

## 关键实现细节

### Session ID解析

从session_id中提取user_id（例如"EV-43"可能需要解析，或从请求中获取）

### 房源查询结果格式化

当Agent完成房源查询后，必须将response格式化为JSON字符串：

```python
response = json.dumps({
    "message": "为您找到以下符合条件的房源：",
    "houses": ["HF_4", "HF_6", "HF_277"]
})
```

### 工具调用流程

1. 用户消息 → Agent
2. Agent调用LLM（带工具定义）
3. LLM返回工具调用请求
4. 执行工具调用（调用房源API）
5. 将工具结果返回LLM
6. LLM生成最终回复
7. 判断是否需要继续调用（多轮工具调用）

### 错误处理

- 模型调用失败
- 房源API调用失败
- 工具执行失败
- 超时处理（5秒限制）

## 配置管理

- **房源API基础URL**: `http://7.225.29.223:8080`（已确认）
- **Agent监听端口**: 8191
- **模型端口**: 8888（固定）
- **X-User-ID**: 从session_id中解析（已确认从session_id解析）

## 已确认的API参数详情

### 核心查询接口 `/api/houses/by_platform` 支持的筛选条件：

- **基础筛选**: district（行政区）、area（商圈）、listing_platform（平台）
- **价格**: min_price、max_price（元/月）
- **户型**: bedrooms（卧室数，逗号分隔）、rental_type（整租/合租）
- **房屋属性**: decoration（装修）、orientation（朝向）、elevator（电梯）
- **面积**: min_area、max_area（平米）
- **地铁**: subway_line（线路）、subway_station（站名）、max_subway_dist（距离，米）
- **其他**: utilities_type（水电类型）、available_from_before（可入住日期）、commute_to_xierqi_max（西二旗通勤时间，分钟）
- **排序**: sort_by（price/area/subway）、sort_order（asc/desc）
- **分页**: page、page_size（默认10，最大10000）

所有接口的详细参数已在OpenAPI规范中完整定义，可直接用于工具函数实现。

## 依赖列表

```
fastapi>=0.104.0
uvicorn>=0.24.0
openai>=1.0.0
httpx>=0.25.0
pydantic>=2.0.0
python-dotenv>=1.0.0
```

## 实现步骤

1. **项目初始化**: 创建项目结构，安装依赖
2. **基础框架**: 实现FastAPI应用和基础路由
3. **Session管理**: 实现Session管理器
4. **API客户端**: 实现房源API和LLM客户端
5. **工具系统**: 定义所有工具函数
6. **Agent核心**: 实现Agent主逻辑
7. **集成测试**: 使用提供的3个用例进行测试
8. **优化调试**: 优化prompt、错误处理、性能
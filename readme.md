# 租房AI Agent

基于Python + FastAPI构建的租房AI Agent，实现需求理解、房源查询、多轮对话和租房操作等核心功能。

## 技术栈

- **后端框架**: Python + FastAPI
- **LLM调用**: OpenAI兼容API（通过httpx异步调用）
- **HTTP客户端**: httpx（异步）
- **Session管理**: 内存字典

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

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行服务

```bash
python main.py
```

服务将在 `http://0.0.0.0:8191` 启动。

## API接口

### POST /api/v1/chat

聊天接口，接收用户消息并返回Agent回复。

**请求参数**:
```json
{
  "model_ip": "xxx.xxx.xx.x",
  "session_id": "EV-43",
  "message": "查询海淀区的房源"
}
```

**响应格式**:
```json
{
  "session_id": "EV-43",
  "response": "为您找到以下符合条件的房源：",
  "status": "success",
  "tool_results": [...],
  "timestamp": 1704067200,
  "duration_ms": 1500
}
```

### GET /health

健康检查接口。

## 核心功能

1. **Session管理**: 自动管理对话历史，新Session时自动重置房源数据
2. **工具调用**: 支持房源查询、租房、退租、下架等操作
3. **多轮对话**: 支持多轮工具调用，自动处理上下文
4. **响应格式化**: 房源查询结果自动格式化为JSON字符串

## 配置说明

- **房源API基础URL**: `http://7.225.29.223:8080`
- **Agent监听端口**: 8191
- **模型端口**: 8888（固定）
- **请求超时**: 5秒
- **LLM超时**: 30秒

## 注意事项

1. 房源查询完成后，response字段必须是JSON字符串格式：`{"message": "...", "houses": [...]}`
2. 所有房源相关API调用必须带 `X-User-ID` 请求头
3. 新Session时会自动调用房源重置接口
4. 支持多轮工具调用，最多10轮

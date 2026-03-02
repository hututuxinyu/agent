---
name: Agent优化方案
overview: 基于赛题要求、打榜用例和评分规则，从需求理解、工具调用、结果输出、性能优化四个维度全面优化Agent，提升用例通过率和得分
todos:
  - id: add-system-prompt
    content: 在agent_service.py中添加system prompt，明确Agent角色、任务和关键规则
    status: completed
  - id: optimize-house-id-extraction
    content: 优化_format_response方法中的房源ID提取逻辑，支持多种API响应格式和LLM回复解析
    status: completed
  - id: add-rent-operation-recognition
    content: 添加租房操作识别逻辑，识别用户租房意图并自动调用rent_house工具
    status: completed
  - id: optimize-output-format
    content: 确保查询结果始终返回正确的JSON格式，包含message和houses字段
    status: completed
    dependencies:
      - optimize-house-id-extraction
  - id: optimize-tool-calling
    content: 优化工具描述和调用策略，添加需求验证和智能重试机制
    status: completed
    dependencies:
      - add-system-prompt
  - id: optimize-token-usage
    content: 实现对话历史压缩和工具结果摘要，减少token消耗
    status: completed
  - id: enhance-multi-turn-context
    content: 增强多轮对话上下文理解，支持指代消解和需求状态管理
    status: completed
  - id: add-sorting-logic
    content: 实现智能排序逻辑，支持用户指定的排序方式和匹配度排序
    status: completed
    dependencies:
      - optimize-house-id-extraction
---

# Agent优化方案

## 一、优化目标分析

### 1.1 Agent核心要求

- **需求理解能力**：精准识别多元需求，处理模糊/隐含需求，主动追问
- **自主决策能力**：自动筛选、核验、分类房源
- **信息整合能力**：多平台对比、多维度分析
- **结果输出能力**：清晰、直观、最多5套候选房源

### 1.2 打榜用例类型

- **Chat类（5分）**：基础对话能力
- **Single类（10-15分）**：单轮简单/复杂查询（单条件→多条件）
- **Multi类（20-30分）**：多轮查询、房源对比、边聊天边查询并租房（5-7轮）

### 1.3 评分规则关键点

- **时间片限制**：300时间片内完成所有用例
- **Token消耗公式**：`t = 1 + max(0, (n-1k)) * 0.3`，需控制每次调用的token数
- **计分规则**：按答案匹配数量给分，匹配越多得分越高
- **排名规则**：得分优先，token消耗次之
- **时间限制**：单用例执行时间（减去模型调用时间）≤5秒

## 二、当前实现分析

### 2.1 代码结构

- [services/agent_service.py](services/agent_service.py)：核心处理逻辑，支持多轮工具调用
- [tools/house_tools.py](tools/house_tools.py)：工具定义和实现
- [services/llm_client.py](services/llm_client.py)：LLM调用封装
- [services/session_manager.py](services/session_manager.py)：会话管理

### 2.2 当前问题

1. **缺少System Prompt**：LLM没有明确的角色定位和任务指导
2. **工具调用策略不明确**：依赖LLM自主决策，可能产生无效调用
3. **结果格式化逻辑简单**：`_format_response`可能无法准确提取房源ID
4. **多轮对话上下文管理**：缺少需求提取和状态管理
5. **Token消耗未优化**：对话历史可能过长，工具结果可能冗余
6. **排序和筛选逻辑**：依赖API排序，缺少智能排序策略
7. **多平台对比能力**：未实现多平台交叉筛选和比价
8. **租房操作识别**：需要准确识别用户租房意图并调用API

## 三、优化方案

### 3.1 需求理解优化

#### 3.1.1 添加System Prompt

**位置**：[services/agent_service.py](services/agent_service.py) `process_message`方法

**优化点**：

- 在首次调用LLM时添加system message，明确Agent角色和任务
- 指导LLM如何理解租房需求、调用工具、格式化输出
- 强调关键规则：近地铁=800米以内、最多返回5套房源、查询结果需JSON格式

#### 3.1.2 需求提取和状态管理

**位置**：新增 `services/requirement_extractor.py`

**优化点**：

- 从对话历史中提取结构化需求（区域、价格、户型、地铁距离等）
- 维护需求状态，支持多轮对话中的需求更新
- 识别模糊需求，指导LLM主动追问

### 3.2 工具调用优化

#### 3.2.1 工具调用策略优化

**位置**：[services/agent_service.py](services/agent_service.py)

**优化点**：

- 优化工具描述，明确使用场景和参数要求
- 添加工具调用前的需求验证逻辑
- 实现智能重试机制：查询无结果时放宽条件重新查询

#### 3.2.2 多平台对比能力

**位置**：[tools/house_tools.py](tools/house_tools.py)

**优化点**：

- 新增 `compare_platforms` 工具，支持链家/安居客/58同城交叉查询
- 实现比价逻辑，对比同一房源在不同平台的价格
- 在工具描述中强调多平台查询的重要性

#### 3.2.3 排序和筛选优化

**位置**：[services/agent_service.py](services/agent_service.py) `_format_response`方法

**优化点**：

- 实现智能排序：优先匹配度、价格、地铁距离
- 支持用户指定的排序方式（如"按离地铁从近到远"）
- 确保返回的房源ID顺序符合用户要求

### 3.3 结果输出优化

#### 3.3.1 房源ID提取优化

**位置**：[services/agent_service.py](services/agent_service.py) `_format_response`方法

**优化点**：

- 增强房源ID提取逻辑，支持多种API响应格式
- 从LLM回复中提取房源ID（当工具结果解析失败时）
- 验证房源ID格式（HF_xxx），过滤无效ID

#### 3.3.2 输出格式优化

**位置**：[services/agent_service.py](services/agent_service.py)

**优化点**：

- 确保查询结果始终返回JSON格式（符合用例要求）
- 优化message内容，包含关键信息（区域、户型、地铁距离等）
- 支持"没有房源"场景的正确输出

#### 3.3.3 租房操作识别

**位置**：[services/agent_service.py](services/agent_service.py)

**优化点**：

- 识别用户租房意图（如"就租最近的那套"）
- 自动调用 `rent_house` 工具
- 从对话历史或查询结果中提取房源ID和平台信息

### 3.4 性能优化

#### 3.4.1 Token消耗优化

**位置**：[services/session_manager.py](services/session_manager.py)

**优化点**：

- 实现对话历史压缩：保留关键信息，删除冗余内容
- 工具结果摘要：只保留关键字段（房源ID、价格、地铁距离等）
- 限制对话历史长度：最多保留最近N轮对话

#### 3.4.2 执行时间优化

**位置**：[services/agent_service.py](services/agent_service.py)

**优化点**：

- 优化工具调用顺序：并行调用独立工具
- 减少不必要的工具调用：缓存查询结果
- 优化API调用：使用合适的page_size，减少分页查询

#### 3.4.3 迭代次数优化

**位置**：[services/agent_service.py](services/agent_service.py)

**优化点**：

- 动态调整 `max_iterations`：根据任务复杂度调整
- 提前终止机制：查询到足够房源后提前结束
- 错误恢复机制：工具调用失败时的重试策略

### 3.5 多轮对话优化

#### 3.5.1 上下文理解

**位置**：[services/agent_service.py](services/agent_service.py)

**优化点**：

- 识别指代消解（"最近的那套"、"其他的"）
- 维护查询历史，支持"还有其他的吗"类查询
- 识别需求变更，支持动态调整查询条件

#### 3.5.2 状态管理

**位置**：[services/session_manager.py](services/session_manager.py)

**优化点**：

- 维护查询状态：当前查询条件、已返回房源列表
- 支持增量查询：基于已有结果继续查询
- 维护租房状态：已租房源列表

## 四、实施优先级

### 高优先级（直接影响用例通过率）

1. System Prompt添加
2. 房源ID提取优化
3. 租房操作识别
4. 输出格式优化（JSON格式确保）

### 中优先级（提升得分和性能）

5. 需求提取和状态管理
6. 工具调用策略优化
7. Token消耗优化
8. 多轮对话上下文理解

### 低优先级（锦上添花）

9. 多平台对比能力
10. 智能排序和筛选
11. 执行时间优化

## 五、关键文件修改清单

1. [services/agent_service.py](services/agent_service.py)

- 添加system prompt
- 优化 `_format_response` 方法
- 添加租房操作识别逻辑
- 优化工具调用循环

2. [tools/house_tools.py](tools/house_tools.py)

- 优化工具描述
- 添加多平台对比工具（可选）

3. [services/session_manager.py](services/session_manager.py)

- 添加对话历史压缩
- 添加状态管理功能

4. 新增文件

- `services/requirement_extractor.py`：需求提取模块（可选）
- `utils/response_formatter.py`：响应格式化工具（可选）

## 六、测试验证

1. **用例1验证**：无房源场景，确保返回"没有"和空列表
2. **用例2验证**：单轮查询+多轮追问，确保房源ID和排序正确
3. **用例3验证**：多轮查询+租房操作，确保识别租房意图并调用API
4. **性能测试**：验证token消耗和执行时间
5. **边界测试**：模糊需求、指代消解、多平台查询等场景
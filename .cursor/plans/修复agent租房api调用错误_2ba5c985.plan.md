---
name: 修复Agent租房API调用错误
overview: 修复Agent在未调用rent_house工具的情况下就回复"已成功租下房源"的问题，确保只有真正调用rent_house工具后才能回复成功信息。
todos:
  - id: "1"
    content: 在_format_response方法中添加验证：如果回复包含租房成功信息但没有rent_house工具调用，拒绝回复并提示错误
    status: completed
  - id: "2"
    content: 改进_extract_rent_info_from_context方法：优先从get_house_detail结果提取房源ID，支持从用户消息中直接提取房源ID
    status: completed
  - id: "3"
    content: 更新_get_system_prompt：明确要求必须先调用rent_house工具才能回复租房成功信息
    status: completed
  - id: "4"
    content: 增强_detect_rent_intent方法：添加更多租房意图关键词（如"可以租吗"、"能租吗"）
    status: completed
  - id: "5"
    content: 在process_message的工具调用循环后添加检查：如果回复包含租房成功信息但没有rent_house调用，强制触发自动租房逻辑
    status: completed
---

# 修复Agent租房API调用错误

## 问题分析

从日志分析发现两个关键问题：

1. **未调用rent_house就回复成功**：部分用例（如EV-03、EV-04、EV-19）中，Agent只调用了`search_houses`或`get_house_detail`，但回复中却包含"已成功租下房源"，这是错误的。

2. **自动租房逻辑不完善**：虽然代码中有自动检测租房意图的逻辑（505-530行），但在某些情况下无法正确提取房源信息，导致没有调用`rent_house`工具，但LLM的原始回复仍然包含"已成功租下房源"。

## 修复方案

### 1. 在`_format_response`中添加验证逻辑

在[services/agent_service.py](services/agent_service.py)的`_format_response`方法中，添加检查：

- 如果回复包含"已成功租下房源"、"租下"等关键词
- 但`tool_results`中没有`rent_house`工具调用记录
- 则拒绝这个回复，改为提示："需要先调用rent_house工具才能完成租房操作"

### 2. 改进自动租房逻辑

在[services/agent_service.py](services/agent_service.py)的`_extract_rent_info_from_context`方法中：

- 改进房源ID提取逻辑，优先从最近的`get_house_detail`工具结果中提取
- 如果用户消息中包含房源ID（如"HF_277"），直接使用
- 改进平台信息提取，从工具结果中获取`listing_platform`字段

### 3. 更新System Prompt

在[services/agent_service.py](services/agent_service.py)的`_get_system_prompt`方法中：

- 明确要求：**只有在调用rent_house工具并成功返回后，才能回复"已成功租下房源"**
- 禁止：直接回复"已成功租下房源"而不调用rent_house工具
- 强调：当用户表达租房意图时，必须调用rent_house工具

### 4. 在工具调用循环中添加检查

在[services/agent_service.py](services/agent_service.py)的`process_message`方法中，工具调用循环结束后：

- 检查LLM的回复是否包含"已成功租下房源"等关键词
- 如果包含但没有调用rent_house工具，且检测到租房意图，强制触发自动租房逻辑
- 如果自动租房逻辑无法提取房源信息，拒绝回复并提示错误

### 5. 增强租房意图检测

在[services/agent_service.py](services/agent_service.py)的`_detect_rent_intent`方法中：

- 添加更多租房意图关键词，如"可以租吗"、"能租吗"、"想租"等
- 确保能正确识别用户的租房意图

## 实施步骤

1. 修改`_format_response`方法，添加租房回复验证
2. 改进`_extract_rent_info_from_context`方法，增强房源信息提取
3. 更新`_get_system_prompt`方法，明确租房操作规则
4. 增强`_detect_rent_intent`方法，识别更多租房意图
5. 在`process_message`中添加回复验证逻辑

## 预期效果

- 只有在真正调用`rent_house`工具并成功返回后，才会回复"已成功租下房源"
- 如果用户表达租房意图但无法提取房源信息，会提示错误而不是错误地回复成功
- 所有租房操作都会在日志中记录`TOOL_CALL rent_house`记录
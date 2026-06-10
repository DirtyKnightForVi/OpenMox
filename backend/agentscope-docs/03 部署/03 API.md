# AgentScope API 参考文档

> 整合自 AgentScope 官方 API 文档
> 来源：https://docs.agentscope.io/api-reference/

---

## 目录

1. [Agent（智能体）](#1-agent智能体)
   - 1.1 [GET /agent - 列出所有智能体](#11-get-agent-列出所有智能体)
   - 1.2 [POST /agent - 创建新智能体](#12-post-agent-创建新智能体)
   - 1.3 [DELETE /agent/{agent_id} - 删除智能体](#13-delete-agentagent_id-删除智能体)
   - 1.4 [PATCH /agent/{agent_id} - 更新智能体](#14-patch-agentagent_id-更新智能体)
2. [Background Tasks（后台任务）](#2-background-tasks后台任务)
   - 2.1 [GET /background-tasks/{session_id} - 列出会话的后台任务](#21-get-background-taskssession_id-列出会话的后台任务)
   - 2.2 [DELETE /background-tasks/{session_id}/{task_id} - 取消后台任务](#22-delete-background-taskssession_idtask_id-取消后台任务)
3. [Chat（聊天）](#3-chat聊天)
   - 3.1 [POST /chat - 与智能体流式聊天](#31-post-chat-与智能体流式聊天)
4. [Credential（凭证）](#4-credential凭证)
   - 4.1 [GET /credential/schemas - 列出所有凭证类型的 JSON Schema](#41-get-credentialschemas-列出所有凭证类型的-json-schema)
   - 4.2 [GET /credential - 列出所有凭证](#42-get-credential-列出所有凭证)
   - 4.3 [POST /credential - 创建新凭证](#43-post-credential-创建新凭证)
   - 4.4 [DELETE /credential/{credential_id} - 删除凭证](#44-delete-credentialcredential_id-删除凭证)
   - 4.5 [PATCH /credential/{credential_id} - 更新凭证](#45-patch-credentialcredential_id-更新凭证)
5. [Model（模型）](#5-model模型)
   - 5.1 [GET /model - 列出指定凭证类型下的候选模型](#51-get-model-列出指定凭证类型下的候选模型)
6. [Schedule（定时任务）](#6-schedule定时任务)
   - 6.1 [GET /schedule - 列出所有定时任务](#61-get-schedule-列出所有定时任务)
   - 6.2 [POST /schedule - 创建新定时任务](#62-post-schedule-创建新定时任务)
   - 6.3 [DELETE /schedule/{schedule_id} - 删除定时任务](#63-delete-scheduleschedule_id-删除定时任务)
   - 6.4 [PATCH /schedule/{schedule_id} - 更新定时任务](#64-patch-scheduleschedule_id-更新定时任务)
   - 6.5 [GET /schedule/{schedule_id}/sessions - 列出定时任务的执行会话](#65-get-scheduleschedule_idsessions-列出定时任务的执行会话)
7. [Sessions（会话）](#7-sessions会话)
   - 7.1 [GET /sessions - 列出智能体的所有会话](#71-get-sessions-列出智能体的所有会话)
   - 7.2 [POST /sessions - 创建新会话](#72-post-sessions-创建新会话)
   - 7.3 [DELETE /sessions/{session_id} - 删除会话](#73-delete-sessionssession_id-删除会话)
   - 7.4 [PATCH /sessions/{session_id} - 更新会话](#74-patch-sessionssession_id-更新会话)
   - 7.5 [GET /sessions/{session_id}/messages - 列出会话消息](#75-get-sessionssession_idmessages-列出会话消息)
8. [Workspace（工作空间）](#8-workspace工作空间)
   - 8.1 [GET /workspace/mcp - 列出 MCP 客户端](#81-get-workspacemcp-列出-mcp-客户端)
   - 8.2 [POST /workspace/mcp - 添加 MCP 客户端](#82-post-workspacemcp-添加-mcp-客户端)
   - 8.3 [DELETE /workspace/mcp/{mcp_name} - 移除 MCP 客户端](#83-delete-workspacemcpmcp_name-移除-mcp-客户端)
   - 8.4 [GET /workspace/skill - 列出技能](#84-get-workspaceskill-列出技能)
   - 8.5 [POST /workspace/skill - 添加技能](#85-post-workspaceskill-添加技能)
   - 8.6 [DELETE /workspace/skill/{skill_name} - 移除技能](#86-delete-workspaceskillskill_name-移除技能)

---

# 1. Agent（智能体）

## 1.1 GET /agent 列出所有智能体

返回属于已验证用户的所有智能体记录。

**端点：** `GET /agent`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID（临时基于请求头的身份标识，后续将替换为 JWT 认证） |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/agent/ \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
{
  "agents": [
    {
      "user_id": "<string>",
      "data": {
        "name": "<string>",
        "system_prompt": "<string>",
        "context_config": {
          "trigger_ratio": 0.8,
          "reserve_ratio": 0.1,
          "compression_prompt": "<system-hint>You have been working on the task described above but have not yet completed it...</system-hint>",
          "summary_template": "<system-info>Here is a summary of your previous work...</system-info>",
          "summary_schema": {},
          "tool_result_limit": 3000
        },
        "react_config": {
          "max_iters": 20,
          "stop_on_reject": false
        },
        "id": "<string>"
      },
      "id": "<string>",
      "updated_at": "2023-11-07T05:31:56Z",
      "created_at": "2023-11-07T05:31:56Z"
    }
  ],
  "total": 123
}
```

**响应字段说明：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agents | AgentRecord[] | 是 | 智能体记录数组 |
| agents[].user_id | string | - | 用户 ID |
| agents[].data.name | string | - | 智能体名称 |
| agents[].data.system_prompt | string | - | 基础系统提示词 |
| agents[].data.context_config | ContextConfig | - | 上下文窗口管理配置 |
| agents[].data.context_config.trigger_ratio | number | - | 触发压缩的比率阈值 |
| agents[].data.context_config.reserve_ratio | number | - | 压缩后保留的比率 |
| agents[].data.context_config.tool_result_limit | number | - | 工具结果限制长度 |
| agents[].data.react_config | ReActConfig | - | ReAct 循环配置 |
| agents[].data.react_config.max_iters | number | - | 最大迭代次数 |
| agents[].data.react_config.stop_on_reject | boolean | - | 被拒绝时是否停止 |
| agents[].id | string | - | 记录 ID |
| agents[].updated_at | datetime | - | 更新时间 |
| agents[].created_at | datetime | - | 创建时间 |
| total | integer | 是 | 智能体总数 |

---

## 1.2 POST /agent 创建新智能体

创建并持久化一个新的智能体配置。

**端点：** `POST /agent`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/agent/ \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data @- <<EOF
{
  "name": "<string>",
  "system_prompt": "You're a helpful assistant.",
  "context_config": {
    "trigger_ratio": 0.8,
    "reserve_ratio": 0.1,
    "compression_prompt": "<system-hint>...</system-hint>",
    "summary_template": "<system-info>...</system-info>",
    "summary_schema": {},
    "tool_result_limit": 3000
  },
  "react_config": {
    "max_iters": 20,
    "stop_on_reject": false
  }
}
EOF
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | 是 | 智能体的显示名称 |
| system_prompt | string | 否（默认：You're a helpful assistant.） | 提供给智能体的基础系统提示词 |
| context_config | ContextConfig | 否 | 上下文窗口管理配置 |
| react_config | ReActConfig | 否 | ReAct 循环配置 |

**响应 (200)：**
```json
{
  "agent_id": "<string>"
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 服务端分配的智能体标识符 |

---

## 1.3 DELETE /agent/{agent_id} 删除智能体

永久删除一个智能体配置。

**端点：** `DELETE /agent/{agent_id}`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 要删除的智能体 ID |

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/agent/{agent_id} \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：** 空响应

**错误：** 404 — 智能体不存在或不属于该用户

---

## 1.4 PATCH /agent/{agent_id} 更新智能体

部分更新一个现有的智能体配置。仅更新请求体中存在的字段，其余字段保持当前值。

**端点：** `PATCH /agent/{agent_id}`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 要更新的智能体 ID |

**cURL 示例：**
```bash
curl --request PATCH \
  --url https://api.example.com/agent/{agent_id} \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "name": "<string>",
  "system_prompt": "<string>",
  "context_config": { ... },
  "react_config": { ... }
}'
```

**请求体参数：** 与创建智能体的请求体结构相同，所有字段可选。

**响应 (200)：** 返回完整的 `AgentRecord`（与 `GET /agent` 中的记录结构相同）。

**错误：** 404 — 智能体不存在或不属于该用户

---

# 2. Background Tasks（后台任务）

## 2.1 GET /background-tasks/{session_id} 列出会话的后台任务

列出指定 `session_id` 下所有正在运行的后台任务。

**端点：** `GET /background-tasks/{session_id}`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| session_id | string | 是 | 要查询的会话 ID |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/background-tasks/{session_id} \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
{
  "tasks": [
    {
      "task_id": "<string>",
      "session_id": "<string>",
      "agent_id": "<string>"
    }
  ],
  "total": 123
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| tasks | BackgroundTaskInfo[] | 是 | 正在运行的后台任务 |
| tasks[].task_id | string | - | 任务 ID |
| tasks[].session_id | string | - | 会话 ID |
| tasks[].agent_id | string | - | 智能体 ID |
| total | integer | 是 | 运行中的任务总数 |

---

## 2.2 DELETE /background-tasks/{session_id}/{task_id} 取消后台任务

通过 `task_id` 取消一个正在运行的后台任务。底层的 asyncio 任务会立即被取消，`on_complete` 回调不会被调用。

**端点：** `DELETE /background-tasks/{session_id}/{task_id}`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| session_id | string | 是 | 拥有者会话 ID |
| task_id | string | 是 | 要取消的任务 ID |

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/background-tasks/{session_id}/{task_id} \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：** 空响应

**错误：** 404 — task_id 未找到或不属于该 session_id

---

# 3. Chat（聊天）

## 3.1 POST /chat 与智能体流式聊天

向智能体发送消息并以 SSE（Server-Sent Events）事件流的方式流式返回回复。

**端点：** `POST /chat`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/chat/ \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "agent_id": "<string>",
  "session_id": "<string>",
  "input": {
    "name": "<string>",
    "content": [
      {
        "text": "<string>",
        "type": "text",
        "id": "<string>"
      }
    ],
    "id": "<string>",
    "metadata": {},
    "created_at": "<string>",
    "finished_at": "<string>",
    "usage": {
      "input_tokens": 123,
      "output_tokens": 123
    }
  }
}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 聊天目标的智能体 ID |
| session_id | string | 是 | 要发送消息的会话 |
| input | Msg | 是 | AgentScope 中的消息对象，负责智能体间的信息存储和传输 |

**响应：** `text/event-stream` 格式的 SSE 流，每个 frame 携带一个 JSON 序列化的 `AgentEvent` 对象。

---

# 4. Credential（凭证）

## 4.1 GET /credential/schemas 列出所有凭证类型的 JSON Schema

返回所有已注册凭证类型的 JSON Schema。用于前端动态渲染凭证创建表单。

**端点：** `GET /credential/schemas`

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/credential/schemas
```

**响应 (200)：**
```json
{
  "schemas": [{}]
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| schemas | object[] | 是 | 所有已注册凭证类型的 JSON Schema |

---

## 4.2 GET /credential 列出所有凭证

返回属于已验证用户的所有凭证记录。

**端点：** `GET /credential`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/credential/ \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
{
  "credentials": [
    {
      "data": {},
      "id": "<string>",
      "updated_at": "2023-11-07T05:31:56Z",
      "created_at": "2023-11-07T05:31:56Z",
      "user_id": "<string>"
    }
  ],
  "total": 123
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| credentials | CredentialRecord[] | 是 | 凭证记录 |
| total | integer | 是 | 凭证总数 |

---

## 4.3 POST /credential 创建新凭证

存储一个新的凭证。

**端点：** `POST /credential`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/credential/ \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{"data": {}}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| data | object | 是 | 凭证有效载荷（如 API 密钥） |

**响应 (200)：**
```json
{
  "credential_id": "<string>"
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| credential_id | string | 是 | 服务端分配的凭证标识符 |

---

## 4.4 DELETE /credential/{credential_id} 删除凭证

永久删除一个凭证。

**端点：** `DELETE /credential/{credential_id}`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| credential_id | string | 是 | 要删除的凭证 ID |

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/credential/{credential_id} \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：** 空响应

**错误：** 404 — 凭证不存在或不属于该用户

---

## 4.5 PATCH /credential/{credential_id} 更新凭证

替换现有凭证的有效载荷。

**端点：** `PATCH /credential/{credential_id}`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| credential_id | string | 是 | 要更新的凭证 ID |

**cURL 示例：**
```bash
curl --request PATCH \
  --url https://api.example.com/credential/{credential_id} \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{"data": {}}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| data | object | 是 | 新的凭证有效载荷 |

**响应 (200)：** 返回完整的 `CredentialRecord`。

**错误：** 404 — 凭证不存在或不属于该用户

---

# 5. Model（模型）

## 5.1 GET /model 列出指定凭证类型下的候选模型

返回指定凭证类型下的所有候选模型。

**端点：** `GET /model`

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| provider | string | 是 | 凭证提供商类型 |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/model/
```

**响应 (200)：**
```json
{
  "models": [
    {
      "name": "<string>",
      "label": "<string>",
      "context_size": 123,
      "output_size": 123,
      "parameter_schema": {},
      "parameters_overrides": {},
      "type": "chat_model",
      "deprecated_at": "2023-11-07T05:31:56Z",
      "input_types": ["text/plain"],
      "output_types": ["text/plain"]
    }
  ],
  "total": 123
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| models | ModelCard[] | 是 | 候选模型列表 |
| models[].name | string | - | 模型名称 |
| models[].label | string | - | 模型标签 |
| models[].context_size | integer | - | 上下文大小 |
| models[].output_size | integer | - | 输出大小 |
| models[].parameter_schema | object | - | 参数 Schema |
| models[].parameters_overrides | object | - | 参数覆盖 |
| models[].type | string | - | 模型类型（chat_model 等） |
| models[].deprecated_at | datetime | - | 弃用时间 |
| models[].input_types | string[] | - | 输入类型 |
| models[].output_types | string[] | - | 输出类型 |
| total | integer | 是 | 候选模型总数 |

---

# 6. Schedule（定时任务）

## 6.1 GET /schedule 列出所有定时任务

列出当前用户拥有的所有定时任务。

**端点：** `GET /schedule`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/schedule/ \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
{
  "schedules": [
    {
      "user_id": "<string>",
      "agent_id": "<string>",
      "data": {
        "name": "<string>",
        "cron_expression": "<string>",
        "started_at": "2023-11-07T05:31:56Z",
        "chat_model_config": {
          "type": "<string>",
          "credential_id": "<string>",
          "model": "<string>",
          "parameters": {}
        },
        "description": "",
        "enabled": true,
        "timezone": "UTC",
        "ended_at": "2023-11-07T05:31:56Z",
        "stateful": false,
        "permission_mode": "dont_ask",
        "source": "USER",
        "source_session_id": ""
      },
      "id": "<string>",
      "updated_at": "2023-11-07T05:31:56Z",
      "created_at": "2023-11-07T05:31:56Z"
    }
  ],
  "total": 123
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| schedules | ScheduleRecord[] | 是 | 定时任务记录 |
| schedules[].data.name | string | - | 定时任务名称 |
| schedules[].data.cron_expression | string | - | Cron 表达式 |
| schedules[].data.started_at | datetime | - | 开始时间 |
| schedules[].data.chat_model_config | object | - | 模型配置 |
| schedules[].data.description | string | - | 描述 |
| schedules[].data.enabled | boolean | - | 是否启用 |
| schedules[].data.timezone | string | - | 时区 |
| schedules[].data.ended_at | datetime | - | 结束时间 |
| schedules[].data.stateful | boolean | - | 是否保持状态 |
| schedules[].data.permission_mode | string | - | 权限模式 |
| schedules[].data.source | string | - | 来源 |
| total | integer | 是 | 定时任务总数 |

---

## 6.2 POST /schedule 创建新定时任务

创建一个新的定时任务并注册到调度器。

**端点：** `POST /schedule`

**请求头：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| x-user-id | string | 是 | 调用者的用户 ID |

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/schedule/ \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "name": "<string>",
  "cron_expression": "<string>",
  "agent_id": "<string>",
  "chat_model_config": {
    "type": "<string>",
    "credential_id": "<string>",
    "model": "<string>",
    "parameters": {}
  },
  "description": "",
  "timezone": "UTC",
  "enabled": true,
  "stateful": false,
  "permission_mode": "dont_ask"
}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| name | string | 是 | - | 定时任务的显示名称 |
| cron_expression | string | 是 | - | 标准 5 字段 Cron 表达式，如 '0 9 * * 1-5' |
| agent_id | string | 是 | - | 定时触发时运行的智能体 |
| chat_model_config | ChatModelConfig | 是 | - | 自动创建会话的模型配置 |
| description | string | 否 | "" | 可选描述 |
| timezone | string | 否 | "UTC" | IANA 时区名，如 'America/New_York' |
| enabled | boolean | 否 | true | 创建后是否立即激活 |
| stateful | boolean | 否 | false | 为 true 时连续执行共享同一会话上下文 |
| permission_mode | enum | 否 | "dont_ask" | 定时执行时智能体的权限级别 |

**permission_mode 可选值：** `default`、`accept_edits`、`explore`、`bypass`、`dont_ask`

**响应 (200)：**
```json
{
  "schedule_id": "<string>"
}
```

---

## 6.3 DELETE /schedule/{schedule_id} 删除定时任务

永久删除一个定时任务。从存储中移除记录并从 APScheduler 中注销该任务。

**端点：** `DELETE /schedule/{schedule_id}`

**请求头：** 需 `x-user-id`

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/schedule/{schedule_id} \
  --header 'x-user-id: <x-user-id>'
```

**错误：** 404 — 定时任务不存在

---

## 6.4 PATCH /schedule/{schedule_id} 更新定时任务

部分更新一个定时任务。省略的字段保持当前值。更改 `cron_expression` 或 `timezone` 会立即重新调度 APScheduler 任务。

**端点：** `PATCH /schedule/{schedule_id}`

**请求头：** 需 `x-user-id`

**cURL 示例：**
```bash
curl --request PATCH \
  --url https://api.example.com/schedule/{schedule_id} \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "name": "<string>",
  "description": "<string>",
  "cron_expression": "<string>",
  "timezone": "<string>",
  "enabled": true,
  "stateful": true
}'
```

**请求体参数（所有字段可选）：**

| 参数 | 类型 | 描述 |
|------|------|------|
| name | string | null | 新的显示名称 |
| description | string | null | 新的描述 |
| cron_expression | string | null | 新的 Cron 表达式 |
| timezone | string | null | 新的 IANA 时区 |
| enabled | boolean | 是否启用（设为 false 从调度器中移除但保留记录） |
| stateful | boolean | 是否保持状态 |

**响应：** 返回完整的 `ScheduleRecord`

---

## 6.5 GET /schedule/{schedule_id}/sessions 列出定时任务的执行会话

返回指定定时任务触发的所有会话。

**端点：** `GET /schedule/{schedule_id}/sessions`

**请求头：** 需 `x-user-id`

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/schedule/{schedule_id}/sessions \
  --header 'x-user-id: <x-user-id>'
```

**响应：** 包含 `sessions` 数组和 `total` 总数，按创建时间倒序排列。

**详情请查看原始响应示例。**

---

# 7. Sessions（会话）

## 7.1 GET /sessions 列出智能体的所有会话

返回属于已验证用户的指定智能体的所有会话。

**端点：** `GET /sessions`

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 要列出会话的智能体 ID |

**请求头：** 需 `x-user-id`

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/sessions/ \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：** 包含 `sessions` 数组（SessionRecord）和 `total` 总数。

**错误：** 404 — 智能体不存在或不属于该用户

---

## 7.2 POST /sessions 创建新会话

为给定的智能体和工作空间创建（或恢复）一个会话。对于同一 `(user_id, agent_id, workspace_id)` 三元组最多存在一个会话。

**端点：** `POST /sessions`

**请求头：** 需 `x-user-id`

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/sessions/ \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "agent_id": "<string>",
  "workspace_id": "<string>",
  "name": "<string>",
  "chat_model_config": {
    "type": "<string>",
    "credential_id": "<string>",
    "model": "<string>",
    "parameters": {}
  }
}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 会话所属的智能体 |
| workspace_id | string | null | 会话所属的工作空间 |
| name | string | null | 显示名称（省略时默认为当前日期时间） |
| chat_model_config | ChatModelConfig | 否 | 模型提供者和参数 |

**响应 (200)：**
```json
{
  "session_id": "<string>"
}
```

---

## 7.3 DELETE /sessions/{session_id} 删除会话

永久删除一个会话及其所有关联状态。

**端点：** `DELETE /sessions/{session_id}`

**请求头：** 需 `x-user-id`

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| session_id | string | 是 | 要删除的会话 ID |

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 会话所属的智能体 |

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/sessions/{session_id} \
  --header 'x-user-id: <x-user-id>'
```

**错误：** 404 — 会话不存在或不属于该用户

---

## 7.4 PATCH /sessions/{session_id} 更新会话

更新现有会话的模型配置。

**端点：** `PATCH /sessions/{session_id}`

**请求头：** 需 `x-user-id`

**cURL 示例：**
```bash
curl --request PATCH \
  --url https://api.example.com/sessions/{session_id} \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "name": "<string>",
  "chat_model_config": {
    "type": "<string>",
    "credential_id": "<string>",
    "model": "<string>",
    "parameters": {}
  }
}'
```

**响应：** 返回完整的 `SessionRecord`。

**错误：** 404 — 会话、智能体或凭证不存在或不属于该用户

---

## 7.5 GET /sessions/{session_id}/messages 列出会话消息

返回会话中持久化的消息。

**端点：** `GET /sessions/{session_id}/messages`

**请求头：** 需 `x-user-id`

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| session_id | string | 是 | 要查询的会话 |

**查询参数：**

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| agent_id | string | 是 | - | 会话所属的智能体 |
| offset | integer | 否 | 0 | 分页偏移量（>= 0） |
| limit | integer | 否 | 50 | 最大消息数（1-200） |

**cURL 示例：**
```bash
curl --request GET \
  --url 'https://api.example.com/sessions/{session_id}/messages?limit=50' \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
{
  "messages": [],
  "is_running": true
}
```

**响应字段：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| messages | any[] | 是 | 按时间顺序排列的消息 |
| is_running | boolean | 是 | 会话是否正在运行 |

---

# 8. Workspace（工作空间）

## 8.1 GET /workspace/mcp 列出 MCP 客户端

返回所有 MCP 客户端及其实时工具列表和健康状态。

**端点：** `GET /workspace/mcp`

**请求头：** 需 `x-user-id`

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 智能体 ID |
| session_id | string | 是 | 会话 ID |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/workspace/mcp \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
[
  {
    "name": "<string>",
    "is_stateful": true,
    "mcp_config": {
      "command": "<string>",
      "type": "stdio_mcp",
      "args": ["<string>"],
      "env": {},
      "cwd": "<string>",
      "encoding_error_handler": "strict"
    },
    "enable_tools": ["<string>"],
    "disable_tools": ["<string>"],
    "execution_timeout": 123,
    "is_healthy": false,
    "tools": [
      {
        "name": "<string>",
        "description": "<string>"
      }
    ]
  }
]
```

---

## 8.2 POST /workspace/mcp 添加 MCP 客户端

向会话的工作空间添加一个 MCP 客户端。

**端点：** `POST /workspace/mcp`

**请求头：** 需 `x-user-id`

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 智能体 ID |
| session_id | string | 是 | 会话 ID |

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/workspace/mcp \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{
  "name": "<string>",
  "is_stateful": true,
  "mcp_config": {
    "command": "<string>",
    "type": "stdio_mcp",
    "args": ["<string>"],
    "env": {},
    "cwd": "<string>",
    "encoding_error_handler": "strict"
  },
  "enable_tools": ["<string>"],
  "disable_tools": ["<string>"],
  "execution_timeout": 123
}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| name | string | 是 | MCP 名称 |
| is_stateful | boolean | 是 | 是否为有状态连接。STDIO MCP 必须为有状态，HTTP MCP 可以有/无状态 |
| mcp_config | StdioMCPConfig / HttpMCPConfig | 是 | MCP 服务器配置 |
| enable_tools | string[] | 否 | 启用的工具列表 |
| disable_tools | string[] | 否 | 禁用的工具列表 |
| execution_timeout | number | 否 | 执行超时时间 |

---

## 8.3 DELETE /workspace/mcp/{mcp_name} 移除 MCP 客户端

按名称从会话的工作空间中移除一个 MCP 客户端。

**端点：** `DELETE /workspace/mcp/{mcp_name}`

**请求头：** 需 `x-user-id`

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| mcp_name | string | 是 | MCP 客户端名称 |

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 智能体 ID |
| session_id | string | 是 | 会话 ID |

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/workspace/mcp/{mcp_name} \
  --header 'x-user-id: <x-user-id>'
```

---

## 8.4 GET /workspace/skill 列出技能

返回会话工作空间中所有可用的技能。

**端点：** `GET /workspace/skill`

**请求头：** 需 `x-user-id`

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 智能体 ID |
| session_id | string | 是 | 会话 ID |

**cURL 示例：**
```bash
curl --request GET \
  --url https://api.example.com/workspace/skill \
  --header 'x-user-id: <x-user-id>'
```

**响应 (200)：**
```json
[
  {
    "name": "<string>",
    "description": "<string>",
    "dir": "<string>",
    "markdown": "<string>",
    "updated_at": 123
  }
]
```

**响应字段：**

| 字段 | 类型 | 描述 |
|------|------|------|
| name | string | 技能名称 |
| description | string | 技能描述 |
| dir | string | 技能目录 |
| markdown | string | 技能的 Markdown 内容 |
| updated_at | number | 更新时间戳 |

---

## 8.5 POST /workspace/skill 添加技能

从指定路径向会话的工作空间添加一个技能。

**端点：** `POST /workspace/skill`

**请求头：** 需 `x-user-id`

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 智能体 ID |
| session_id | string | 是 | 会话 ID |

**cURL 示例：**
```bash
curl --request POST \
  --url https://api.example.com/workspace/skill \
  --header 'Content-Type: application/json' \
  --header 'x-user-id: <x-user-id>' \
  --data '{"skill_path": "<string>"}'
```

**请求体参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| skill_path | string | 是 | 技能路径 |

---

## 8.6 DELETE /workspace/skill/{skill_name} 移除技能

按名称从会话的工作空间中移除一个技能。

**端点：** `DELETE /workspace/skill/{skill_name}`

**请求头：** 需 `x-user-id`

**路径参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| skill_name | string | 是 | 技能名称 |

**查询参数：**

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| agent_id | string | 是 | 智能体 ID |
| session_id | string | 是 | 会话 ID |

**cURL 示例：**
```bash
curl --request DELETE \
  --url https://api.example.com/workspace/skill/{skill_name} \
  --header 'x-user-id: <x-user-id>'
```

---

> 本文档由 BrowserOS 自动爬取整合
> 源文档：https://docs.agentscope.io/api-reference/

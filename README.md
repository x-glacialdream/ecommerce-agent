# Minimal E-commerce Agent

一个基于 **FastAPI + Gemini + ReAct** 的最小电商 Agent 项目。
系统支持多工具协同、轻量检索增强、上下文压缩、结构化日志，以及基础的安全控制与服务化部署。

当前已实现：

* FastAPI 服务化接口
* Gemini 驱动的多步决策
* ReAct 风格任务执行链路
* 三个工具协同：
    * 订单修改 `modify_order`
    * 物流查询 `query_logistics`
    * 规则知识检索 `query_kb`
* Tool Schema 标准化
* 轻量 RAG 检索层（关键词召回 + top-k + score + evidence）
* 上下文压缩（最近步骤保留细节，历史步骤做摘要）
* Max-Step 与循环检测
* request_id / trace_id
* 结构化 JSON 日志
* `/health` 与 `/tools` 对外接口

---

## 1. 项目定位

这个项目的目标不是做一个简单聊天机器人，而是实现一个具备 **感知 - 决策 - 行动** 闭环能力的最小电商 Agent。

它可以处理类似这样的复合任务：

> 帮我查一下订单 1001 的物流，并判断现在还能不能改地址

系统会自动完成：

1.  调用物流工具查询订单状态
2.  调用知识库检索相关规则
3.  整合多步结果，生成最终回答

---

## 2. 技术栈

* Python
* FastAPI
* Uvicorn
* Gemini API
* Pydantic
* 本地轻量检索（JSON knowledge base + keyword retrieval）

---

## 3. 项目结构

```text
ecommerce-agent/
├─ app/
│  ├─ agent/
│  │  ├─ core.py
│  │  ├─ planner.py
│  │  └─ safety.py
│  ├─ data/
│  │  └─ knowledge_base.json
│  ├─ services/
│  │  ├─ memory.py
│  │  ├─ registry.py
│  │  └─ retriever.py
│  ├─ tools/
│  │  ├─ base.py
│  │  ├─ logistics.py
│  │  ├─ order.py
│  │  └─ kb.py
│  ├─ utils/
│  │  └─ logger.py
│  ├─ main.py
│  └─ schemas.py
├─ .dockerignore
├─ Dockerfile
├─ requirements.txt
└─ README.md
```

**目录职责说明：**
* **agent/**：Agent 主循环、Planner、安全控制
* **tools/**：工具定义与具体实现
* **services/**：检索、上下文压缩、工具注册
* **data/**：知识库数据
* **utils/**：日志等通用能力
* **main.py**：FastAPI 服务入口

---

## 4. 核心能力说明

### 4.1 ReAct 风格多步执行
系统不是单轮问答，而是按多步方式执行：
1.  planner 决策下一步 action
2.  调用工具执行
3.  将 observation 返回给 planner
4.  planner 再决定下一步
5.  直到 finish

### 4.2 Tool Schema 标准化
每个工具都暴露统一定义：
* name
* description
* input_schema
* output_schema
* examples

这使得：
* LLM 更稳定地调用工具
* `/tools` 接口可直接暴露工具能力
* 后续 Android / Web 前端可动态读取能力注册表

### 4.3 轻量 RAG 检索层
知识库不再是简单 dict 匹配，而是升级为：
* 独立 `knowledge_base.json`
* 检索服务 `retriever.py`
* 关键词召回
* top-k 返回
* score 打分
* evidence 证据片段

这使系统具备了最小可用的 RAG 形态，后续可以进一步升级到 embedding 和向量检索。

### 4.4 上下文压缩
为了避免多步任务中 prompt 长度不断膨胀，系统加入了上下文压缩：
* 最近 2~3 步保留完整细节
* 更早步骤转为摘要
* planner 使用压缩后的上下文做决策

### 4.5 安全控制
系统加入了基础安全边界：
* Max-Step 限制
* 循环检测
* 工具异常捕获
* 错误 observation 回传 planner

### 4.6 结构化日志
系统将业务 trace 和工程日志分开：
* 业务层：steps
* 工程层：JSON 结构化日志

日志中包含：
* request_id
* trace_id
* step
* action
* action_input
* observation_success
* latency_ms
* stop_reason

便于后续问题排查、性能分析、云端部署观测以及 CI/CD smoke test 调试。

---

## 5. 环境要求

建议环境：
* Python 3.10+
* Windows / macOS / Linux
* 可选：Gemini API Key

---

## 6. 环境变量

使用 Gemini 时需要配置：
```bash
GEMINI_API_KEY=your_gemini_api_key
```

可选模型配置：
```bash
GEMINI_MODEL=gemini-2.5-flash
```
*如果没有配置 Gemini API，系统会自动回退到内置 MockPlanner。*

---

## 7. 安装依赖

```bash
pip install -r requirements.txt
```

---

## 8. 本地启动

在项目根目录运行：
```bash
uvicorn app.main:app --reload
```

启动后访问：
* 根路径：[http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* Swagger 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 9. API 接口

### 9.1 GET `/`
服务首页。

**示例响应：**
```json
{
  "message": "Minimal E-commerce Agent is running.",
  "available_endpoints": [
    "/run_task",
    "/health",
    "/tools"
  ]
}
```

### 9.2 GET `/health`
健康检查接口。
用于 Docker 健康检查、EC2 部署验证、GitHub Actions smoke test、Kubernetes readiness / liveness probe。

**示例响应：**
```json
{
  "status": "ok",
  "service": "minimal-ecommerce-agent",
  "version": "0.1.0"
}
```

### 9.3 GET `/tools`
返回当前系统已注册工具及其 schema。

**示例响应：**
```json
{
  "count": 3,
  "tools": [
    {
      "name": "query_logistics",
      "description": "Query logistics status and tracking number by order_id.",
      "input_schema": {
        "type": "object",
        "properties": {
          "order_id": {
            "type": "string",
            "description": "Order ID, such as 1001"
          }
        },
        "required": ["order_id"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "order_id": { "type": "string" },
          "status": { "type": "string" },
          "tracking_no": { "type": "string" }
        }
      },
      "examples": [
        {
          "input": { "order_id": "1001" },
          "description": "Query current logistics info of an order"
        }
      ]
    }
  ]
}
```

### 9.4 POST `/run_task`
执行用户任务。

**请求体：**
```json
{
  "user_input": "帮我查一下订单1001的物流，并判断现在还能不能改地址"
}
```

**示例响应：**
```json
{
  "status": "success",
  "final_answer": "订单 1001 的物流状态是：运输中，运单号：SF123456。另外，根据知识库规则：通常订单发货后不支持直接修改收货地址。若物流尚未完成派送，可尝试联系物流公司或客服协助处理，但不能保证修改成功。",
  "steps": [
    {
      "step": 1,
      "thought": "[call_tool] 这是一个复合任务，先查物流状态。",
      "action": "query_logistics",
      "action_input": {
        "order_id": "1001"
      },
      "observation": {
        "success": true,
        "data": {
          "order_id": "1001",
          "status": "运输中",
          "tracking_no": "SF123456"
        },
        "error": null,
        "suggestion": null,
        "tool_name": "query_logistics"
      }
    },
    {
      "step": 2,
      "thought": "[switch_tool] 物流信息已拿到，继续查询发货后修改地址规则。",
      "action": "query_kb",
      "action_input": {
        "query": "发货后修改地址",
        "top_k": 3
      },
      "observation": {
        "success": true,
        "data": {
          "query": "发货后修改地址",
          "query_tokens": [
            "发货后修改地址",
            "发货",
            "地址",
            "修改"
          ],
          "top_k": 3,
          "results": []
        },
        "error": null,
        "suggestion": null,
        "tool_name": "query_kb"
      }
    }
  ],
  "stop_reason": "planner_finish:finish"
}
```

---

## 10. 典型任务示例

**示例 1：查询物流**
```json
{
  "user_input": "帮我查一下订单1001的物流"
}
```

**示例 2：修改未发货订单地址**
```json
{
  "user_input": "帮我把订单1003的地址改成上海市闵行区XX路88号"
}
```

**示例 3：查询退款规则**
```json
{
  "user_input": "退款规则是什么"
}
```

**示例 4：复合任务**
```json
{
  "user_input": "帮我查一下订单1001的物流，并判断现在还能不能改地址"
}
```

---

## 11. Docker 启动

**构建镜像：**
```bash
docker build -t ecommerce-agent:latest .
```

**运行容器：**
```bash
docker run -d -p 8000:8000 --name ecommerce-agent \
  -e GEMINI_API_KEY=your_gemini_api_key \
  ecommerce-agent:latest
```

启动后访问：
* [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 12. 日志说明

服务运行时会输出 JSON 结构化日志，例如：
```json
{
  "timestamp": "2026-04-11T10:14:18.848727Z",
  "level": "INFO",
  "logger": "ecommerce_agent",
  "message": "tool_execution_completed",
  "request_id": "req_6917a10e58e9",
  "trace_id": "trace_s2_63637e67",
  "step": 2,
  "action": "query_kb",
  "action_input": {
    "query": "发货后修改地址",
    "top_k": 3
  },
  "observation_success": true,
  "error": null,
  "latency_ms": 1.78
}
```

---

## 13. 当前已完成的工程能力

* FastAPI 服务化
* 多工具 ReAct 执行链
* Tool Schema 标准化
* 轻量 RAG 检索层
* 上下文压缩
* Max-Step 与循环检测
* 结构化日志
* `/health`
* `/tools`

---

## 14. 后续扩展方向

### 14.1 云部署
* 部署到 AWS EC2
* 基于 Docker 运行服务
* 使用安全组开放 API 端口

### 14.2 CI/CD
* GitHub Actions 自动测试
* 自动构建 Docker 镜像
* 自动部署到 EC2

### 14.3 Android 客户端
* Kotlin + Jetpack Compose
* 通过 HTTP 调用 `/run_task`
* 展示 final answer 和 steps trace

### 14.4 Kubernetes
* 编写 `deployment.yaml` / `service.yaml`
* 基于 `/health` 做 readiness / liveness probe
* 后续扩展副本数与滚动更新

### 14.5 更正式的 RAG
* 引入 embedding
* 向量检索
* rerank
* 外部知识库管理

### 14.6 可观测性
* 请求级链路追踪
* 访问统计
* 指标上报
* 监控面板
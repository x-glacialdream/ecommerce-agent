# Business Ops AI Agent

该项目最初以电商 Agent 原型启动，后续逐步抽象并扩展为面向企业内部业务场景的多工具 AI Agent 平台，当前主要覆盖销售分析、异常预警、报销审核与内部知识检索等场景。

---

## 1. 项目定位

本项目的目标不是做一个“会聊天”的通用助手，而是做一个可落地的 **企业内部数智化 AI Agent**。

系统聚焦以下典型业务问题：

- 帮我分析最近 30 天各区域销量表现
- 帮我看看最近哪些区域-产品线组合出现异常波动
- 帮我检查这批报销记录里有哪些异常项
- 帮我看看最近哪些异常，再结合制度给出处理建议

与普通问答不同，这类任务通常需要：

1. 先识别任务类型
2. 选择合适工具
3. 调用数据分析 / 规则审核 / 知识检索能力
4. 基于 observation 继续下一步
5. 最终整合为对业务可读的结论

因此项目采用 **ReAct 风格的多步执行链路**，而不是单轮直接生成答案。

---

## 2. 项目当前能力

当前系统已经具备以下能力：

- FastAPI 服务化接口
- 多工具 Agent 主循环
- 规则 Planner + LLM Planner 双路径
- 销售分析工具 `query_sales_insight`
- 业务异常检测工具 `detect_business_anomaly`
- 报销审核工具 `audit_expense`
- 内部知识检索工具 `query_internal_kb`
- 结构化 Tool Schema
- 更正式的 RAG embedding 检索链路
- 关键词检索降级回退机制
- 上下文压缩
- Max-Step 与循环检测
- request_id / trace_id
- 结构化 JSON 日志
- 基础 metrics 统计与访问结果统计
- Docker 容器化
- AWS EC2 部署
- GitHub Actions 自动部署
- Android 最小客户端接入
- Kubernetes 基础配置

---

## 3. 典型任务示例

### 示例 1：销售分析

> 帮我分析最近30天各区域销量表现

系统会：

1. 识别为销售分析任务
2. 调用 `query_sales_insight`
3. 返回各区域核心表现、top groups 与摘要

---

### 示例 2：异常预警

> 帮我看看最近哪些销量异常下滑

系统会：

1. 识别为异常检测任务
2. 调用 `detect_business_anomaly`
3. 返回异常对象、偏离比例、严重程度和建议动作

---

### 示例 3：报销审核

> 帮我检查这批报销单有哪些异常

系统会：

1. 识别为财务审核任务
2. 调用 `audit_expense`
3. 标记超限、重复发票、日期异常、缺失字段等问题

---

### 示例 4：复合任务

> 帮我看看最近哪些异常，再结合制度给出处理建议

系统会：

1. 先调用 `detect_business_anomaly`
2. 再调用 `query_internal_kb`
3. 将异常结果与制度依据合并为最终回答

---

## 4. 技术栈

### 后端

- Python
- FastAPI
- Uvicorn
- Pydantic
- Pandas

### Agent / AI

- ReAct-style multi-step orchestration
- Gemini API（可选）
- MockPlanner（降级路径）
- LlamaIndex
- HuggingFace Embedding
- 关键词检索 + embedding 检索双路径

### 工程化

- Docker
- AWS EC2
- GitHub Actions
- Kubernetes 基础 YAML

### 客户端

- Kotlin
- Jetpack Compose
- Retrofit

---

## 5. 项目结构

```text
ecommerce-agent/
├─ .github/
│  └─ workflows/
│     └─ deploy.yml
├─ android/
│  └─ EcommerceAgentApp/
├─ app/
│  ├─ agent/
│  │  ├─ core.py
│  │  ├─ planner.py
│  │  └─ safety.py
│  ├─ data/
│  │  ├─ knowledge_base.json
│  │  ├─ sales_data.csv
│  │  └─ expense_data.csv
│  ├─ services/
│  │  ├─ llamaindex_retriever.py
│  │  ├─ memory.py
│  │  ├─ metrics.py
│  │  ├─ registry.py
│  │  └─ retriever.py
│  ├─ tools/
│  │  ├─ anomaly.py
│  │  ├─ base.py
│  │  ├─ expense_audit.py
│  │  ├─ kb.py
│  │  └─ sales_insight.py
│  ├─ utils/
│  │  └─ logger.py
│  ├─ main.py
│  └─ schemas.py
├─ scripts/
│  ├─ generate_expense_data.py
│  └─ generate_sales_data.py
├─ k8s/
│  ├─ deployment.yaml
│  └─ service.yaml
├─ .dockerignore
├─ .gitignore
├─ Dockerfile
├─ README.md
└─ requirements.txt
```

---

## 6. 核心设计说明

### 6.1 Agent 主循环

核心执行逻辑位于 Agent 主循环中。系统不会在收到请求后直接输出答案，而是先把：

- 用户输入

- 历史步骤

- 压缩后的上下文

- 最近一次 observation

一起交给 planner 决策下一步 action。

每次决策后：

1. 通过 ToolRegistry 找到目标工具

2. 调用工具执行

3. 将 observation 记录到 step trace

4. 再交回 planner 做下一步决策

5. 直到 `finish`

---

### 6.2 Tool Schema 标准化

每个工具都遵循统一结构：

- `name`

- `description`

- `input_schema`

- `output_schema`

- `examples`

统一返回格式：

```json
{
  "success": true,
  "data": {},
  "error": null,
  "suggestion": null,
  "tool_name": "query_sales_insight",
  "summary": "..."
}
```

这使得：

- Planner 更容易稳定调用工具

- `/tools` 接口可以自动暴露工具定义

- 新工具后续更容易扩展

---

### 6.3 销售分析工具

`sales_insight.py` 面向销售与经营分析场景，支持：

- 按区域分析

- 按产品线分析

- 时间范围分析

- 结构化 top groups 输出

- 自动摘要生成

支持字段包括：

- `sales_amount`

- `quantity`

- `region`

- `product_line`

---

### 6.4 异常检测工具

`anomaly.py` 面向经营异常识别，支持：

- `region`

- `product_line`

- `region_product_line`

三个粒度的异常分析。

为了避免异常被粗粒度聚合摊平，工具支持 **区域-产品线组合粒度** 检测，并使用：

- recent daily average

- baseline daily average

- deviation ratio

- severity

- suggested action

输出结构化异常结果。

---

### 6.5 报销审核工具

`expense_audit.py` 面向内部财务审核场景，支持识别：

- 金额超限

- 重复发票号

- 疑似重复报销

- 日期异常

- 缺失字段

并输出：

- `flagged_items`

- `issue_list`

- `risk_level`

- `summary`

该模块体现了“规则优先，模型辅助”的设计思路。

---

### 6.6 更正式的 RAG embedding 检索

知识检索部分采用两层设计：

#### 第一层：LlamaIndex + Embedding

- 基于 `knowledge_base.json` 构建向量索引

- 使用 HuggingFace Embedding

- 支持持久化索引

- 支持索引自动重建

- 支持按文档 ID 去重，避免重复 chunk 返回

#### 第二层：SimpleRetriever 关键词检索降级

- 当 embedding 检索不可用或失败时

- 自动回退到关键词检索

- 仍能返回 top-k、score、evidence

这使系统具备了更正式的 RAG 形态，而不只是简单 FAQ 匹配。

---

### 6.7 上下文压缩

为了控制多步任务中的上下文膨胀，系统会：

- 保留最近几步的完整细节

- 将更早步骤压缩成摘要

- 将压缩结果传入 planner

这能在多步任务中保持上下文可用性，同时控制 prompt 规模。

---

### 6.8 安全边界

系统加入了基础安全控制：

- Max-Step 限制

- 循环检测

- 工具异常捕获

- observation 回传

- Planner 决策闭环控制

避免 Agent 在复杂任务中无限循环。

---

## 7. 简单监控 / 访问日志统计

项目目前实现了轻量级可观测性能力，主要包括两部分：

### 7.1 结构化访问日志

系统会输出 JSON 结构化日志，包含：

- `request_id`

- `trace_id`

- `step`

- `action`

- `action_input`

- `observation_success`

- `latency_ms`

- `stop_reason`

这使得每次请求、每一步工具调用都可追踪。

---

### 7.2 基础 metrics 统计

系统提供 `/metrics` 接口，用于暴露基础请求统计信息，包括：

- 请求总数

- 成功 / 失败请求数

- 工具调用次数

- 请求耗时分布

- action 计数

虽然目前还不是 Prometheus / Grafana 级别的正式监控体系，但已经具备了：

- 访问日志统计

- 工具级调用统计

- 请求级耗时观测

能够支撑本地调试、接口验收和最小部署观测。

---

## 8. 环境要求

建议环境：

- Python 3.10+

- Windows / macOS / Linux

- Docker Desktop（容器化时）

- Android Studio（客户端开发时）

- 可选：Gemini API Key

---

## 9. 环境变量

```bash
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
```

如果未配置 Gemini，系统会自动回退到内置 `MockPlanner`。

---

## 10. 安装依赖

```bash
pip install -r requirements.txt
```

---

## 11. 生成模拟数据

项目提供了两个数据生成脚本：

```bash
python scripts/generate_sales_data.py
python scripts/generate_expense_data.py
```

会生成：

- `app/data/sales_data.csv`

- `app/data/expense_data.csv`

用于本地演示销售分析、异常检测和报销审核。

---

## 12. 本地启动

```bash
uvicorn app.main:app --reload
```

启动后可访问：

- `http://127.0.0.1:8000/`

- `http://127.0.0.1:8000/docs`

- `http://127.0.0.1:8000/health`

- `http://127.0.0.1:8000/tools`

- `http://127.0.0.1:8000/metrics`

---

## 13. API 说明

### GET `/`

服务首页。

### GET `/health`

健康检查接口。

### GET `/tools`

返回当前已注册工具及其 schema。

### GET `/metrics`

返回基础监控统计信息。

### POST `/run_task`

执行业务任务。

示例请求：

```json
{
  "user_input": "帮我看看最近哪些异常，再结合制度给出处理建议"
}
```

---

## 14. 典型测试输入

### 销售分析

```json
{
  "user_input": "帮我分析最近30天各区域销量表现"
}
```

### 异常检测

```json
{
  "user_input": "帮我看看最近哪些异常"
}
```

### 报销审核

```json
{
  "user_input": "帮我检查这批报销单有哪些异常"
}
```

### 知识检索

```json
{
  "user_input": "差旅报销超过标准怎么处理"
}
```

### 复合任务

```json
{
  "user_input": "帮我看看最近哪些异常，再结合制度给出处理建议"
}
```

---

## 15. Docker 启动

构建镜像：

```bash
docker build -t business-ops-ai-agent:latest .
```

运行容器：

```bash
docker run -d -p 8000:8000 --name business-ops-ai-agent \
  -e GEMINI_API_KEY=your_gemini_api_key \
  -e GEMINI_MODEL=gemini-2.5-flash \
  business-ops-ai-agent:latest
```

---

## 16. AWS EC2 / GitHub Actions / Kubernetes

### EC2

项目已完成云端部署验证，可在 EC2 上通过 Docker 运行。

### GitHub Actions

项目已补充自动化部署流程，可在代码提交后执行构建与发布。

### Kubernetes

项目包含基础配置：

```text
k8s/deployment.yaml
k8s/service.yaml
```

支持：

- Deployment

- Service

- `/health` 作为健康检查入口

---

## 17. Android 最小客户端

项目已补充最小 Android 客户端，用于验证：

- 移动端可调用云端 Agent 接口

- 服务端返回结果可在客户端展示

- `steps` 执行链路不是黑盒

当前客户端能力包括：

- 输入任务

- 调用 `/run_task`

- 展示 `final_answer`

- 展示 `steps`

---

## 18. 当前仍可继续补强的方向

当前版本已满足本地演示、服务部署、接口测试和多步任务验证需求。如果继续往更正式的企业应用推进，下一步可以补这些：

### 18.1 更正式的监控

- Prometheus 指标导出

- Grafana 可视化看板

- 更细粒度的 tool latency 分析

### 18.2 更强的 RAG

- rerank

- metadata filtering

- 权限型检索

- 文档版本控制

### 18.3 更强的规则引擎

- 报销审核规则配置化

- 异常策略配置化

- 审核规则热更新

### 18.4 更真实的数据接入

- 从数据库 / API 拉取真实业务数据

- 替代当前模拟 CSV 数据

### 18.5 更完整前端

- Web 管理页

- 看板页面

- 历史任务记录

- 报表导出

---

## 19. License

仅用于学习、实验、演示与面试展示。

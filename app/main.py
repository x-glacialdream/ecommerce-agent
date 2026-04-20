from fastapi import FastAPI

from app.schemas import TaskRequest, TaskResponse
from app.agent.core import BusinessOpsAgent
from app.services.registry import ToolRegistry
from app.services.metrics import metrics_collector

APP_TITLE = "Business Ops AI Agent"
APP_VERSION = "0.2.0"
APP_DESCRIPTION = (
    "A multi-tool business operations AI agent for sales analytics, anomaly detection, "
    "expense audit, and internal knowledge retrieval, with error handling, max-step control, "
    "loop detection, structured logging, and simple metrics."
)
SERVICE_NAME = "business-ops-ai-agent"

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)

agent = BusinessOpsAgent()
registry = ToolRegistry()


@app.get("/")
def root():
    return {
        "message": f"{APP_TITLE} is running.",
        "available_endpoints": [
            "/run_task",
            "/health",
            "/tools",
            "/metrics",
        ],
        "capabilities": [
            "sales_insight",
            "business_anomaly_detection",
            "expense_audit",
            "internal_knowledge_query",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": APP_VERSION,
    }


@app.get("/tools")
def list_tools():
    return {
        "count": len(registry.list_tools()),
        "tools": registry.list_tools(),
    }


@app.get("/metrics")
def metrics():
    return metrics_collector.snapshot()


@app.post("/run_task", response_model=TaskResponse)
def run_task(req: TaskRequest):
    return agent.run(req.user_input)
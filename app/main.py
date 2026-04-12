from fastapi import FastAPI
from app.schemas import TaskRequest, TaskResponse
from app.agent.core import EcommerceAgent
from app.services.registry import ToolRegistry

app = FastAPI(
    title="Minimal E-commerce Agent",
    version="0.1.0",
    description="A minimal multi-tool e-commerce agent with error handling, max-step control, loop detection, lightweight retrieval, and structured logging."
)

agent = EcommerceAgent()
registry = ToolRegistry()


@app.get("/")
def root():
    return {
        "message": "Minimal E-commerce Agent is running.",
        "available_endpoints": [
            "/run_task",
            "/health",
            "/tools"
        ]
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "minimal-ecommerce-agent",
        "version": "0.1.0"
    }


@app.get("/tools")
def list_tools():
    return {
        "count": len(registry.list_tools()),
        "tools": registry.list_tools()
    }


@app.post("/run_task", response_model=TaskResponse)
def run_task(req: TaskRequest):
    return agent.run(req.user_input)
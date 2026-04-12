from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    user_input: str = Field(..., description="User task input")


class ToolResult(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    suggestion: Optional[str] = None


class StepTrace(BaseModel):
    step: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Dict[str, Any]


class TaskResponse(BaseModel):
    status: str
    final_answer: str
    steps: List[StepTrace]
    stop_reason: str
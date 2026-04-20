from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseTool(ABC):
    """
    Standardized tool definition for agent tool-calling.

    Each tool should expose:
    - name
    - description
    - input_schema
    - output_schema
    - examples

    Unified return format:
    {
        "success": True/False,
        "data": {...},
        "error": "...",
        "suggestion": "...",
        "tool_name": "query_sales_insight",
        "summary": "human readable summary"
    }
    """

    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    examples: List[Dict[str, Any]] = []

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def get_definition(self) -> Dict[str, Any]:
        """
        Metadata used by registry, planner, /tools endpoint, and prompt building.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "examples": self.examples,
        }

    def ok(
        self,
        data: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "data": data or {},
            "error": None,
            "suggestion": None,
            "tool_name": self.name,
            "summary": summary,
        }

    def fail(
        self,
        error: str,
        suggestion: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "data": data,
            "error": error,
            "suggestion": suggestion,
            "tool_name": self.name,
            "summary": None,
        }

    def require_fields(self, payload: Dict[str, Any], required_fields: List[str]) -> Optional[Dict[str, Any]]:
        missing = [field for field in required_fields if payload.get(field) in (None, "", [], {})]
        if missing:
            return self.fail(
                error=f"Missing required parameters: {', '.join(missing)}",
                suggestion=f"Please provide the following fields: {', '.join(missing)}",
            )
        return None

    def to_float(self, value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def to_int(self, value: Any, default: int = 0) -> int:
        try:
            if value is None or value == "":
                return default
            return int(value)
        except (TypeError, ValueError):
            return default
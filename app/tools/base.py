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
    """

    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {}
    output_schema: Dict[str, Any] = {}
    examples: List[Dict[str, Any]] = []

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """
        Unified return format:
        {
            "success": True/False,
            "data": {...},
            "error": "...",
            "suggestion": "...",
            "tool_name": "query_logistics"
        }
        """
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

    def ok(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "success": True,
            "data": data or {},
            "error": None,
            "suggestion": None,
            "tool_name": self.name,
        }

    def fail(self, error: str, suggestion: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "data": None,
            "error": error,
            "suggestion": suggestion,
            "tool_name": self.name,
        }
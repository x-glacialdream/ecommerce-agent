from typing import Dict, List

from app.tools.anomaly import DetectBusinessAnomalyTool
from app.tools.base import BaseTool
from app.tools.expense_audit import ExpenseAuditTool
from app.tools.kb import QueryInternalKBTool
from app.tools.sales_insight import SalesInsightTool


class ToolRegistry:
    def __init__(self) -> None:
        self.tools: Dict[str, BaseTool] = {}
        self.register(SalesInsightTool())
        self.register(DetectBusinessAnomalyTool())
        self.register(ExpenseAuditTool())
        self.register(QueryInternalKBTool())

    def register(self, tool: BaseTool) -> None:
        self.tools[tool.name] = tool

    def get_tool(self, tool_name: str) -> BaseTool:
        if tool_name not in self.tools:
            raise ValueError(f"Tool not found: {tool_name}")
        return self.tools[tool_name]

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tools

    def list_tools(self) -> List[Dict[str, object]]:
        return [tool.get_definition() for tool in self.tools.values()]

    def get_tool_prompt_text(self) -> str:
        """
        Build a planner-friendly textual description for prompt injection.
        """
        lines = []
        for tool in self.tools.values():
            definition = tool.get_definition()
            lines.append(f"Tool: {definition['name']}")
            lines.append(f"Description: {definition['description']}")
            lines.append(f"Input Schema: {definition['input_schema']}")
            lines.append(f"Output Schema: {definition['output_schema']}")
            if definition["examples"]:
                lines.append(f"Examples: {definition['examples']}")
            lines.append("")
        return "\n".join(lines).strip()
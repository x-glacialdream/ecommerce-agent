from typing import Any, Dict
from app.tools.base import BaseTool
from app.services.retriever import SimpleRetriever


class QueryKBTool(BaseTool):
    name = "query_kb"
    description = "Query e-commerce policy and FAQ knowledge base by policy-related query."

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Policy or FAQ query, such as 发货后修改地址 or 退款规则"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top retrieved documents to return, default is 3"
            }
        },
        "required": ["query"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "query_tokens": {"type": "array"},
            "top_k": {"type": "integer"},
            "results": {"type": "array"}
        }
    }

    examples = [
        {
            "input": {"query": "发货后修改地址", "top_k": 3},
            "description": "Retrieve policy documents about modifying address after shipment"
        },
        {
            "input": {"query": "退款规则", "top_k": 2},
            "description": "Retrieve refund-related documents"
        }
    ]

    def __init__(self) -> None:
        self.retriever = SimpleRetriever()

    def run(self, **kwargs) -> Dict[str, Any]:
        query = str(kwargs.get("query", "")).strip()
        top_k = kwargs.get("top_k", 3)

        if not query:
            return self.fail(
                error="Missing required parameter: query",
                suggestion="Please provide a knowledge base query"
            )

        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 3

        top_k = max(1, min(top_k, 5))

        retrieved = self.retriever.search(query=query, top_k=top_k)

        if not retrieved["success"]:
            return self.fail(
                error=retrieved["error"],
                suggestion="Try using a more specific policy-related query"
            )

        return self.ok(
            data={
                "query": retrieved["query"],
                "query_tokens": retrieved["query_tokens"],
                "top_k": retrieved["top_k"],
                "results": retrieved["results"]
            }
        )
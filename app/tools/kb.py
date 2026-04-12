from typing import Any, Dict

from app.tools.base import BaseTool
from app.services.retriever import SimpleRetriever
from app.services.llamaindex_retriever import LlamaIndexRetriever


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
        self.llama_retriever = LlamaIndexRetriever()
        self.legacy_retriever = SimpleRetriever()

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

        # 先走 LlamaIndex embedding RAG
        try:
            retrieved = self.llama_retriever.search(query=query, top_k=top_k)

            if not retrieved["success"]:
                raise RuntimeError(retrieved.get("error", "Unknown LlamaIndex retrieval error"))

            return self.ok(
                data={
                    "query": retrieved["query"],
                    "query_tokens": retrieved["query_tokens"],
                    "top_k": retrieved["top_k"],
                    "results": retrieved["results"]
                }
            )

        # 如果 LlamaIndex 失败，再降级到旧版关键词检索
        except Exception as llama_error:
            try:
                retrieved = self.legacy_retriever.search(query=query, top_k=top_k)

                if not retrieved["success"]:
                    return self.fail(
                        error=retrieved["error"],
                        suggestion="Try using a more specific policy-related query"
                    )

                result = self.ok(
                    data={
                        "query": retrieved["query"],
                        "query_tokens": retrieved["query_tokens"],
                        "top_k": retrieved["top_k"],
                        "results": retrieved["results"]
                    }
                )
                result["suggestion"] = (
                    f"LlamaIndex retrieval failed, fallback to legacy retriever: {str(llama_error)}"
                )
                return result

            except Exception as legacy_error:
                return self.fail(
                    error=f"LlamaIndex failed: {str(llama_error)} | Legacy retriever failed: {str(legacy_error)}",
                    suggestion="Check embedding dependencies, knowledge base format, or retriever logic"
                )
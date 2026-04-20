from typing import Any, Dict

from app.tools.base import BaseTool
from app.services.retriever import SimpleRetriever
from app.services.llamaindex_retriever import LlamaIndexRetriever


class QueryInternalKBTool(BaseTool):
    name = "query_internal_kb"
    description = (
        "Query internal enterprise knowledge base, including policies, SOPs, reimbursement rules, "
        "sales handling guidelines, procurement processes, training materials, and product documents."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Knowledge query, such as 差旅报销制度, 区域销量异常处理规范, 招采流程说明"
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
            "summary": {"type": "string"},
            "query": {"type": "string"},
            "query_tokens": {"type": "array"},
            "top_k": {"type": "integer"},
            "results": {"type": "array"}
        }
    }

    examples = [
        {
            "input": {"query": "差旅报销制度", "top_k": 3},
            "description": "Retrieve reimbursement policy documents"
        },
        {
            "input": {"query": "区域销量异常处理规范", "top_k": 3},
            "description": "Retrieve anomaly handling guidelines for business operations"
        },
        {
            "input": {"query": "重点客户回访规则", "top_k": 2},
            "description": "Retrieve customer follow-up rules"
        },
        {
            "input": {"query": "招采流程说明", "top_k": 2},
            "description": "Retrieve procurement process documents"
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
                suggestion="Please provide a valid internal knowledge base query"
            )

        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 3

        top_k = max(1, min(top_k, 5))

        # First try LlamaIndex embedding retrieval
        try:
            retrieved = self.llama_retriever.search(query=query, top_k=top_k)

            if not retrieved["success"]:
                raise RuntimeError(retrieved.get("error", "Unknown LlamaIndex retrieval error"))

            results = retrieved.get("results", [])
            if results:
                first = results[0]
                title = first.get("title", "知识库结果")
                content = first.get("content", "未检索到明确内容。")
                summary = f"已完成内部知识库检索。当前最相关结果为《{title}》：{content}"
            else:
                summary = "已完成内部知识库检索，但未返回有效结果。"

            return self.ok(
                data={
                    "query": retrieved["query"],
                    "query_tokens": retrieved["query_tokens"],
                    "top_k": retrieved["top_k"],
                    "results": results,
                },
                summary=summary,
            )

        # Fallback to legacy keyword retriever if LlamaIndex fails
        except Exception as llama_error:
            try:
                retrieved = self.legacy_retriever.search(query=query, top_k=top_k)

                if not retrieved["success"]:
                    return self.fail(
                        error=retrieved["error"],
                        suggestion="Try using a more specific policy, SOP, or process-related query"
                    )

                results = retrieved.get("results", [])
                if results:
                    first = results[0]
                    title = first.get("title", "知识库结果")
                    content = first.get("content", "未检索到明确内容。")
                    summary = f"已完成内部知识库检索。当前最相关结果为《{title}》：{content}"
                else:
                    summary = "已完成内部知识库检索，但未返回有效结果。"

                result = self.ok(
                    data={
                        "query": retrieved["query"],
                        "query_tokens": retrieved["query_tokens"],
                        "top_k": retrieved["top_k"],
                        "results": results,
                    },
                    summary=summary,
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
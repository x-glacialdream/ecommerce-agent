import json
import re
from pathlib import Path
from typing import Any, Dict, List


class SimpleRetriever:
    """
    Lightweight retrieval layer for policy / FAQ search.

    Features:
    - JSON knowledge base loading
    - keyword recall
    - top-k ranking
    - score
    - evidence extraction
    """

    def __init__(self, kb_path: str = "app/data/knowledge_base.json") -> None:
        self.kb_path = Path(kb_path)
        self.documents = self._load_documents()

    def _load_documents(self) -> List[Dict[str, Any]]:
        if not self.kb_path.exists():
            raise FileNotFoundError(f"Knowledge base file not found: {self.kb_path}")

        with self.kb_path.open("r", encoding="utf-8") as f:
            docs = json.load(f)

        if not isinstance(docs, list):
            raise ValueError("Knowledge base JSON must be a list of documents")

        return docs

    def _tokenize(self, text: str) -> List[str]:
        """
        Very lightweight tokenizer for Chinese + English mixed text.
        Strategy:
        - split English words / numbers
        - keep Chinese chunks
        - also keep single useful keywords from known terms
        """
        text = (text or "").strip().lower()
        if not text:
            return []

        english_parts = re.findall(r"[a-zA-Z0-9_]+", text)
        chinese_parts = re.findall(r"[\u4e00-\u9fff]+", text)

        tokens: List[str] = []
        tokens.extend(english_parts)
        tokens.extend(chinese_parts)

        # simple keyword expansion for common policy queries
        extra_keywords = [
            "发货", "未发货", "已发货", "地址", "修改", "退款",
            "物流", "异常", "签收", "售后", "客服", "订单"
        ]
        for kw in extra_keywords:
            if kw in text:
                tokens.append(kw)

        # deduplicate while preserving order
        seen = set()
        result = []
        for token in tokens:
            if token and token not in seen:
                seen.add(token)
                result.append(token)
        return result

    def _score_document(self, query_tokens: List[str], doc: Dict[str, Any]) -> Dict[str, Any]:
        title = str(doc.get("title", ""))
        content = str(doc.get("content", ""))
        tags = doc.get("tags", []) or []

        score = 0.0
        matched_terms: List[str] = []

        for token in query_tokens:
            token_score = 0.0

            if token in title:
                token_score += 3.0
            if token in content:
                token_score += 2.0
            if any(token in str(tag) for tag in tags):
                token_score += 2.5

            if token_score > 0:
                matched_terms.append(token)
                score += token_score

        return {
            "doc": doc,
            "score": round(score, 2),
            "matched_terms": matched_terms
        }

    def _build_evidence(self, doc: Dict[str, Any], matched_terms: List[str]) -> str:
        content = str(doc.get("content", ""))
        if not content:
            return ""

        for term in matched_terms:
            idx = content.find(term)
            if idx != -1:
                start = max(0, idx - 18)
                end = min(len(content), idx + len(term) + 28)
                return content[start:end]

        return content[:60]

    def search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        query = (query or "").strip()
        if not query:
            return {
                "success": False,
                "query": query,
                "results": [],
                "error": "Empty query"
            }

        query_tokens = self._tokenize(query)
        scored_results = []

        for doc in self.documents:
            scored = self._score_document(query_tokens, doc)
            if scored["score"] > 0:
                evidence = self._build_evidence(scored["doc"], scored["matched_terms"])
                scored_results.append({
                    "id": scored["doc"].get("id"),
                    "title": scored["doc"].get("title"),
                    "content": scored["doc"].get("content"),
                    "tags": scored["doc"].get("tags", []),
                    "score": scored["score"],
                    "matched_terms": scored["matched_terms"],
                    "evidence": evidence
                })

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        top_results = scored_results[:top_k]

        return {
            "success": len(top_results) > 0,
            "query": query,
            "query_tokens": query_tokens,
            "top_k": top_k,
            "results": top_results,
            "error": None if top_results else f"No relevant knowledge found for query: {query}"
        }
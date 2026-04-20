import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from llama_index.core import (
    Document,
    Settings,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


class LlamaIndexRetriever:
    def __init__(
        self,
        kb_path: str = "app/data/knowledge_base.json",
        persist_dir: str = "app/data/llamaindex_storage",
        embedding_model_name: str = "BAAI/bge-m3",
        similarity_top_k: int = 3,
    ) -> None:
        self.kb_path = Path(kb_path)
        self.persist_dir = Path(persist_dir)
        self.embedding_model_name = embedding_model_name
        self.similarity_top_k = similarity_top_k
        self.meta_path = self.persist_dir / "kb_meta.json"

        self.embed_model = HuggingFaceEmbedding(model_name=self.embedding_model_name)

        self.text_splitter = SentenceSplitter(
            chunk_size=256,
            chunk_overlap=32,
        )

        Settings.embed_model = self.embed_model
        Settings.text_splitter = self.text_splitter

        self.raw_docs = self._load_kb()
        self.current_kb_hash = self._compute_kb_hash(self.raw_docs)
        self.index = self._load_or_build_index()

    def _load_kb(self) -> List[Dict[str, Any]]:
        if not self.kb_path.exists():
            raise FileNotFoundError(f"Knowledge base file not found: {self.kb_path}")

        with open(self.kb_path, "r", encoding="utf-8") as f:
            rows = json.load(f)

        if not isinstance(rows, list):
            raise ValueError("knowledge_base.json must be a list of documents")

        return rows

    def _compute_kb_hash(self, rows: List[Dict[str, Any]]) -> str:
        canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(canonical.encode("utf-8")).hexdigest()

    def _load_meta(self) -> Dict[str, Any]:
        if not self.meta_path.exists():
            return {}
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_meta(self) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "kb_hash": self.current_kb_hash,
            "kb_path": str(self.kb_path),
            "embedding_model_name": self.embedding_model_name,
        }
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def _should_rebuild_index(self) -> bool:
        if not self.persist_dir.exists():
            return True

        if not any(self.persist_dir.iterdir()):
            return True

        meta = self._load_meta()
        stored_hash = meta.get("kb_hash")
        stored_model = meta.get("embedding_model_name")

        if not stored_hash:
            return True

        if stored_hash != self.current_kb_hash:
            return True

        if stored_model != self.embedding_model_name:
            return True

        return False

    def _clear_persist_dir(self) -> None:
        if self.persist_dir.exists():
            shutil.rmtree(self.persist_dir)

    def _build_documents(self, rows: List[Dict[str, Any]]) -> List[Document]:
        docs: List[Document] = []

        for row in rows:
            doc_id = row.get("id", "")
            title = row.get("title", "")
            content = row.get("content", "")
            tags = row.get("tags", [])

            tags_text = " ".join(tags)

            text = (
                f"规则标题：{title}\n"
                f"规则标签：{tags_text}\n"
                f"规则编号：{doc_id}\n"
                f"规则内容：{content}\n"
                f"主题总结：{title}；标签：{tags_text}"
            )

            docs.append(
                Document(
                    text=text,
                    metadata={
                        "id": doc_id,
                        "title": title,
                        "content": content,
                        "tags": tags,
                    },
                )
            )

        return docs

    def _build_index(self) -> VectorStoreIndex:
        documents = self._build_documents(self.raw_docs)
        index = VectorStoreIndex.from_documents(
            documents,
            embed_model=self.embed_model,
            transformations=[self.text_splitter],
        )

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(self.persist_dir))
        self._save_meta()
        return index

    def _load_or_build_index(self) -> VectorStoreIndex:
        if self._should_rebuild_index():
            self._clear_persist_dir()
            return self._build_index()

        storage_context = StorageContext.from_defaults(
            persist_dir=str(self.persist_dir)
        )
        return load_index_from_storage(storage_context)

    def rebuild_index(self) -> None:
        self.raw_docs = self._load_kb()
        self.current_kb_hash = self._compute_kb_hash(self.raw_docs)
        self._clear_persist_dir()
        self.index = self._build_index()

    def search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        top_k = max(1, min(int(top_k), 5))
        # 先多取一些，再按文档 id 去重
        retriever = self.index.as_retriever(similarity_top_k=max(top_k * 3, 6))
        nodes = retriever.retrieve(query)

        best_by_id: Dict[str, Dict[str, Any]] = {}

        for node in nodes:
            md = node.metadata or {}
            content = md.get("content", "")
            score = float(getattr(node, "score", 0.0) or 0.0)
            evidence = content[:100] if content else node.text[:100]

            doc_id = str(md.get("id") or "")
            if not doc_id:
                doc_id = f"unknown::{md.get('title', '')}"

            candidate = {
                "id": md.get("id"),
                "title": md.get("title"),
                "content": content,
                "tags": md.get("tags", []),
                "score": score,
                "matched_terms": [],
                "evidence": evidence,
            }

            existing = best_by_id.get(doc_id)
            if existing is None or candidate["score"] > existing["score"]:
                best_by_id[doc_id] = candidate

        results = sorted(
            best_by_id.values(),
            key=lambda x: x["score"],
            reverse=True,
        )[:top_k]

        return {
            "success": len(results) > 0,
            "query": query,
            "query_tokens": [],
            "top_k": top_k,
            "results": results,
            "error": None if results else f"No relevant knowledge found for query: {query}",
        }
import json
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

        # 1) embedding 模型
        self.embed_model = HuggingFaceEmbedding(model_name=self.embedding_model_name)

        # 2) 轻量 chunking 策略
        # chunk_size / overlap 不用太激进，当前知识库很小
        self.text_splitter = SentenceSplitter(
            chunk_size=256,
            chunk_overlap=32,
        )

        # 3) 全局设置
        Settings.embed_model = self.embed_model
        Settings.text_splitter = self.text_splitter

        # 4) 加载知识库原始数据
        self.raw_docs = self._load_kb()

        # 5) 加载或构建索引
        self.index = self._load_or_build_index()

    def _load_kb(self) -> List[Dict[str, Any]]:
        with open(self.kb_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_documents(self, rows: List[Dict[str, Any]]) -> List[Document]:
        """
        metadata 利用：
        - title
        - tags
        - id
        - 原始 content

        文本构造策略：
        - 强化标题
        - 强化标签
        - 保留正文
        - 用统一模板让 embedding 更容易抓住语义重点
        """
        docs: List[Document] = []

        for row in rows:
            doc_id = row.get("id", "")
            title = row.get("title", "")
            content = row.get("content", "")
            tags = row.get("tags", [])

            tags_text = " ".join(tags)

            # metadata 加权：标题和标签显式写进正文，帮助 embedding 捕捉主题
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

    def _load_or_build_index(self) -> VectorStoreIndex:
        """
        持久化索引：
        - 如果本地 persist_dir 已存在索引，直接加载
        - 否则从 knowledge_base.json 构建并持久化
        """
        if self.persist_dir.exists() and any(self.persist_dir.iterdir()):
            storage_context = StorageContext.from_defaults(
                persist_dir=str(self.persist_dir)
            )
            return load_index_from_storage(storage_context)

        documents = self._build_documents(self.raw_docs)
        index = VectorStoreIndex.from_documents(
            documents,
            embed_model=self.embed_model,
            transformations=[self.text_splitter],
        )

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(self.persist_dir))
        return index

    def rebuild_index(self) -> None:
        """
        当 knowledge_base.json 更新后，可以手动重建索引。
        """
        self.raw_docs = self._load_kb()
        documents = self._build_documents(self.raw_docs)

        index = VectorStoreIndex.from_documents(
            documents,
            embed_model=self.embed_model,
            transformations=[self.text_splitter],
        )

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        index.storage_context.persist(persist_dir=str(self.persist_dir))
        self.index = index

    def search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        返回结构尽量兼容你现在的 query_kb。
        """
        top_k = max(1, min(int(top_k), 5))
        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)

        results: List[Dict[str, Any]] = []
        for node in nodes:
            md = node.metadata or {}
            content = md.get("content", "")
            score = float(getattr(node, "score", 0.0) or 0.0)

            # evidence 优先截正文，避免把拼接模板整段暴露出去
            evidence = content[:100] if content else node.text[:100]

            results.append(
                {
                    "id": md.get("id"),
                    "title": md.get("title"),
                    "content": content,
                    "tags": md.get("tags", []),
                    "score": score,
                    "matched_terms": [],
                    "evidence": evidence,
                }
            )

        return {
            "success": True,
            "query": query,
            "query_tokens": [],
            "top_k": top_k,
            "results": results,
            "error": None,
        }
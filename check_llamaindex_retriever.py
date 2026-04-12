from app.services.llamaindex_retriever import LlamaIndexRetriever

retriever = LlamaIndexRetriever()

queries = [
    "发货后还能改地址吗",
    "退款规则是什么",
    "物流异常怎么办",
]

for q in queries:
    print("=" * 80)
    print("QUERY:", q)
    result = retriever.search(q, top_k=3)
    print(result)
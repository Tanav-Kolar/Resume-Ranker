HYDE_PROFILES = [
    {"name": "search_ranking_specialist", "weight": 0.35, "text":
     "Senior ML engineer with ~7 years focused on search, retrieval, and ranking in "
     "production. Designed and shipped a hybrid retrieval system combining BM25 with dense "
     "vector recall (sentence-transformers + FAISS) serving tens of millions of queries at "
     "sub-200ms p95. Built a learning-to-rank layer and ran it in A/B tests against the "
     "legacy scorer, tracking NDCG and click-through in an offline-to-online eval harness."},
    {"name": "recsys_to_retrieval", "weight": 0.25, "text":
     "Applied ML engineer, ~6 years, recommendation systems background now working on "
     "embedding-based retrieval at a product company. Built a production recommender "
     "(matrix factorization + content embeddings + candidate ranking) serving 10M+ users, "
     "then migrated discovery from keyword search to dense retrieval with an ANN index "
     "(Milvus/Pinecone). Owned relevance metrics and A/B experiments for the ranking models."},
    {"name": "applied_scientist_who_ships", "weight": 0.22, "text":
     "Product-minded ML engineer, ~6-8 years, ships end to end from experimentation to "
     "deployment. Built a RAG feature over an internal corpus (sentence-transformers "
     "embeddings, FAISS, LLM re-ranker) and owned its eval framework. Fine-tuned embedding "
     "and language models (LoRA/PEFT) for domain retrieval and drove the offline/online "
     "evaluation that decided what shipped. Strong Python."},
    {"name": "title_undersells_backend", "weight": 0.18, "text":
     "Senior software/data engineer, ~5-6 years at product companies, who quietly built the "
     "search and recommendation systems behind the product. Implemented semantic search over "
     "hundreds of thousands of documents (bge embeddings + vector store) and the ranking that "
     "ordered results. Built the retrieval infrastructure — indexing, embedding refresh, "
     "relevance evaluation — even though my title just says 'Software Engineer'."},
]

AGG_MODE = "max"  # HyDE: archetypes are alternative personas -> max over archetypes

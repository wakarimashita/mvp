Формулировка для презентации / README
AEGIS provides a hybrid retrieval service combining Qdrant semantic vector search and BM25 keyword search, fused through Reciprocal Rank Fusion. The service applies lightweight schema-aware reranking using explicit asset identifiers, document type, document status, and source authority.

The local pipeline implements the same Bronze/Silver/Gold transformations. A Fabric Pipeline deployment definition maps these stages to scheduled Lakehouse notebook activities.

In a benchmark of 20 representative enterprise queries executed three times each (60 measured runs) over 1,000 retrieval-ready document chunks, AEGIS achieved 100% Top-1 retrieval accuracy and 108.95 ms p95 end-to-end retrieval latency. This exceeds the sub-second p95 latency requirement.

Формулировка покороче для слайда
Hybrid retrieval p95: 108.95 ms
Qdrant Vector Search + BM25 + RRF + Schema-Aware Reranking
100% Top-1 accuracy across 60 benchmark runs


### Reproduction section

# 1. Start Qdrant
docker compose up -d

# 2. Ensure Ollama embedding model is available
ollama pull nomic-embed-text

# 3. Build / load the local Lakehouse and Qdrant index
python build_local_lakehouse.py

# 4. Run measured hybrid retrieval benchmark
python benchmark_lakehouse_fast.py
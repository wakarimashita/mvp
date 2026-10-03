# AEGIS — HACKATHON CHECKPOINT

## Project
Aegis — Enterprise Knowledge Intelligence Platform & Service Assistant (RAG)
Team: Scythe of Vyse

Goal:
"Answer → Evidence → Action"

Core idea:
Aegis should not merely retrieve documents. It should investigate enterprise knowledge,
resolve outdated/conflicting information, provide provenance, detect knowledge gaps,
and generate safe actions.

## Current status

LOCAL MVP IS WORKING.

Implemented locally:

1. Vector search
   - Ollama nomic-embed-text
   - 768-dimensional embeddings
   - Qdrant

2. Hybrid retrieval
   - Vector search
   - BM25
   - Reciprocal Rank Fusion (RRF)

3. Reranking
   - BAAI/bge-reranker-v2-m3
   - ~7 sec on user's weak laptop

4. Provenance
   - document ID
   - title
   - version
   - effective date
   - status
   - source
   - page
   - section

5. Knowledge Compiler
   - knowledge_graph.json
   - assets
   - documents
   - relationships
   - supersedes relation

6. Conflict / authority resolution
   - current vs superseded documents
   - Evidence Fusion
   - current source takes precedence

7. Query Router
   - EXACT
   - FAST
   - DEEP

8. Deep Investigation
   - unstructured knowledge
   - structured service history
   - causal chain

9. Knowledge Guard
   - SUFFICIENT / INSUFFICIENT
   - knowledge gap generation
   - abstention

10. Action Layer
    - deterministic safe actions
    - no hallucinated technician actions

11. Evaluation
    - golden_questions.json
    - status accuracy
    - source retrieval accuracy
    - current toy dataset: 5 questions
    - current result: 100% / 100%

12. Latency benchmark
    - retrieval stages measured separately
    - important: local laptop is weak
    - Qwen3:4b can take minutes (~4 tokens/sec)
    - don't optimize architecture around local hardware limitations

13. Unified Aegis MVP

USER
 ↓
Query Router
 ↓
Vector + BM25 + RRF
 ↓
Reranker
 ↓
Knowledge Guard
 ├─ insufficient → Knowledge Gap
 └─ sufficient → Evidence Fusion
                      ↓
                     LLM
                      ↓
                Answer + Actions


## Current example

Old manual:
P-481 uses pressure sensor E17.

Service bulletin SB-104:
P-481 sensor was replaced.
New sensor = E21.
SB-104 supersedes old manual.

Service history:
2026-08-15 — E17 intermittent readings
2026-09-10 — E17 replaced with E21

Current answer:
P-481 currently uses E21.

Important architectural lesson:
Reranker determines RELEVANCE.
Evidence Fusion determines AUTHORITY / CURRENTNESS.
LLM should receive normalized evidence, not decide truth from raw chunks.


## Azure status

AZURE MIGRATION IS PAUSED.

Reason:
Hackathon Azure sandbox has not been issued yet.
Do NOT start Azure resource creation.

Planned Azure mapping later:

documents/          → Azure Blob Storage
ingest.py           → Azure Functions
parsers/OCR         → Azure Document Intelligence
Qdrant              → Azure AI Search
Ollama embeddings   → Azure embedding model
Qwen3:4b            → Foundry/Azure OpenAI model
knowledge_graph     → Cosmos DB / graph-like storage
Deep Investigation  → Foundry Agent Service
evaluation          → Foundry Evaluation
telemetry           → Application Insights


## NEXT LOCAL STEP

Do NOT add random features.

Next planned improvement:

HETEROGENEOUS DOCUMENT SOURCES.

Add:
- PDF
- DOCX
- CSV
- XLSX

Example:

documents/
├── pump_p481_manual_v2.json
├── service_bulletin_sb104.json
├── pump_p482_manual.pdf
├── maintenance_records.csv
├── assets.xlsx
└── troubleshooting.docx

Goal:

Create a universal ingestion pipeline that converts different formats
into the same normalized Document / Chunk representation.

Then retrieval should work across:
- unstructured documents
- structured CSV/XLSX
- PDF/DOCX

After that:
extend the knowledge graph and implement simple graph queries.

Potential graph queries:

find_asset("P-481")
find_related_documents("P-481")
find_change_history("P-481")
find_current_configuration("P-481")


## Important implementation principle

Don't install Neo4j just for the sake of using Neo4j.

First demonstrate what graph functionality gives Aegis using the existing
knowledge_graph.json.

If graph queries prove useful, then evaluate:
- Neo4j Docker
- Cosmos DB
- or another graph representation.

## Communication preference

User wants compact interaction.

Preferred workflow:
- one practical step
- complete ready-to-run code
- user runs it
- user says "работает"
- continue

Do not repeat the architecture unnecessarily.

Language:
Russian.

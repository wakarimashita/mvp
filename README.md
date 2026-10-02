# 1. Current Local MVP Architecture

```mermaid
flowchart TB
    User[Developer / Engineer via CLI]

    subgraph LocalPipeline["Local Lakehouse Pipeline"]
        RawDocs[Raw unstructured documents<br/>Manuals, Service Bulletins,<br/>Troubleshooting Notes, Work Instructions]
        RawTables[Structured operational data<br/>Assets, Maintenance Records,<br/>Work Orders, Incidents]

        Bronze[Bronze Layer<br/>Raw files and source tables]
        Silver[Silver Layer<br/>Normalized documents,<br/>chunks and summaries]
        Gold[Gold Layer<br/>Retrieval-ready chunks,<br/>embeddings and metadata]

        RawDocs --> Bronze
        RawTables --> Bronze
        Bronze --> Silver
        Silver --> Gold
    end

    subgraph LocalRetrieval["Local Hybrid Retrieval Service"]
        Gold --> Qdrant[Qdrant<br/>Vector Index]
        Gold --> BM25[In-memory BM25<br/>Keyword Index]

        QueryEmbedding[Ollama<br/>nomic-embed-text query embedding]
        VectorSearch[Vector Search]
        KeywordSearch[Keyword Search]
        RRF[Reciprocal Rank Fusion]

        QueryEmbedding --> VectorSearch
        Qdrant --> VectorSearch
        BM25 --> KeywordSearch
        VectorSearch --> RRF
        KeywordSearch --> RRF

        AssetExpansion[Exact Asset Candidate Expansion]
        AuthorityRerank[Schema-aware Authority Reranking<br/>Asset ID + Intent + Document Type<br/>Status + Source Authority]

        RRF --> AssetExpansion
        AssetExpansion --> AuthorityRerank
    end

    subgraph LocalRAG["Local Trustworthy RAG Layer"]
        Evidence[Evidence Selection]
        Guard[Knowledge Guard<br/>Grounding validation,<br/>citation validation,<br/>safe refusal]
        Generator[Local LLM / RAG Generation]
        Answer[Grounded Answer<br/>Ordered Guidance + Citations<br/>or Explicit Refusal]

        AuthorityRerank --> Evidence
        Evidence --> Generator
        Evidence --> Guard
        Generator --> Guard
        Guard --> Answer
    end

    User --> QueryEmbedding
    User --> AuthorityRerank
    Answer --> User

    subgraph LocalEvaluation["Local Evaluation and Evidence"]
        Benchmark[20-query retrieval benchmark<br/>60 measured runs]
        RAGEval[RAG quality evaluation]
        Metrics[Metrics:<br/>100% Top-1 retrieval accuracy<br/>108.95 ms p95 retrieval latency<br/>Groundedness, relevance,<br/>citation precision, refusal accuracy]

        Benchmark --> Metrics
        RAGEval --> Metrics
    end

    AuthorityRerank --> Benchmark
    Guard --> RAGEval
```

## Current Local MVP Components

| Layer | Current implementation |
|---|---|
| Data generation | `generate_synthetic_corpus.py` |
| Lakehouse transformation | `build_local_lakehouse.py` |
| Gold retrieval corpus | `local_lakehouse/gold/retrieval_chunks.jsonl` |
| Vector index | Qdrant |
| Embeddings | Ollama `nomic-embed-text` |
| Keyword search | Local `rank-bm25` BM25 index |
| Hybrid fusion | Reciprocal Rank Fusion |
| Authority layer | Exact `asset_id` matching, intent detection, document-type and status-aware reranking |
| RAG trust controls | `knowledge_guard.py`, citation validation, refusal handling |
| Retrieval evaluation | `benchmark_lakehouse_fast.py` |
| RAG evaluation | `evaluate_rag.py` |
| Frontend | Python CLI / scripts |
| Access scope model | Metadata field: `access_scope` |

## Proven Local Evidence

```text
Corpus:                       1,000 Gold retrieval chunks
Retrieval mode:               Qdrant Vector + BM25 + RRF + schema-aware reranking
Benchmark questions:          20
Measured retrieval runs:      60
Top-1 retrieval accuracy:     100.00%
p95 retrieval latency:        108.95 ms
Sub-second requirement:       PASS
```

---

# 2. Target Azure-Native Enterprise Architecture

```mermaid
flowchart TB
    Engineer[Engineer]

    subgraph Experience["User Experience"]
        Copilot[Microsoft Copilot Studio<br/>AEGIS Assistant]
    end

    subgraph IdentityGovernance["Identity, Governance and Security"]
        Entra[Microsoft Entra ID<br/>User identity, groups and roles]
        Purview[Microsoft Purview<br/>Sensitivity labels,<br/>classification and governance]
        KV[Azure Key Vault<br/>Secrets and configuration]
    end

    subgraph APIPlatform["Application and API Platform"]
        APIM[Azure API Management<br/>OAuth, rate limits,<br/>audit and API policies]
        API[AEGIS Trust and Authority API<br/>FastAPI on Azure Container Apps]

        Intent[Intent and Asset Detection]
        Authz[Authorization Policy<br/>Entra groups to access scopes]
        Authority[Authority Policy<br/>Current vs superseded,<br/>document-type selection]
        CitationGuard[Citation and Grounding Guard<br/>Evidence sufficiency,<br/>claim support and refusal]
    end

    subgraph KnowledgePlatform["Microsoft Fabric Knowledge Layer"]
        FabricPipeline[Fabric Data Pipeline<br/>Scheduled refresh]

        BronzeAzure[Fabric Lakehouse Bronze<br/>Raw documents and<br/>operational source tables]
        SilverAzure[Fabric Lakehouse Silver<br/>Normalized records,<br/>chunks and summaries]
        GoldAzure[Fabric Lakehouse Gold<br/>Retrieval records,<br/>metadata and embeddings]

        StructuredTables[Structured Tables<br/>Assets, Maintenance Records,<br/>Work Orders, Incidents]
        UnstructuredDocs[Unstructured Content<br/>Manuals, Bulletins,<br/>Troubleshooting, Procedures]

        UnstructuredDocs --> BronzeAzure
        StructuredTables --> BronzeAzure
        FabricPipeline --> BronzeAzure
        BronzeAzure --> SilverAzure
        SilverAzure --> GoldAzure
    end

    subgraph AIAndRetrieval["Azure AI and Retrieval Serving Layer"]
        AOAIEmbed[Azure OpenAI<br/>Embedding Model]
        AISearch[Azure AI Search<br/>Hybrid Vector + Keyword Search<br/>RRF + Metadata/OData Filters]
        AOAIGen[Azure OpenAI<br/>Grounded Response Generation]

        GoldAzure --> AOAIEmbed
        AOAIEmbed --> AISearch
        GoldAzure --> AISearch
    end

    subgraph Observability["Observability"]
        AppInsights[Application Insights<br/>Latency, retrieval traces,<br/>errors and audit telemetry]
        Monitor[Azure Monitor<br/>Alerts and dashboards]
    end

    Engineer --> Copilot
    Copilot --> Entra
    Copilot --> APIM
    APIM --> API

    API --> Intent
    API --> Authz
    Entra --> Authz
    Purview --> Authz
    API --> Authority

    Intent --> AISearch
    Authz --> AISearch
    Authority --> AISearch

    AISearch --> CitationGuard
    CitationGuard --> AOAIGen
    AOAIGen --> CitationGuard
    CitationGuard --> API

    KV --> API

    API --> AppInsights
    AISearch --> AppInsights
    AppInsights --> Monitor

    API --> APIM
    APIM --> Copilot
    Copilot --> Engineer
```

## Azure-Native Data and Request Flow

### Scheduled knowledge refresh flow

```text
Fabric Data Pipeline schedule
    → Ingest documents and operational tables into Bronze
    → Normalize data into Silver
    → Chunk, summarize and enrich document metadata
    → Generate Azure OpenAI embeddings
    → Publish Gold retrieval records
    → Update Azure AI Search index
    → Log pipeline status, record counts and failures
```

### Engineer question flow

```text
Engineer asks AEGIS through Copilot Studio
    → Copilot Studio obtains signed-in Entra identity
    → Request is sent through Azure API Management
    → AEGIS API resolves user roles and authorized scopes
    → API extracts asset ID and question intent
    → Azure AI Search runs hybrid vector + keyword retrieval
       with permission and metadata filters
    → Authority policy selects current and appropriate evidence
    → Azure OpenAI generates ordered guidance from evidence only
    → Citation/grounding guard verifies support for claims
    → API returns cited answer or explicit refusal
    → Copilot Studio displays response and sources
```

## Target Azure Component Responsibilities

| Azure component | Responsibility |
|---|---|
| **Microsoft Fabric Lakehouse** | Governed system of record for raw, normalized and Gold knowledge assets |
| **Fabric Data Pipeline** | Scheduled Bronze → Silver → Gold refresh and index publication |
| **Azure OpenAI embeddings** | Create vectors for Gold chunks and incoming user questions |
| **Azure AI Search** | Low-latency hybrid vector + lexical retrieval, RRF and metadata filtering |
| **Azure Container Apps** | Hosts stateless AEGIS FastAPI trust/authority service |
| **Azure API Management** | Secure, governed API endpoint for Copilot Studio |
| **Azure OpenAI chat model** | Generates concise, ordered and grounded engineering guidance |
| **Microsoft Entra ID** | User authentication, groups and authorization identity |
| **Microsoft Purview** | Data classification, sensitivity labels and governance evidence |
| **Azure Key Vault** | Secrets and service configuration |
| **Application Insights / Azure Monitor** | Latency monitoring, errors, traces, auditability and operational dashboards |
| **Copilot Studio** | Enterprise conversational frontend |

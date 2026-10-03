# 1. Current Local MVP Architecture

```mermaid
flowchart TB
    Engineer["Engineer / Developer<br/>Local Python CLI"]

    subgraph LocalEnvironment["Local Development Environment"]
        Python["Python 3.x<br/>Pipeline, retrieval, RAG,<br/>evaluation and guard scripts"]

        Ollama["Ollama<br/>Embedding model: nomic-embed-text<br/>Generation model: Qwen 3B or local LLM"]

        FileSystem["Local File System<br/>local_lakehouse/"]
    end

    subgraph Lakehouse["Local Lakehouse-Style Knowledge Layer"]
        direction LR

        RawDocuments["Unstructured Documents<br/>Manuals, service bulletins,<br/>troubleshooting notes, work instructions"]

        StructuredData["Structured Operational Data<br/>Assets, maintenance records,<br/>work orders, incidents"]

        Bronze["Bronze Layer<br/>Raw documents and source tables"]

        Silver["Silver Layer<br/>Normalized documents,<br/>chunks and summaries"]

        Gold["Gold Layer<br/>1,000 retrieval-ready chunks<br/>metadata and 768-dimensional vectors"]

        RawDocuments --> Bronze
        StructuredData --> Bronze
        Bronze -->|"build_local_lakehouse.py"| Silver
        Silver -->|"chunk, summarize, embed"| Gold
    end

    subgraph Retrieval["Local Hybrid Retrieval Service"]
        Query["User Query"]

        QueryEmbedding["Ollama Query Embedding<br/>nomic-embed-text"]

        Qdrant["Qdrant Vector Database<br/>Collection: aegis_lakehouse"]

        BM25["BM25 Keyword Index<br/>rank-bm25, in memory"]

        VectorSearch["Semantic Vector Search<br/>Top-K candidates"]

        KeywordSearch["Lexical Keyword Search<br/>Top-K candidates"]

        RRF["Reciprocal Rank Fusion"]

        AssetExpansion["Exact Asset Candidate Expansion<br/>Explicit asset ID constraint"]

        AuthorityRerank["Schema-Aware Authority Reranking<br/>asset_id, intent, document type,<br/>document status and source authority"]

        Query --> QueryEmbedding
        QueryEmbedding --> VectorSearch
        Qdrant --> VectorSearch

        Query --> KeywordSearch
        BM25 --> KeywordSearch

        VectorSearch --> RRF
        KeywordSearch --> RRF
        RRF --> AssetExpansion
        AssetExpansion --> AuthorityRerank
    end

    subgraph RAG["Local Trustworthy RAG Layer"]
        Evidence["Evidence Selection<br/>Authoritative evidence only"]

        Generation["Local LLM Generation<br/>Ordered guidance"]

        Guard["Knowledge Guard<br/>Grounding, citation validation,<br/>safe refusal"]

        Response["Final Response<br/>Step-by-step guidance with citations<br/>or explicit refusal"]

        Evidence --> Generation
        Evidence --> Guard
        Generation --> Guard
        Guard --> Response
    end

    subgraph Evaluation["Local Evaluation and Benchmarking"]
        RetrievalBenchmark["benchmark_lakehouse_fast.py<br/>20 queries, 3 runs each<br/>60 measured runs"]

        RAGEvaluation["evaluate_rag.py<br/>Groundedness, relevance,<br/>citation quality and refusal"]

        Results["Measured Results<br/>100% Top-1 retrieval accuracy<br/>108.95 ms p95 retrieval latency"]

        RetrievalBenchmark --> Results
        RAGEvaluation --> Results
    end

    FileSystem --> Bronze
    FileSystem --> StructuredData
    Gold -->|"index_lakehouse_qdrant.py"| Qdrant
    Gold --> BM25

    Engineer --> Query
    AuthorityRerank --> Evidence
    Response --> Engineer

    AuthorityRerank --> RetrievalBenchmark
    Guard --> RAGEvaluation

    classDef user fill:#E8F0FE,stroke:#2563EB,color:#111827,stroke-width:2px;
    classDef local fill:#ECFDF5,stroke:#059669,color:#111827,stroke-width:2px;
    classDef data fill:#FFF7ED,stroke:#EA580C,color:#111827,stroke-width:2px;
    classDef search fill:#F5F3FF,stroke:#7C3AED,color:#111827,stroke-width:2px;
    classDef guard fill:#FEF2F2,stroke:#DC2626,color:#111827,stroke-width:2px;
    classDef metric fill:#F0FDFA,stroke:#0F766E,color:#111827,stroke-width:2px;

    class Engineer,Query,Response user;
    class Python,Ollama,FileSystem local;
    class RawDocuments,StructuredData,Bronze,Silver,Gold data;
    class Qdrant,BM25,VectorSearch,KeywordSearch,RRF,AssetExpansion,AuthorityRerank search;
    class Evidence,Generation,Guard guard;
    class RetrievalBenchmark,RAGEvaluation,Results metric;
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
    Engineer["Engineer"]

    subgraph MicrosoftCloud["Microsoft Azure and Microsoft Fabric"]
        direction TB

        subgraph Experience["User Experience"]
            Copilot["Microsoft Copilot Studio<br/>AEGIS Assistant"]
        end

        subgraph IdentityGovernance["Identity, Security and Governance"]
            Entra["Microsoft Entra ID<br/>Authentication, user identity,<br/>groups and roles"]

            Purview["Microsoft Purview<br/>Sensitivity labels,<br/>classification and governance"]

            KeyVault["Azure Key Vault<br/>Secrets and configuration"]

            ManagedIdentity["Managed Identity<br/>Passwordless service access"]
        end

        subgraph APIPlatform["Application and API Platform"]
            APIM["Azure API Management<br/>OAuth, policies, rate limits<br/>and API audit"]

            ContainerApps["Azure Container Apps<br/>Stateless AEGIS API hosting"]

            AegisAPI["AEGIS Trust and Authority API<br/>Asset and intent extraction<br/>Authorization policy<br/>Authority selection<br/>Citation validation and refusal"]

            APIM --> ContainerApps
            ContainerApps --> AegisAPI
        end

        subgraph FabricPlatform["Microsoft Fabric Knowledge Platform"]
            FabricPipeline["Fabric Data Pipeline<br/>Scheduled refresh"]

            OneLake["OneLake<br/>Governed data foundation"]

            BronzeAzure["Fabric Lakehouse Bronze<br/>Raw documents and<br/>operational source tables"]

            SilverAzure["Fabric Lakehouse Silver<br/>Normalized documents,<br/>chunks and summaries"]

            GoldAzure["Fabric Lakehouse Gold<br/>Retrieval records,<br/>metadata and embeddings"]

            OperationalTables["Structured Operational Tables<br/>Assets, maintenance records,<br/>work orders and incidents"]

            EnterpriseDocuments["Enterprise Documents<br/>Manuals, service bulletins,<br/>troubleshooting notes and procedures"]

            EnterpriseDocuments --> BronzeAzure
            OperationalTables --> BronzeAzure
            BronzeAzure --> SilverAzure
            SilverAzure --> GoldAzure

            OneLake --- BronzeAzure
            FabricPipeline --> BronzeAzure
            FabricPipeline --> SilverAzure
            FabricPipeline --> GoldAzure
        end

        subgraph AIPlatform["Azure AI and Retrieval Platform"]
            AzureOpenAIEmbedding["Azure OpenAI<br/>Embedding Deployment<br/>Target: text-embedding-3-small<br/>Optional: text-embedding-3-large"]

            AzureAISearch["Azure AI Search<br/>Hybrid vector and keyword retrieval<br/>RRF and OData metadata filters"]

            AzureOpenAIGeneration["Azure OpenAI<br/>Grounded response generation<br/>Target: GPT-4.1-mini<br/>Fallback: GPT-4o-mini"]

            GoldAzure -->|"embedding generation"| AzureOpenAIEmbedding
            GoldAzure -->|"index records and vectors"| AzureAISearch
        end

        subgraph Observability["Observability and Operations"]
            AppInsights["Application Insights<br/>Traces, latency, exceptions<br/>and audit telemetry"]

            AzureMonitor["Azure Monitor<br/>Alerts and dashboards"]

            CostManagement["Azure Cost Management<br/>Budgets, tags and alerts"]

            AppInsights --> AzureMonitor
        end
    end

    Engineer --> Copilot
    Copilot -->|"Signed-in identity"| Entra
    Copilot -->|"HTTPS Custom Connector"| APIM

    Entra -->|"Groups and roles"| AegisAPI
    Purview -->|"Labels and classifications"| AegisAPI
    KeyVault -->|"Secrets"| ContainerApps
    ManagedIdentity -->|"Authorized access"| KeyVault

    AegisAPI -->|"Asset ID, intent and authorized scopes"| AzureAISearch
    AegisAPI -->|"Structured operational lookup"| GoldAzure

    AzureAISearch -->|"Authorized evidence only"| AegisAPI
    AegisAPI -->|"Grounded evidence context"| AzureOpenAIGeneration
    AzureOpenAIGeneration -->|"Draft response"| AegisAPI

    AegisAPI -->|"Latency, retrieval traces,<br/>citation and refusal events"| AppInsights
    AegisAPI -->|"Cited response or refusal"| APIM
    APIM --> Copilot
    Copilot --> Engineer

    classDef user fill:#E8F0FE,stroke:#2563EB,color:#111827,stroke-width:2px;
    classDef security fill:#FEF3C7,stroke:#D97706,color:#111827,stroke-width:2px;
    classDef api fill:#FFF7ED,stroke:#EA580C,color:#111827,stroke-width:2px;
    classDef fabric fill:#F3E8FF,stroke:#9333EA,color:#111827,stroke-width:2px;
    classDef ai fill:#ECFDF5,stroke:#059669,color:#111827,stroke-width:2px;
    classDef observe fill:#F1F5F9,stroke:#475569,color:#111827,stroke-width:2px;

    class Engineer,Copilot user;
    class Entra,Purview,KeyVault,ManagedIdentity security;
    class APIM,ContainerApps,AegisAPI api;
    class FabricPipeline,OneLake,BronzeAzure,SilverAzure,GoldAzure,OperationalTables,EnterpriseDocuments fabric;
    class AzureOpenAIEmbedding,AzureAISearch,AzureOpenAIGeneration ai;
    class AppInsights,AzureMonitor,CostManagement observe;
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

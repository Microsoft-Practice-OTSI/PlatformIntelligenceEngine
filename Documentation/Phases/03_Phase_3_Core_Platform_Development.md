# Phase 3: Core Platform Development & Multi-Channel Architecture (PIE)

> **Document Version:** 2.0 | **Status:** Ready for Implementation | **Prerequisite:** Phase 2 Complete (All 5 Spikes Validated on Live Tenant)

---

## 1. Executive Summary & Architectural Scope
Phase 3 builds the production-grade engineering foundation of the **Platform Intelligence Engine (PIE)**. It turns the proven spikes from Phase 2 into a high-performance, decoupled, headless intelligence platform that exposes unified REST APIs, WebSocket/SSE streaming, and webhooks to power three primary consumer interfaces:

```
                                  ┌────────────────────────────────────────────────────────┐
                                  │      PIE Core Intelligence Engine (Headless API)       │
                                  │   (Graph Engine + Context Builder + AI Reasoning)      │
                                  └───────────────────────────┬────────────────────────────┘
                                                              │
                    ┌─────────────────────────────────────────┼────────────────────────────────────────┐
                    │                                         │                                        │
                    ▼                                         ▼                                        ▼
    ┌───────────────────────────────┐         ┌───────────────────────────────┐        ┌───────────────────────────────┐
    │    1. Web Application Portal  │         │   2. Microsoft Teams Bot      │        │    3. Developer CLI Assistant │
    │    • React / Next.js / Vite   │         │    • Bot Framework Webhooks   │        │    • Local terminal chat      │
    │    • Interactive D3/DAG Lineage│        │    • Interactive Adaptive     │        │    • Rapid IDE discovery      │
    │    • Deletion Risk Sandbox    │         │      Cards in DevOps Channels │        │    • CI/CD audit scripting    │
    │    • Live AI Copilot Drawer   │         │    • @PIE Instant Q&A         │        │    • Sub-300ms offline mode   │
    └───────────────────────────────┘         └───────────────────────────────┘        └───────────────────────────────┘
```

---

## 2. Core Subsystems & Production Deliverables

### 1. Ingestion & Discovery Engine (`pie.discovery`)
* Live Azure Resource Manager (ARM) REST client with automatic pagination, exponential backoff, and Entra ID bearer token refreshing.
* Multi-subscription and multi-factory orchestration across all 9 discovered subscriptions.
* Comprehensive extraction of:
  * **161+ Pipelines** (folders, annotations, parameters, variables).
  * **793+ Activities** (`Copy`, `ExecutePipeline`, `WebActivity`, `ExecuteDataFlow`, `Lookup`, `Script`, `SetVariable`, retry policies, timeouts).
  * **72+ Datasets** (schemas, formats, file paths, linked services).
  * **58+ Linked Services** (connection configurations with secrets/keys safely redacted).
  * **23+ Triggers** (schedule recurrences, state, target pipeline maps).
  * **37+ Data Flows** (source-to-sink mapping graphs).
  * **Factory-Level Global Parameters** (`@pipeline().globalParameters.xxx`).

### 2. In-Memory Directed Knowledge Graph Repository (`pie.graph`)
* Multi-graph topology index (`1,144+ Nodes`, `2,626+ Edges`) with $O(1)$ node lookups and indexed adjacency tables.
* **Deterministic Lineage Traversal (`GraphTraversalService`):**
  * Bidirectional ancestor/descendant graph walker.
  * Localized $k$-hop subgraph isolation.
  * Cycle & recursion loop detector (**0 cycles verified**).
  * Change risk scoring algorithm (0–100 deterministic scale).
* **Deep Activity Storyteller (`PipelineStoryteller`):**
  * Plain-language pipeline execution synthesizer.
  * Minute parameter, SQL query, Stored Procedure, and Key Vault secret inspector.
* **What-If Deletion Simulator (`AssetDeletionSimulator`):**
  * Simulates asset deletion, computing directly broken activities, downstream cascade failures, and step-by-step remediation plans.
* **Enterprise Audit Engine (`audit_engine.py`):**
  * External SaaS vendor mapper (SAP, Dynamics CRM, Databricks, Coupa, RailCarRx).
  * Technical debt & orphan asset detector (identifying 73 orphan pipelines and 371 zero-retry activities).
  * Schedule concurrency collision heatmap (identifying peak batch collisions at 06:00 AM).

### 3. Precision Context Builder & Token Budgeter (`pie.context`)
* **`SchemaCompressor`:** Removes GUI layout coordinates and internal GUIDs, achieving **99.3% token reduction**.
* **`TokenBudgeter`:** Enforces mathematical token allocations across prompt sections.
* **`MultiIntentContextBuilder`:** Tailors high-density prompt packages for `ARCHITECTURE`, `DEBUGGING`, `IMPACT_ANALYSIS`, and `MODERNIZATION`.

### 4. AI Reasoning Engine (`pie.ai`)
* Unified provider abstraction supporting **Azure OpenAI**, **OpenAI**, **Anthropic**, **Gemini**, and **Deterministic Mock Engine**.
* Real-time streaming response generator (SSE) with 100% deterministic grounding.

---

## 3. Production FastAPI REST API Specification (`src/pie/api/`)

The Core Platform exposes a clean, versioned, OpenAPI 3.1 REST API:

```text
├── Authentication & Session
│   GET  /api/v1/auth/session                      # Current Entra ID token status and claims
│   POST /api/v1/auth/login                        # Initiate Device Code authentication
│
├── Discovery & Asset Hierarchy
│   GET  /api/v1/factories                         # List all discovered Data Factories across subscriptions
│   GET  /api/v1/factories/{name}/summary          # Factory dashboard metrics & asset counts
│   GET  /api/v1/pipelines                         # Filterable list of pipelines (by folder, tag, schedule)
│   GET  /api/v1/pipelines/{name}                  # Full normalized pipeline detail with 24-step breakdown
│   GET  /api/v1/datasets                          # Search datasets by file type (csv/parquet) or on-prem status
│   GET  /api/v1/linked-services                   # List linked services and SaaS endpoints
│   GET  /api/v1/triggers                          # List triggers and schedule concurrency
│
├── Knowledge Graph & Lineage Traversal
│   GET  /api/v1/graph/topology                    # Full in-memory graph (nodes and edges)
│   GET  /api/v1/graph/lineage/{asset_name}        # Upstream lineage & downstream blast radius
│   GET  /api/v1/graph/subgraph/{asset_name}       # Localized k-hop subgraph for visual DAG rendering
│   POST /api/v1/graph/deletion-simulation         # What-if deletion simulator and remediation plan
│
├── Technical Debt & Security Governance Auditing
│   GET  /api/v1/audit/technical-debt              # Orphan pipelines, unreferenced datasets, zero retries
│   GET  /api/v1/audit/concurrency-heatmap         # Trigger collision analysis across batch windows
│   GET  /api/v1/audit/saas-vendors                # Mapping of SAP, Databricks, CRM, and Coupa endpoints
│   GET  /api/v1/audit/parameters                  # Factory global parameters & duplicate parameter audit
│
├── AI Reasoning & Streaming Chat
│   POST /api/v1/ai/ask                            # Synchronous AI reasoning query
│   GET  /api/v1/ai/chat/stream                    # Server-Sent Events (SSE) streaming token response
│   POST /api/v1/ai/generate-code                  # Automated PySpark / dbt migration script generator
│
└── Multi-Channel Webhooks (Teams Bot & Slack)
    POST /api/v1/teams/webhook                     # Microsoft Teams Bot webhook returning Adaptive Cards
    POST /api/v1/teams/cards/deletion-impact       # Generates rich Adaptive Card for deletion simulation
```

---

## 4. Microsoft Teams Bot Adaptive Card Architecture

When integrated into Microsoft Teams channels, PIE responds with interactive **Adaptive Cards**:

```json
{
  "type": "AdaptiveCard",
  "version": "1.4",
  "body": [
    {
      "type": "TextBlock",
      "text": "⚠️ PIE Asset Deletion Risk Assessment",
      "weight": "Bolder",
      "size": "Medium",
      "color": "Attention"
    },
    {
      "type": "FactSet",
      "facts": [
        {"title": "Target Asset", "value": "DataLakeCsv (Dataset)"},
        {"title": "Risk Rating", "value": "CRITICAL (100/100)"},
        {"title": "Blast Radius", "value": "20 broken entities in Pre Release pipeline"}
      ]
    }
  ],
  "actions": [
    {
      "type": "Action.OpenUrl",
      "title": "Open Visual Lineage in PIE Portal",
      "url": "https://pie.company.local/lineage/DataLakeCsv"
    }
  ]
}
```

---

## 5. Phase 3 Exit Criteria & Readiness
* **FastAPI Server Running:** All `/api/v1/` endpoints operational with comprehensive OpenAPI/Swagger documentation.
* **In-Memory Cache & Repository:** Sub-5ms query response times across all 161 pipelines and 793 activities.
* **Multi-Channel Verification:** Validated responses across CLI, Web REST endpoints, and Teams Bot Adaptive Card payloads.
* **100% Passing Test Suite:** Expanding the 29 unit tests from Phase 2 into a comprehensive integration and API test suite.

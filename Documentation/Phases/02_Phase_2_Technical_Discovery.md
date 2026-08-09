# Phase 2: Technical Discovery & Validation (PIE)

> **Document Version:** 2.0 | **Status:** Spikes 1–4 Validated Live / Spike 5 In Progress | **Live Tenant:** `6df067fb-6816-4dc8-af4d-07eba42c900b`

---

## 1. Executive Summary & Objectives
Phase 2 de-risks all core technical assumptions through 5 focused Proof-of-Concept Spikes validated directly against real Microsoft Azure subscriptions and live enterprise Azure Data Factory instances.

---

## 2. The 5 Technical Spikes & Validated Implementations

### 🔐 Spike 1: Azure Authentication & RBAC Discovery (Validated Live)
* **Goal:** Authenticate securely using Microsoft Entra ID Device Code flow with least-privilege Reader role.
* **Live Discovery:** Authenticated `Vishwajeeth.Vangala@watco.com` across all **9 Azure Subscriptions**:
  1. `Azure Enterprise  - EIM Team` (`60a58917-1a0c-4902-a24d-ab97dd75f0ab`) — **4 Data Factory Instances**
  2. `Production` (`fce19f33-6b97-4ffb-9fac-f947c987ff7f`) — 1 Data Factory
  3. `Development` (`bb8f520a-dadb-47ee-a008-80bd125c79ff`) — 2 Data Factories
  4. `Pay-As-You-Go` (`433bf937-861d-4e1a-9267-77a249cf0ebc`) — 2 Data Factories
  5. `Sandbox` (`0b20d376-d479-4b33-93d7-abb8d3681c15`) — 1 Data Factory
  6. `UAT`, `QA`, `Hub`, `Free Credits Visual Studio Pro`
* **Artifacts:** `spikes/spike_1_auth/output/token_session.json` & `spike_1_results.json`.

---

### 🏭 Spike 2: ADF Metadata Extraction & Schema Normalization (Validated Live)
* **Goal:** Extract and normalize live metadata from **`df-dataintegration-dev`** (`rg-dataintegration-dev`).
* **Live Extraction Volume:**
  * **161 Pipelines** with folders, parameters, variables, and annotations.
  * **793 Activities** with dependency precedence (`dependsOn`), inputs, outputs, retry policies, and timeouts.
  * **72 Datasets** with schemas, linked services, and path locations.
  * **58 Linked Services** with connection properties (passwords and secret keys securely redacted).
  * **23 Triggers** with recurrence schedules and target pipeline mappings.
  * **37 Mapping Data Flows**.
* **Artifacts:** `spikes/spike_2_discovery/output/spike_2_metadata.json` (4.8 MB JSON).

---

### 🧠 Spike 3: Knowledge Graph, Deep Storyteller & Enterprise Audit Suite (Validated Live)
* **Goal:** Map extracted metadata into an in-memory directed multi-graph (`1,144 Nodes`, `2,626 Edges`).
* **Core Graph Engines Implemented:**
  1. **Lineage Traversal (`GraphTraversalService`):**
     * Upstream lineage tracing to root triggers and source data stores.
     * Downstream blast radius and deterministic risk scoring (0–100).
     * Cycle & recursion loop detector (**0 circular loops verified** across 161 pipelines).
  2. **Minute Activity Storyteller (`PipelineStoryteller`):**
     * Inspects minute activity parameters, Stored Procedures, SQL queries, Key Vault secrets, Web API endpoints, and Copy source/sink transformations (demonstrated live on `RailCarRx_InvoiceLoad`).
  3. **Multi-Criteria Asset Discovery (`AssetQueryEngine`):**
     * Discovers datasets by file format (`csv`, `parquet`, `json`), on-prem/cloud connectivity (`OnPremEtlFileStore`), folder, and schema columns.
  4. **What-If Deletion Simulator & Remediation Planner (`AssetDeletionSimulator`):**
     * Simulates dataset or linked service deletion, identifying broken readers/writers, impacted pipelines, and step-by-step remediation plans.
  5. **Enterprise Security & Technical Debt Audit Suite (`audit_engine.py`):**
     * **SaaS Vendor Mapping:** SAP (4 linked services), Dynamics CRM, Databricks Lakehouse (4 clusters), RailCarRx, Coupa, OpenText ECM, Datex WMS, Cleo.
     * **Technical Debt:** Identified **73 orphan pipelines** and **371 zero-retry fragile activities**.
     * **Schedule Concurrency Heatmap:** Identified **17 concurrent pipelines** firing in the Daily batch window.
* **Artifacts:** `spikes/spike_3_graph/output/spike_3_graph.json`.

---

### 📦 Spike 4: Context Builder, Subgraph Extractor & Token Budgeting (Validated Live)
* **Goal:** Intelligently extract localized $k$-hop subgraphs and format token-budgeted prompt payloads for AI reasoning.
* **Engines Implemented:**
  1. **`SchemaCompressor`:** Strips UI visual layout coordinates and system GUIDs, compressing raw metadata by 90%+.
  2. **`TokenBudgeter`:** Enforces mathematical token allocations across prompt sections (guaranteeing zero LLM truncation).
  3. **`MultiIntentContextBuilder`:** Tailors context across 4 cognitive intents:
     * 📋 `ARCHITECTURE`: Executive overview, SaaS vendors, schedule.
     * 💻 `DEBUGGING`: Technical sequence, SQL queries, stored procedures, retry policies.
     * 🛡️ `IMPACT_ANALYSIS`: Blast radius, broken activities, change risk remediation plan.
     * 🔄 `MODERNIZATION`: Schema mappings for PySpark/dbt code generation.
* **Live Performance & Compression Metrics:**
  * `RailCarRx_InvoiceLoad` Pipeline: **184,208 raw tokens $\rightarrow$ 1,324 compressed tokens (99.3% reduction)**.
  * `DataLakeCsv` Dataset: **6,353 raw tokens $\rightarrow$ 263 compressed tokens (95.9% reduction)**.
* **Artifacts:** `spikes/spike_4_context/output/spike_4_context.json` & `spike_4_context.md`.

---

### 🤖 Spike 5: AI Reasoning Engine & End-to-End Chat (In Progress)
* **Goal:** Connect high-density context packages to LLM reasoning (OpenAI, Azure OpenAI, Anthropic, Gemini, and Mock providers).
* **Scope:**
  1. `LLMProvider` abstraction supporting streaming responses.
  2. Dynamic Intent Classifier & Query Router.
  3. Terminal chat assistant answering real architectural, debugging, deletion, and code-generation questions with 100% ground truth.

---

## 3. Phase 2 Test Coverage Matrix
All **27 unit tests** across Spikes 1–4 are passing with 100% green status:
* `tests/unit/test_auth_models.py` (3 passed)
* `tests/unit/test_credentials.py` (3 passed)
* `tests/unit/test_discovery_mock_fixture.py` (1 passed)
* `tests/unit/test_discovery_normalizer.py` (4 passed)
* `tests/unit/test_graph_engine.py` (12 passed)
* `tests/unit/test_context_builder.py` (4 passed)

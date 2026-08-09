# Phase 1: Product Definition & Vision (PIE)

> **Document Version:** 1.0 | **Status:** Complete / Approved | **Prerequisites:** None

---

## 1. Executive Summary & Vision
* **Product:** Platform Intelligence Engine (PIE)
* **Tagline:** *“Understanding your Azure Data Factory before you change it.”*
* **Core Mission:** Transform technical Azure Data Factory metadata into actionable engineering intelligence using Azure-native AI services.

---

## 2. Product Philosophy

### What PIE Is NOT:
* **NOT a Chatbot:** Does not rely on generic internet knowledge.
* **NOT a Documentation Generator:** Docs are an output, not the primary identity.
* **NOT a Replacement for ADF Studio:** Does not build, deploy, or run pipelines.
* **NOT a Pipeline Execution Platform:** Execution-agnostic and out-of-band.

### What PIE IS:
* An **Engineering Intelligence Platform**
* A **Platform Discovery Engine**
* A **Dependency & Blast-Radius Analysis Engine**
* An **AI-Assisted Engineering Advisor**
* A **Knowledge Preservation Platform**

---

## 3. Key Problems Solved
1. **Knowledge Loss:** Tribal knowledge vanishes when senior engineers leave the team.
2. **Documentation Rot:** Hand-written documentation becomes stale immediately after implementation.
3. **Manual Dependency Analysis:** Engineers waste days tracing JSON definitions across pipelines, datasets, and linked services.
4. **Slow Onboarding:** New hires need weeks to safely navigate environments with 200+ pipelines.
5. **Change Risk:** Modifying or deleting a shared dataset/linked service causes unexpected downstream pipeline failures.

---

## 4. Target Personas
* **Data Engineers:** Daily pipeline comprehension, dependency tracing, and change risk mitigation.
* **Technical Leads:** PR risk analysis, architecture review, and standard enforcement.
* **Solution Architects:** End-to-end estate visibility, integration patterns, and technical debt audit.
* **Support / Operations Engineers:** Upstream/downstream root-cause investigation during incident triage.

---

## 5. Scope & Boundaries
* **In Scope (MVP):**
  * Assets: Pipelines, Activities, Datasets, Linked Services, Triggers, Data Flows.
  * Capabilities: Automated metadata discovery, dependency graph, AI explanations, impact analysis, semantic search, asset explorer.
* **Explicitly Excluded from MVP (Deferred to Future):**
  * Azure Databricks, Microsoft Fabric, Azure Synapse Analytics, Microsoft Purview, Azure DevOps / Git repositories.
  * Pipeline editing, pipeline execution, runtime telemetry monitoring, and cost optimization.

---

## 6. Core Engineering Principles
* **Metadata-First:** Discovered platform metadata is the single source of truth.
* **Knowledge Graph Centric:** Graph is the primary layer for structural relationships and dependency traversal.
* **AI for Reasoning:** AI interprets structured platform context; it does not store platform state.
* **Read-Only Architecture (Least Privilege):** Requires only Azure Reader role; never modifies resources.
* **Azure Native:** Built with Azure Management APIs, Azure AI Search, and Azure AI Foundry.

---

## 7. Phase 1 Exit Criteria
* Product vision finalized and approved.
* MVP boundaries and target personas agreed upon.
* Architecture blueprints established for Phase 2 technical spikes.

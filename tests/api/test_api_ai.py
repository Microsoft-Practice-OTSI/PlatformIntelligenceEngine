"""Integration tests for AI Reasoning, SSE streaming chat, and code generation."""

from starlette.testclient import TestClient


def test_ai_ask_architecture_and_impact(client: TestClient):
    """Verify synchronous grounded AI reasoning responses."""
    resp_arch = client.post(
        "/api/v1/ai/ask",
        json={"query": "Explain the PL_Customer_Daily_Ingestion pipeline"},
    )
    assert resp_arch.status_code == 200
    data_arch = resp_arch.json()
    assert data_arch["detected_intent"] == "ARCHITECTURE"
    assert data_arch["target_asset"] == "PL_Customer_Daily_Ingestion"
    assert "PL_Customer_Daily_Ingestion" in data_arch["response_markdown"]
    assert "does" in data_arch["response_markdown"]
    assert data_arch["grounding_score"] == 100.0


def test_ai_chat_stream_sse(client: TestClient):
    """Verify Server-Sent Events (SSE) streaming token output."""
    resp = client.post(
        "/api/v1/ai/chat/stream",
        json={"query": "Explain the PL_Customer_Daily_Ingestion pipeline"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    body_text = resp.text
    assert "event: metadata" in body_text
    assert "event: token" in body_text
    assert "event: done" in body_text


def test_ai_ask_factory_facts_concise(client: TestClient):
    """Direct factory lookups return a short deterministic answer, not an essay."""
    resp = client.post(
        "/api/v1/ai/ask",
        json={"query": "what is the factory name we are connected to"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Factory Name" in data["response_markdown"]
    assert len(data["response_markdown"]) < 300
    assert "FACTORY CONTEXT" not in data["response_markdown"]


def test_ai_ask_factory_count_concise(client: TestClient):
    """Plain count questions return just the count, not the full pipeline inventory."""
    resp = client.post(
        "/api/v1/ai/ask",
        json={"query": "how many pipelines are there"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pipelines" in data["response_markdown"]
    assert "| Factory | Pipeline Count |" not in data["response_markdown"]


def test_ai_generate_code(client: TestClient):
    """Verify automated PySpark migration code generator."""
    resp = client.post(
        "/api/v1/ai/generate-code",
        json={"pipeline_name": "PL_Customer_Daily_Ingestion", "target_framework": "pyspark"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_name"] == "PL_Customer_Daily_Ingestion"
    assert data["target_framework"] == "pyspark"
    assert "```python" in data["generated_code"]
    assert "pyspark" in data["generated_code"]

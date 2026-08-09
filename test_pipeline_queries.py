"""Test deterministic pipeline count and keyword filtering."""
import requests

BASE = "http://localhost:8000/api/v1"
HEADERS = {"X-Session-Token": "test-session", "Content-Type": "application/json"}

# Sync factory
r = requests.post(f"{BASE}/discovery/sync", json={"subscription_id": "sub-1", "factory_names": ["df-dataintegration-dev"]}, headers=HEADERS)
print(f"Sync: {r.status_code}, factories: {r.json().get('synced_factories')}")

# Test 1: how many pipelines (should be deterministic, no LLM)
r1 = requests.post(f"{BASE}/ai/ask", json={"query": "how many pipelines are there", "factory_name": "df-dataintegration-dev"}, headers=HEADERS)
d1 = r1.json()
print(f"\n--- Test 1: how many pipelines (latency: {d1.get('latency_ms')}ms) ---")
print(d1.get("response_markdown", "")[:400])

# Test 2: coupa pipelines keyword filter (should be fast, no LLM)
r2 = requests.post(f"{BASE}/ai/ask", json={"query": "how many coupa pipelines are there", "factory_name": "df-dataintegration-dev"}, headers=HEADERS)
d2 = r2.json()
print(f"\n--- Test 2: coupa pipelines (latency: {d2.get('latency_ms')}ms) ---")
print(d2.get("response_markdown", "")[:400])

# Test 3: find sap pipelines
r3 = requests.post(f"{BASE}/ai/ask", json={"query": "find all sap pipelines", "factory_name": "df-dataintegration-dev"}, headers=HEADERS)
d3 = r3.json()
print(f"\n--- Test 3: find sap pipelines (latency: {d3.get('latency_ms')}ms) ---")
print(d3.get("response_markdown", "")[:400])

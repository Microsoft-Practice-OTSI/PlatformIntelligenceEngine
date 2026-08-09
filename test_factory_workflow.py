#!/usr/bin/env python
"""Test factory selection and sync workflow"""
import requests
import json

# Test the full workflow: sync -> chat -> verify factory is used

BASE_URL = "http://localhost:8000/api/v1"

print("=" * 60)
print("TEST: Factory Selection & Sync Workflow")
print("=" * 60)

# Step 1: Sync factory (no ARM token)
print("\n1. SYNC: Creating mock factory 'df-dataintegration-uat'")
sync_response = requests.post(
    f"{BASE_URL}/discovery/sync",
    json={
        "subscription_ids": ["test-sub-id"],
        "factory_names": ["df-dataintegration-uat"],
        "factory_resource_groups": {"df-dataintegration-uat": "test-rg"},
    }
)
print(f"   Status: {sync_response.status_code}")
sync_data = sync_response.json()
print(f"   Synced: {sync_data.get('synced_factories')}")
print(f"   Pipelines: {sync_data.get('total_pipelines')}")

# Step 2: Get factories list
print("\n2. GET FACTORIES: Check available factories")
factories_response = requests.get(f"{BASE_URL}/factories")
print(f"   Status: {factories_response.status_code}")
factories_data = factories_response.json()
print(f"   Factories: {[f['factory_name'] for f in factories_data.get('factories', [])]}")

# Step 3: Ask question using specific factory
print("\n3. CHAT: Query using specific factory 'df-dataintegration-uat'")
chat_response = requests.post(
    f"{BASE_URL}/ai/ask",
    json={
        "query": "What are the pipelines in this factory?",
        "factory_name": "df-dataintegration-uat",
        "model": "mock",
    }
)
print(f"   Status: {chat_response.status_code}")
chat_data = chat_response.json()
print(f"   Intent: {chat_data.get('detected_intent')}")
print(f"   Factory Name (response): {chat_data.get('response_markdown', '')[:100]}...")

# Step 4: Check if response mentions the right factory
if "df-dataintegration-uat" in chat_data.get('response_markdown', '').lower():
    print("\n   ✅ SUCCESS: Response mentions the selected factory!")
elif "df-dataintegration-dev" in chat_data.get('response_markdown', '').lower():
    print("\n   ❌ FAIL: Response mentions wrong factory (df-dataintegration-dev)")
else:
    print("\n   ⚠️ UNCLEAR: Could not determine which factory was used")

print("\n" + "=" * 60)

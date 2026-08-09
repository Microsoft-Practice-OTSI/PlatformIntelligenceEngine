#!/usr/bin/env python
"""Test complete workflow: sync -> get factories -> chat"""
import requests
import json

# First, trigger a sync
print("1. SYNC: Syncing factory...")
sync_url = 'http://localhost:8000/api/v1/discovery/sync'
payload = {
    'subscription_ids': ['test-sub'],
    'factory_names': ['df-dataintegration-uat'],
    'factory_resource_groups': {'df-dataintegration-uat': 'test-rg'}
}

r = requests.post(sync_url, json=payload)
print(f"   Status: {r.status_code}")
sync_result = r.json()
print(f"   Synced: {sync_result.get('synced_factories')}")
print(f"   Pipelines: {sync_result.get('total_pipelines')}")

# Check what's in the factories list
print("\n2. GET FACTORIES: Checking stored factories...")
factories_url = 'http://localhost:8000/api/v1/factories'
r2 = requests.get(factories_url)
print(f"   Status: {r2.status_code}")
factories = r2.json().get('factories', [])
factory_names = [f['factory_name'] for f in factories]
print(f"   Found: {factory_names}")

# Now make a chat request with that factory
print("\n3. CHAT: Making request with df-dataintegration-uat...")
chat_url = 'http://localhost:8000/api/v1/ai/ask'
chat_payload = {
    'query': 'What pipelines exist?',
    'factory_name': 'df-dataintegration-uat',
    'model': 'mock'
}
r3 = requests.post(chat_url, json=chat_payload)
resp = r3.json()
print(f"   Status: {r3.status_code}")

# Check which factory the response mentions
response_text = resp.get('response_markdown', '')
if 'df-dataintegration-uat' in response_text:
    print("   ✅ Response mentions the correct factory (df-dataintegration-uat)")
elif 'df-dataintegration-dev' in response_text:
    print("   ❌ Response mentions wrong factory (df-dataintegration-dev)")
else:
    print("   ⚠️ Could not determine factory from response")

print(f"\n   Response preview: {response_text[:150]}...")

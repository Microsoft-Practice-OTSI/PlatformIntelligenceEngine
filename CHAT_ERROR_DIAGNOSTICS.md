# Chat API Error Diagnostics Guide

## Issue
When asking questions in the chat, you get an error: "Sorry, I encountered an error. Please ensure the backend is running and synced"

## Changes Made to Debug This

### 1. Enhanced Frontend Error Logging
- **File:** `frontend/src/components/Chat/ChatContainer.jsx`
- **Changes:**
  - Added console logging of all request details (factory, model, session token)
  - Added detailed error response logging including HTTP status, headers, and backend error message
  - Updated error message to show actual backend error instead of generic message
  - Added prompt to check browser console for full details

### 2. Fixed Factory Graph Rebuilding
- **File:** `src/pie/ai/engine.py`
- **Changes:**
  - Added logic to rebuild knowledge graph when a different factory is requested
  - Engine now checks if requested factory differs from current graph's factory
  - If different, engine fetches the factory from repository and rebuilds all graph services
  - Added logging to track factory selection and graph rebuilds

## How to Diagnose

### Step 1: Refresh Browser
```
Press Ctrl+R or F5 to reload the frontend
```

### Step 2: Open DevTools
```
Press F12 or Right-click → Inspect → Console tab
```

### Step 3: Reproduce the Error
1. Log in with Microsoft account
2. Select subscription and factory
3. Ask any question (e.g., "How many pipelines?")

### Step 4: Check Console for Errors
Look for one of these messages:

#### Message Type 1: Request Details
```
{
  factory: "adf-sales-enterprise-prod",
  model: "azure-openai",
  sessionToken: "✓ present",
  query: "How many pipelines..."
}
```
This shows the request is being sent correctly.

#### Message Type 2: Successful Response
```
{
  query: "How many pipelines?",
  detected_intent: "GENERAL",
  response_markdown: "...",
  latency_ms: 42.5
}
```
This means the chat worked! Error might be intermittent.

#### Message Type 3: Error Details
```
{
  message: "Network Error",
  status: 500,
  statusText: "Internal Server Error",
  data: {
    detail: "Specific error message from backend"
  }
}
```
**This is what we need to see** - it shows the actual error

### Step 5: Report the Error
If you see an error in Step 4, share:
- The full error object from the console
- The specific error message
- Which model was selected (Google Gemini, Azure OpenAI, or NVIDIA NIM)
- Any warnings in the backend terminal

## What the Error Might Be

### Error: "Factory not found"
- **Cause:** Selected factory hasn't been synced
- **Fix:** Go to Settings → Sync Factories again

### Error: "Graph is empty"
- **Cause:** No metadata was loaded for the factory
- **Fix:** Ensure factory sync completed successfully

### Error: "Missing API key"
- **Cause:** Selected model (Google/NVIDIA) requires API key
- **Fix:** Go to Settings → Add API key for selected model

### Error: Connection refused / Network Error
- **Cause:** Backend not running on port 8000
- **Fix:** Check terminal running backend, restart if needed

### Error: CORS error
- **Cause:** Frontend and backend port mismatch
- **Fix:** Verify frontend is on :5173 and backend on :8000

## Quick Checklist

Before reporting the error, verify:
- [ ] Backend terminal shows "Application startup complete" (no errors)
- [ ] Frontend shows blue "PIE" logo (app loaded)
- [ ] Logged in successfully (can see subscriptions)
- [ ] Selected a factory and saw "Syncing..." complete
- [ ] Workspace page shows chat interface
- [ ] localStorage has `selected_factory` key (DevTools → Application → localStorage)

## Testing the Backend Directly

If you want to test without the frontend, run:
```bash
cd d:\Gravity\ADPIE
python -c "
import requests
url = 'http://localhost:8000/api/v1/ai/ask'
payload = {
    'query': 'How many pipelines do we have?',
    'factory_name': 'adf-sales-enterprise-prod',
    'model': 'azure-openai'
}
r = requests.post(url, json=payload)
print(f'Status: {r.status_code}')
print(f'Response: {r.json()}')
"
```

If this works (Status 200), the backend is fine and the issue is on the frontend side (authentication or CORS).

## Next Steps

1. **Refresh browser** with the new code
2. **Try asking a question** again
3. **Open browser console** (F12)
4. **Copy the error details** from the console
5. **Report back** with the specific error message

---

**Note:** The improvements above will show you the ACTUAL error instead of a generic message, making it much easier to diagnose the root cause.

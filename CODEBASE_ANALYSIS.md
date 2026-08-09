# ADPIE Codebase Analysis: Authentication & AI Integration

**Date:** August 9, 2026  
**Analysis Scope:** Authentication flow, factory connection caching, AI provider integration

---

## Table of Contents
1. [Authentication & Factory Connection Flow](#section-1)
2. [AI API Integration](#section-2)
3. [Environment Configuration](#section-3)
4. [Critical Issues & Findings](#section-4)
5. [Architecture Diagrams](#section-5)

---

## Section 1: Authentication & Factory Connection Flow

### 1.1 Overview

The system uses **OAuth2 PKCE (Proof Key for Code Exchange)** with Microsoft Entra ID for browser-based login. The authentication is integrated with Azure factory discovery via the Azure Resource Manager (ARM) API. Sessions are stored in-memory and persisted across requests using session tokens.

### 1.2 Authentication Architecture

#### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Auth Router** | `src/pie/api/routers/auth.py` | Handles OAuth2 PKCE flow, session creation, polling |
| **Session Store** | `src/pie/auth/session_store.py` | Thread-safe in-memory storage for sessions and PKCE states |
| **Callback Server** | Port 8100 (auto-started) | HTTP server that catches OAuth redirects |
| **API Client** | `frontend/src/api/client.js` | Axios client that auto-attaches session token to requests |

#### OAuth2 PKCE Configuration

```
Client ID:    04b07795-8ddb-461a-bbee-02f9e1bf7b46 (Azure CLI public client)
Authority:    https://login.microsoftonline.com/common
Redirect URI: http://localhost:8100 (path-less, no /callback)
Scopes:       openid, profile, email, https://management.azure.com/user_impersonation
Callback Port: 8100 (persistent, runs as daemon thread)
```

**Why path-less redirect?** The wildcard redirect URI allows the server to capture the callback on any path, making it more flexible.

### 1.3 Login Flow (Step-by-Step)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AUTHENTICATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────────┘

STEP 1: Initiate Login
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Frontend: POST /api/v1/auth/login
  ↓
Backend:
  - Generate PKCE parameters: state, code_verifier, code_challenge
  - Create flow_id (UUID)
  - Store: _pending_states[state] = {flow_id, pkce_flow}
  - Store: _flows[flow_id] = {status: "pending"}
  - Return: {login_url, flow_id, poll_url}
  ↓
Frontend: window.open(login_url, '_blank')


STEP 2: User Authenticates with Microsoft
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User: Signs in with Microsoft account
  ↓
Microsoft: Redirects to http://localhost:8100?code=AUTH_CODE&state=STATE_VALUE


STEP 3: Callback Handler Processes Redirect
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Callback Server (:8100):
  1. Parse URL: extract code, state
  2. Look up state in _pending_states
  3. Retrieve: flow_id, code_verifier
  4. Remove state from _pending_states (prevents replay)
  5. Exchange code for token:
     POST https://login.microsoftonline.com/common/oauth2/v2.0/token
       - grant_type: authorization_code
       - code: AUTH_CODE
       - code_verifier: stored PKCE verifier
       - client_id, redirect_uri, scope
  6. Receive: access_token, id_token, refresh_token, expires_in
  7. Decode JWTs: extract tenant_id, user_id, display_name
  8. Create PIE Session:
     - session_token = UUID
     - expires_at = now + expires_in_seconds
     - Store in _sessions[session_token]
  9. Render HTML success page with session_token in JavaScript
     (JavaScript posts message to parent window or stores in sessionStorage)


STEP 4: Poll for Session Ready
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Frontend: Poll GET /api/v1/auth/poll/{flow_id} every 2 seconds
  ↓
Backend:
  - Check _flows[flow_id].status
  - Return {status, session_token, user_id, display_name, tenant_id}
  ↓
Frontend:
  - If status == "complete":
      - localStorage.setItem('x_session_token', session_token)
      - Proceed to factory selection
  - If status == "error":
      - Display error message
  - If status == "pending":
      - Wait and poll again


STEP 5: Session Inspection (Optional)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Frontend: GET /api/v1/auth/session
  Header: X-Session-Token: {session_token}
  ↓
Backend:
  - Retrieve session from _sessions[session_token]
  - Check if expired (token_expires_at <= now)
  - Return: SessionInfo {authenticated, tenant_id, user_id, claims}
```

### 1.4 Session Store Implementation

**File:** `src/pie/auth/session_store.py`

```python
class PieSession:
    """Authenticated session from completed OAuth2 flow."""
    session_token: str           # UUID sent as X-Session-Token header
    tenant_id: str               # From JWT: tid claim
    user_id: str                 # From JWT: preferred_username, upn, or email
    display_name: str            # From JWT: name claim
    access_token: str            # Bearer token for ARM API calls
    token_expires_at: datetime   # Expiration time
    auth_mode: str = "oauth2_pkce_browser"
    created_at: datetime

class SessionStore:
    _pending: dict[str, dict]    # state → {code_verifier, redirect_uri, created_at}
    _sessions: dict[str, PieSession]  # session_token → session
    _lock: threading.Lock()      # Thread safety
```

**Key Methods:**
- `create_session(tenant_id, user_id, display_name, access_token, expires_in_seconds)`
  - Returns: `PieSession` with new `session_token`
  - Stores in `_sessions[session_token]`
  - Thread-safe

- `get_session(session_token) → Optional[PieSession]`
  - Returns None if token not found or expired
  - Expired sessions are automatically deleted

- `pop_pkce_state(state) → Optional[dict]`
  - Retrieves and removes state (prevents replay attacks)
  - Rejects states older than 10 minutes

**Current Limitation:** Sessions stored in process memory only. On server restart, all sessions are lost.

### 1.5 Factory Discovery & Loading

#### Discovery Endpoints

The factory discovery flow uses three main endpoints:

**1. GET /subscriptions**
```
Purpose: Enumerate Azure subscriptions accessible to the user
Auth:    X-Session-Token header (optional)
Flow:
  - If authenticated: Calls Azure ARM API
    GET https://management.azure.com/subscriptions?api-version=2022-12-01
    Returns: Real subscription list
  - If unauthenticated: Returns mock catalog
Returns: SubscriptionListResponse {subscriptions[], total}
```

**2. POST /subscriptions/factories**
```
Purpose: List ADF instances within selected subscriptions
Auth:    X-Session-Token header (required for real data)
Body:    subscription_ids: list[str]
Flow:
  - For each subscription:
      GET https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.DataFactory/factories?api-version=2018-06-01
  - Extract factory metadata:
      * factory_name
      * resource_group (from ARM resource ID)
      * location
      * subscription_id
  - Check if already synced: is_synced = repo.get_factory(name) is not None
  - Get last_refreshed_at timestamp
Returns: FactoryListResponse {factories[], total}
```

**3. POST /discovery/sync**
```
Purpose: Sync selected factories - pulls live ADF metadata and loads into KnowledgeGraph
Auth:    X-Session-Token header (optional, falls back to mock)
Body:    SyncRequest {
  subscription_ids: list[str],
  factory_names: list[str],
  factory_resource_groups: dict[str, str],  # factory_name → resource_group
  force_refresh: bool
}
Flow:
  - For each factory:
      - Call AdfMetadataExtractor with ARM token
      - Extract: pipelines, datasets, linked_services, triggers
      - Normalize metadata
      - Build KnowledgeGraph
      - Store in MetadataRepository
  - Update last_refreshed_at timestamp
Returns: SyncResponse {
  status,
  synced_factories: list[str],
  total_pipelines: int,
  total_activities: int,
  total_datasets: int,
  total_linked_services: int,
  total_triggers: int,
  last_refreshed_at: str
}
```

**4. GET /factories** (Added for workspace)
```
Purpose: List all currently synced factories for current tenant
Auth:    X-Tenant-ID header (optional)
Query:   ?subscription_id=<id> (optional filter)
Flow:
  - repo.list_factories(tenant_id, subscription_id)
  - For each factory: get last_refreshed_at timestamp
  - Return as FactoryItem list
Returns: FactoryListResponse {factories[], total}
```

#### Factory Caching Behavior

**Current Logic:**
```python
# In discovery.py - list_factories_in_subscriptions()
loaded_factories = repo.list_factories(tenant_id=tenant_id)
loaded_names = {f.factory_name.lower(): f for f in loaded_factories}

for f in response.json().get("value", []):
    f_name = f.get("name", "")
    existing = loaded_names.get(f_name.lower())
    discovered.append(FactoryItem(
        ...
        is_synced=existing is not None,  # Already loaded into KnowledgeGraph?
        ...
    ))
```

**Caching Observations:**
- ✅ Factories are cached in `MetadataRepository` (in-memory)
- ✅ `is_synced` flag indicates if KnowledgeGraph is loaded
- ✅ `last_refreshed_at` timestamp tracks when metadata was synced
- ✅ `force_refresh=True` in SyncRequest allows re-download
- ❌ Repository is NOT persisted to disk - lost on server restart
- ❌ No cache invalidation strategy (always newest ARM data if `force_refresh=True`)

### 1.6 Frontend Factory Selection & Caching

**File:** `frontend/src/components/Onboarding/SetupWizard.jsx`

#### The Setup Wizard Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FRONTEND ONBOARDING FLOW                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Initial Check: Is user already authenticated?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
useEffect (on mount):
  1. Check localStorage.getItem('x_session_token')
  2. If found:
     - Try GET /auth/session with X-Session-Token header
     - If valid:
       - Try GET /factories
       - If factories returned: onComplete() → skip wizard
       - If no factories: Go to Step 1 (subscriptions)
     - If invalid/expired:
       - Clear localStorage
       - Show Step 0 (login)
  3. If not found:
     - Show Step 0 (login)


Step 0: Authentication
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Display "Login with Microsoft" button
  - handleLogin():
      1. POST /auth/login → {login_url, flow_id, poll_url}
      2. window.open(login_url, '_blank') → OAuth popup
      3. setInterval polling GET /auth/poll/{flow_id} every 2 seconds
      4. On complete: localStorage.setItem('x_session_token', response.session_token)
      5. Proceed to Step 1
  - Also listen for postMessage from auth popup (fast-path)


Step 1: Select Subscription
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Fetch: GET /subscriptions
  - Display list of subscriptions
  - handleSubSelect(sub):
      1. setSelectedSub(sub)
      2. setStep(2)
      3. fetchFactories(sub.subscription_id)


Step 2: Select Factory
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - fetchFactories(subId):
      POST /subscriptions/factories with [subId]
  - Display list of factories (shows is_synced status)
  - handleFactorySelect(factory):
      1. setSelectedFactory(factory)
      2. setStep(3) → show "Syncing..." spinner
      3. POST /discovery/sync {
           subscription_ids: [selectedSub.subscription_id],
           factory_names: [factory.factory_name],
           factory_resource_groups: {[factory.factory_name]: factory.resource_group},
           force_refresh: true
         }
      4. On success: wait 1.5s, setStep(4)
      5. On error: show error, revert to Step 2


Step 3: Syncing (Loading State)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Display "Syncing {factory.factory_name}..." with spinner
  - Wait for sync to complete


Step 4: Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  - Display "Ready! Workspace synced" with checkmark
  - Call onComplete() callback
  - MainWorkspace.jsx receives callback and sets workspaceReady=true
```

#### Critical Problem: No Factory Selection Caching

**Issue:** The frontend does NOT persist factory selection between page reloads.

```javascript
// In MainWorkspace.jsx
const [workspaceReady, setWorkspaceReady] = useState(false);  // ← NOT persisted!

if (!workspaceReady) {
  return <SetupWizard onComplete={() => setWorkspaceReady(true)} />;
}
```

**Impact:**
1. User authenticates, selects subscription, selects factory, syncs
2. Page reloads (F5, server crash, etc.)
3. SetupWizard shows again
4. User must re-authenticate (session_token in localStorage is valid, but workspaceReady is lost)
5. Actually, on Step 0, the code checks localStorage and calls GET /factories
6. If factories found, skips to workspace without re-syncing

**Workaround Currently in Place:**
```javascript
// On SetupWizard mount, check for cached session
if (localStorage.getItem('x_session_token')) {
  const { data } = await apiClient.get('/factories');
  if (data.factories && data.factories.length > 0) {
    onComplete();  // Skip entire wizard
    return;
  }
}
```

So the system DOES auto-load the workspace if a factory was synced before. However, this relies on the backend having that factory in the repository, which is only in-memory.

### 1.7 Session Flow Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION & FACTORY FLOW                            │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│         FRONTEND (React)                  │
│  MainWorkspace.jsx                        │
│    ├─ workspaceReady (state)              │
│    ├─ selectedModel (state)               │
│    └─ Shows: SetupWizard OR Workspace     │
│                                            │
│  SetupWizard.jsx                          │
│    ├─ step (state: 0-4)                   │
│    ├─ x_session_token (localStorage)      │
│    └─ API calls to /auth, /subscriptions  │
│                                            │
│  Sidebar.jsx                              │
│    ├─ selectedModel (prop)                │
│    ├─ sessionInfo (from /auth/session)    │
│    └─ factories (from GET /factories)     │
└──────────────────┬───────────────────────┘
                   │ HTTP requests with
                   │ X-Session-Token header
                   │
┌──────────────────▼───────────────────────┐
│    BACKEND (FastAPI)                     │
│                                           │
│  auth.py router (:8000/api/v1)           │
│    POST  /auth/login                     │
│    GET   /auth/poll/{flow_id}            │
│    GET   /auth/session                   │
│    POST  /auth/logout                    │
│                                           │
│  discovery.py router (:8000/api/v1)      │
│    GET   /subscriptions                  │
│    POST  /subscriptions/factories        │
│    POST  /discovery/sync                 │
│    GET   /factories                      │
│    GET   /factories/{name}/summary       │
│                                           │
│  CallbackHandler (:8100)                 │
│    GET   http://localhost:8100/...       │ ← OAuth redirect
│      (catches redirect, exchanges code)   │
└──────────────────┬───────────────────────┘
                   │ ARM API calls with
                   │ Bearer {access_token}
                   │
┌──────────────────▼───────────────────────┐
│    Azure ARM API                          │
│                                           │
│  GET /subscriptions                      │
│  GET /subscriptions/{sub}/providers/     │
│      Microsoft.DataFactory/factories      │
└──────────────────────────────────────────┘

In-Memory State:
┌──────────────────────────────────────────┐
│  SessionStore (_session_store)            │
│    ├─ _pending[state] → PKCE flow        │
│    ├─ _sessions[token] → PieSession      │
│    └─ _lock (threading)                   │
│                                            │
│  MetadataRepository                       │
│    ├─ factories_by_name                   │
│    ├─ subscriptions by tenant              │
│    └─ last_refreshed_at timestamps        │
│                                            │
│  KnowledgeGraph (per tenant)              │
│    ├─ nodes: pipelines, datasets, etc.   │
│    ├─ edges: dependencies                 │
│    └─ audit engines                       │
└──────────────────────────────────────────┘
```

---

## Section 2: AI API Integration

### 2.1 AI Provider Architecture

The system supports multiple LLM providers with a pluggable architecture. Each provider implements a common interface.

#### Supported LLM Providers

| Provider | SDK | Authentication | Default Model | Best For |
|----------|-----|---|---|---|
| **Mock** | deterministic | None | N/A | Offline testing, demos |
| **Google Gemini** | google-generativeai | `google_api_key` | gemini-2.0-flash | Fast responses, free tier |
| **Azure OpenAI** | azure.ai.inference | `api_key` + `azure_endpoint` | gpt-4o-mini | Enterprise Azure users |
| **OpenAI** | openai | `api_key` | gpt-4o-mini | Standard OpenAI users |
| **NVIDIA NIM** | openai (compatible) | `nvidia_api_key` | meta/llama-3.1-70b-instruct | On-prem deployments |

#### Provider Configuration

**File:** `src/pie/ai/models.py`

```python
class LLMConfig(BaseModel):
    provider: LLMProviderType              # Which provider to use
    model: str = "gpt-4o-mini"             # Model name (provider-specific)
    temperature: float = 0.1                # Low temperature for deterministic responses
    max_tokens: int = 2000                  # Max output length
    
    # Generic API auth
    api_key: str | None                    # Used by most providers
    endpoint: str | None                   # Optional base URL
    
    # Azure-specific
    azure_endpoint: str | None             # Azure OpenAI endpoint URL
    api_version: str | None                # API version
    
    # Provider-specific keys
    google_api_key: str | None             # Google Gemini
    nvidia_api_key: str | None             # NVIDIA NIM
```

### 2.2 Provider Implementation

**File:** `src/pie/ai/providers.py`

#### Base Class
```python
class BaseLLMProvider(ABC):
    def complete(self, prompt: str, system_prompt: str = "") -> str:
        """Generate complete response synchronously."""
    
    def stream_complete(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        """Stream response tokens one by one."""
```

#### Key Implementations

**1. DeterministicMockLLMProvider** (Offline, Default)
- No external API calls
- Deterministic responses based on prompt keywords
- Handles: Architecture, Deletion Impact, Code Gen, Discovery
- Streams words with 0.01s delay for realistic UX
- **Use case:** Development, testing, demos without API keys

**2. GoogleLLMProvider** (Gemini)
```python
import google.generativeai as genai

genai.configure(api_key=config.google_api_key)
model = genai.GenerativeModel(model_name="gemini-2.0-flash")
response = model.generate_content(prompt)
```
- Supports system instructions
- Streaming via `stream=True` parameter
- **Cost:** Free tier available, then pay-per-request
- **Latency:** ~1-2s

**3. AzureAILLMProvider** (Azure OpenAI)
```python
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential

client = ChatCompletionsClient(
    endpoint=config.azure_endpoint,
    credential=AzureKeyCredential(config.api_key)
)
response = client.complete(messages=...)
```
- Requires: Azure OpenAI resource
- **Cost:** Enterprise pricing
- **Latency:** Varies by deployment
- **Advantage:** VNET integration, HIPAA compliance options

**4. NvidiaLLMProvider** (LLaMA 3.1 via NIM)
```python
import openai

client = openai.OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=config.nvidia_api_key
)
response = client.chat.completions.create(
    model="meta/llama-3.1-70b-instruct",
    messages=...
)
```
- OpenAI-compatible API
- **Models:** LLaMA 3.1 70B (free tier available)
- **Cost:** Free tier + pay-per-token
- **Latency:** ~2-3s

#### Provider Factory

```python
def create_llm_provider(config: LLMConfig | None = None) -> BaseLLMProvider:
    config = config or LLMConfig()
    
    if config.provider == LLMProviderType.GEMINI:
        return GoogleLLMProvider(config)
    elif config.provider == LLMProviderType.AZURE_OPENAI:
        return AzureAILLMProvider(config)
    elif config.provider == LLMProviderType.NVIDIA:
        return NvidiaLLMProvider(config)
    elif config.provider == LLMProviderType.OPENAI:
        return OpenAIProvider(config)
    else:  # Default to mock for reliability
        return DeterministicMockLLMProvider(config)
```

### 2.3 API Key Management

#### Backend: Settings Router

**File:** `src/pie/api/routers/settings.py`

```python
@router.get("/settings/keys")
async def get_keys() -> APIKeysPayload:
    """Retrieve current API keys from environment."""
    return APIKeysPayload(
        google=os.getenv("GOOGLE_API_KEY", ""),
        azureEndpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azureKey=os.getenv("AZURE_OPENAI_API_KEY", ""),
        nvidia=os.getenv("NVIDIA_API_KEY", "")
    )

@router.post("/settings/keys")
async def save_keys(payload: APIKeysPayload):
    """Save API keys to environment and .env file."""
    env_updates = {
        "GOOGLE_API_KEY": payload.google,
        "AZURE_OPENAI_ENDPOINT": payload.azureEndpoint,
        "AZURE_OPENAI_API_KEY": payload.azureKey,
        "NVIDIA_API_KEY": payload.nvidia
    }
    
    # Update process environment (immediate)
    for k, v in env_updates.items():
        if v:
            os.environ[k] = v
    
    # Persist to .env file (naive append - no deduplication!)
    try:
        with open(".env", "a") as f:
            for k, v in env_updates.items():
                if v:
                    f.write(f"\n{k}={v}\n")
    except Exception:
        pass
    
    return {"status": "ok"}
```

**Issues:**
- ❌ API keys read/written as plaintext
- ❌ HTTP transmission (should be HTTPS only)
- ❌ `.env` file stored in repo root (security risk if committed)
- ❌ Naive append to `.env` with no deduplication (causes duplicates)

#### Frontend: Settings Modal

**File:** `frontend/src/components/Sidebar/SettingsModal.jsx`

```javascript
export default function SettingsModal({ isOpen, onClose }) {
  const [keys, setKeys] = useState({
    google: '',
    azureEndpoint: '',
    azureKey: '',
    nvidia: ''
  });
  
  const fetchKeys = async () => {
    const { data } = await apiClient.get('/settings/keys');
    setKeys(data);  // Load current keys from backend
  };
  
  const handleSave = async () => {
    await apiClient.post('/settings/keys', keys);  // Save to backend
    // Backend updates os.environ immediately
  };
}
```

**User Flow:**
1. Click Settings icon in Sidebar
2. SettingsModal opens (fetches current keys)
3. User enters/updates API keys
4. Click "Save Keys"
5. POST /settings/keys sends to backend
6. Backend updates `os.environ` (immediate effect)
7. Backend appends to `.env` file (persists across restarts)
8. Next AI query uses new keys

### 2.4 Intent Classification & Routing

**File:** `src/pie/ai/router.py`

```python
class QueryIntentRouter:
    """Deterministic keyword-based intent classification."""
    
    def classify_intent(self, query: str) -> QueryIntent:
        q_lower = query.lower()
        
        # Keyword-based classification (order matters)
        if any(k in q_lower for k in ["delete", "remove", "what if", "blast radius"]):
            return QueryIntent.IMPACT
        elif any(k in q_lower for k in ["pyspark", "dbt", "generate code"]):
            return QueryIntent.CODE_GEN
        elif any(k in q_lower for k in ["orphan", "debt", "audit"]):
            return QueryIntent.SECURITY_AUDIT
        elif any(k in q_lower for k in ["find", "search", "csv", "parquet"]):
            return QueryIntent.SEARCH
        elif any(k in q_lower for k in ["debug", "sql query"]):
            return QueryIntent.DEBUGGING
        elif any(k in q_lower for k in ["explain", "overview", "architecture"]):
            return QueryIntent.ARCHITECTURE
        else:
            return QueryIntent.GENERAL
    
    def extract_target_asset(self, query: str) -> str | None:
        """Extract asset name from query by matching against graph nodes."""
        for node_id, node in self.graph.nodes.items():
            if node.name.lower() in query.lower():
                return node.name
        return None
```

**Intent Types:**
| Intent | Keywords | Use Case | Prompt Template |
|--------|----------|----------|-----------------|
| `IMPACT` | delete, remove, what if, blast radius | What-if deletion analysis | IMPACT_ANALYSIS_PROMPT |
| `CODE_GEN` | pyspark, dbt, migrate, modernize | Code generation | IMPACT_ANALYSIS_PROMPT |
| `SECURITY_AUDIT` | orphan, debt, audit, concurrency | Security/compliance audit | Asset audit templates |
| `SEARCH` | find, search, csv, parquet, onprem | Asset discovery | Asset search results |
| `DEBUGGING` | debug, sql query, retry | Technical debugging | Stored proc templates |
| `ARCHITECTURE` | explain, overview, how, architecture | System documentation | ARCHITECTURE_REVIEW_PROMPT |
| `GENERAL` | (default) | General questions | DOCUMENTATION_PROMPT |

### 2.5 AI Reasoning Engine

**File:** `src/pie/ai/engine.py`

```python
class PIEReasoningEngine:
    """Master intelligence layer combining KnowledgeGraph + Intent + LLM."""
    
    def __init__(self, graph: KnowledgeGraph, llm_provider: BaseLLMProvider | None = None):
        self.graph = graph
        self.router = QueryIntentRouter(graph)
        self.context_builder = MultiIntentContextBuilder(graph)
        self.llm = llm_provider or create_llm_provider()
    
    def ask(self, payload) -> ReasoningResponse:
        """Process query and return grounded response."""
        # 1. Parse request
        query = payload.query
        selected_model = (getattr(payload, "model", None) or "mock").lower()
        
        # 2. Load API keys from environment
        load_dotenv(override=True)
        config = LLMConfig()
        config.api_key = os.getenv("OPENAI_API_KEY")
        config.google_api_key = os.getenv("GOOGLE_API_KEY")
        config.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        config.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
        
        # 3. Select provider based on request
        if selected_model == "google-gemini":
            config.provider = LLMProviderType.GEMINI
            self.llm = create_llm_provider(config)
        elif selected_model == "azure-openai":
            config.provider = LLMProviderType.AZURE_OPENAI
            self.llm = create_llm_provider(config)
        elif selected_model == "nvidia-nim":
            config.provider = LLMProviderType.NVIDIA
            self.llm = create_llm_provider(config)
        else:
            self.llm = create_llm_provider(LLMConfig(provider=LLMProviderType.MOCK))
        
        # 4. Classify intent and extract target
        intent = self.router.classify_intent(query)
        target_asset = self.router.extract_target_asset(query)
        
        # 5. Build context based on intent
        prompt_payload = ""
        if intent == QueryIntent.IMPACT and target_asset:
            context = self.context_builder.build_intent_package(target_asset, intent)
            prompt_payload = IMPACT_ANALYSIS_PROMPT.format(asset_name=target_asset, context=context.full_prompt_payload_md)
        # ... other intent handlers ...
        
        # 6. Call LLM provider
        response_text = self.llm.complete(prompt_payload, system_prompt="...")
        
        # 7. Return grounded response
        return ReasoningResponse(
            user_query=query,
            detected_intent=intent,
            target_asset=target_asset,
            response_markdown=response_text,
            cited_assets=[target_asset] if target_asset else [],
            grounding_score=100.0,  # Always 100% for deterministic metadata
            latency_ms=time.time() - start_time
        )
```

### 2.6 AI API Endpoints

**File:** `src/pie/api/routers/ai.py`

#### POST /ai/ask

```
Purpose: Synchronous AI reasoning query
Auth:    None (public endpoint)
Body:    AIAskRequest {
  query: str,
  factory_name: str,
  model: str  # "google-gemini", "azure-openai", "nvidia-nim", or "mock"
}
Returns: AIAskResponse {
  query: str,
  detected_intent: str,
  target_asset: str | null,
  grounding_score: float,
  response_markdown: str,
  latency_ms: float,
  cited_assets: list[str]
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/ai/ask \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What happens if we delete the sales_dataset?",
    "factory_name": "adf-sales-enterprise-prod",
    "model": "azure-openai"
  }'
```

#### GET /ai/chat/stream

```
Purpose: Streaming Server-Sent Events (SSE) real-time response
Auth:    None (public endpoint)
Query:   ?q={query}
Returns: Server-Sent Events stream
  event: metadata
  data: {"intent": "...", "target_asset": "...", "grounding_score": 100.0}
  
  event: token
  data: {"token": "word "}
  
  event: token
  data: {"token": "by "}
  
  event: done
  data: {"status": "COMPLETE"}
```

**Frontend Usage:**
```javascript
const response = await fetch('/api/v1/ai/chat/stream?q=...');
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  // Parse SSE events and update UI
  if (text.includes('event: token')) {
    const token = JSON.parse(text.split('data: ')[1]).token;
    updateChatUI(token);
  }
}
```

#### POST /ai/generate-code

```
Purpose: Generate modernization code (PySpark, dbt, SQL)
Auth:    None (public endpoint)
Body:    CodeGenRequest {
  pipeline_name: str,
  target_framework: str  # "pyspark", "dbt", "sql"
}
Returns: CodeGenResponse {
  pipeline_name: str,
  target_framework: str,
  generated_code: str,
  explanation: str
}
```

### 2.7 Frontend Chat Integration

**File:** `frontend/src/components/Chat/ChatContainer.jsx`

```javascript
export default function ChatContainer({ selectedModel }) {
  const [messages, setMessages] = useState([...]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  
  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    // Add user message to chat
    const userMessage = { id: Date.now(), role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    
    try {
      // Call AI endpoint with selected model
      const response = await apiClient.post('/ai/ask', {
        query: userMessage.content,
        factory_name: 'adf-sales-enterprise-prod',  // Hardcoded!
        model: selectedModel
      });
      
      // Add AI response to chat
      const aiMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.data.response_markdown
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      // Error handling...
    } finally {
      setLoading(false);
    }
  };
}
```

**Issue:** `factory_name` is hardcoded to `'adf-sales-enterprise-prod'` - should be dynamic based on selected factory.

### 2.8 Model Selection

**File:** `frontend/src/layouts/MainWorkspace.jsx`

```javascript
export default function MainWorkspace() {
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [selectedModel, setSelectedModel] = useState('azure-openai');  // ← Default
  
  return (
    <>
      <Sidebar selectedModel={selectedModel} setSelectedModel={setSelectedModel} />
      <ChatContainer selectedModel={selectedModel} />
    </>
  );
}
```

**Current Behavior:**
- Default model: `'azure-openai'`
- User can change via Sidebar dropdown
- Selection NOT persisted (lost on page refresh)
- Options: azure-openai, google-gemini, nvidia-nim

---

## Section 3: Environment Configuration

### 3.1 Configuration Files

#### .env.example
Located at project root, template for all available variables:

```bash
# Auth Strategy
PIE_AUTH_MODE=default

# Azure Credentials
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=

# Azure Scope Defaults
AZURE_SUBSCRIPTION_ID=
AZURE_RESOURCE_GROUP=
AZURE_FACTORY_NAME=

# AI Services (Reserved for Spikes 4 & 5)
AZURE_AI_FOUNDRY_ENDPOINT=
AZURE_AI_FOUNDRY_KEY=
AZURE_AI_FOUNDRY_MODEL=gpt-4o-mini
AZURE_AI_SEARCH_ENDPOINT=
AZURE_AI_SEARCH_KEY=

# Logging
PIE_LOG_LEVEL=INFO
PIE_OUTPUT_DIR=output
```

#### src/.env
**SECURITY ALERT:** Actual secrets committed to repo!

```
GOOGLE_API_KEY=AIzaSyBvL8-fERxSiSdYd1oMz3ERU8mpEadCQzk
NVIDIA_API_KEY=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
```

### 3.2 Environment Loading

**In AI Engine:**
```python
from dotenv import load_dotenv

# Load .env when processing query
load_dotenv(override=True)

config = LLMConfig()
config.google_api_key = os.getenv("GOOGLE_API_KEY")
config.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
config.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
```

**In Settings Router:**
```python
# Get current env values
return APIKeysPayload(
    google=os.getenv("GOOGLE_API_KEY", ""),
    azureEndpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    azureKey=os.getenv("AZURE_OPENAI_API_KEY", ""),
    nvidia=os.getenv("NVIDIA_API_KEY", "")
)

# Update env and persist
os.environ[k] = v  # Immediate
with open(".env", "a") as f:
    f.write(f"\n{k}={v}\n")  # Persist
```

---

## Section 4: Critical Issues & Findings

### Issue #1: Factory Selection Not Properly Cached ⚠️ HIGH

**Problem:**
- Frontend `workspaceReady` state not persisted to localStorage
- On page refresh, SetupWizard re-appears even if factory was already synced
- Backend repository is in-memory, lost on server restart

**Current Workaround:**
- On SetupWizard mount, checks localStorage for `x_session_token`
- Calls `GET /factories` to see if any factories synced
- If found, skips wizard and loads workspace
- But only works if server hasn't restarted

**Impact:** 
- Poor UX - repeated wizard steps
- No persistence across server restarts

**Recommendation:**
- Persist `workspaceReady` + `selectedFactory` to localStorage
- Implement persistent factory cache (database or Redis)
- Validate cached factory still exists before loading

### Issue #2: API Keys Stored in Plain Text ⚠️ CRITICAL

**Problem:**
- Real API keys committed to `src/.env` in public repo
- Keys sent via HTTP (not HTTPS)
- Keys stored plaintext in filesystem
- Backend naively appends to `.env` file (causes duplicates)

**Security Risks:**
- Keys exposed if repo leaked
- Man-in-the-middle intercept of settings requests
- No encryption at rest

**Recommendation:**
- Use Azure Key Vault for production
- Remove `.env` from git (add to `.gitignore`)
- Implement HTTPS only for settings endpoints
- Use environment variables only (not .env file)

### Issue #3: Hardcoded Factory Name in Chat ⚠️ MEDIUM

**Problem:**
```javascript
// In ChatContainer.jsx
const response = await apiClient.post('/ai/ask', {
  query: userMessage.content,
  factory_name: 'adf-sales-enterprise-prod',  // ← HARDCODED!
  model: selectedModel
});
```

**Impact:**
- Chat queries always target same factory
- Multi-factory support broken
- No context switching

**Recommendation:**
- Pass selected factory from MainWorkspace to ChatContainer
- Store factory selection in useState + localStorage

### Issue #4: No PKCE State Cleanup ⚠️ MEDIUM

**Problem:**
- `_pending_states` dict grows with each login attempt
- Only cleaned up on successful callback or 10-min expiry
- No periodic cleanup of old entries

**Impact:**
- Memory leak over time
- Could OOM on high-traffic deployments

**Recommendation:**
- Implement TTL-based cleanup of expired PKCE states
- Use garbage collection or Redis with auto-expiry

### Issue #5: Settings Modal Loads Keys on Every Open ⚠️ LOW

**Problem:**
```javascript
useEffect(() => {
  if (isOpen) {
    fetchKeys();  // Always refetch from backend
  }
}, [isOpen]);
```

**Impact:**
- Extra API call each time modal opens
- No caching of values

**Recommendation:**
- Cache keys in SettingsModal state or useContext
- Only refetch if explicitly requested

### Issue #6: Error Handling in AI Pipeline Missing ⚠️ MEDIUM

**Problem:**
- No timeout on LLM provider calls
- No fallback if provider unreachable
- Frontend shows generic error message

**Impact:**
- Long hangs if API unreachable
- No graceful degradation

**Recommendation:**
- Add timeout to LLM client calls (e.g., 30s)
- Implement fallback to mock provider on error
- Show user-friendly error messages

### Issue #7: Factory Selection Re-asks Logic Unclear ⚠️ MEDIUM

**Problem:**
- Logic for "should show factory selection again" scattered:
  - Hardcoded check for "GET /factories returns data"
  - No explicit cache invalidation
  - No "Change Factory" button in workspace

**Impact:**
- User can't switch factories without re-auth
- Confusing UX

**Recommendation:**
- Add "Change Factory" button in Sidebar
- Implement explicit cache invalidation endpoint
- Clear separation of concerns

---

## Section 5: Architecture Diagrams

### 5.1 Complete Authentication Sequence

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     OAUTH2 PKCE AUTHENTICATION SEQUENCE                      │
└──────────────────────────────────────────────────────────────────────────────┘

Time │ Frontend             │ Backend API     │ Callback Server   │ Microsoft
     │ (React/Browser)      │ (:8000)         │ (:8100)           │ (Entra ID)
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T1 │ Click "Login"        │                 │                   │
     │ POST /auth/login     │                 │                   │
     ├──────────────────────────────────────→ │                   │
     │                      │ Generate PKCE   │                   │
     │                      │ params, state   │                   │
     │                      │ Return          │                   │
     │                      │ login_url,      │                   │
     │ ← response           │ flow_id         │                   │
     │                      │ ←────────────────                   │
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T2 │ window.open(         │                 │                   │
     │   login_url)         │                 │                   │
     │ User signs in        │                 │                   │
     │                      │                 │                   │
     │                      │                 │                   │ Login form
     │                      │                 │ ←←←←←←←←←←←←←←←←│
     │                      │                 │ User enter creds  │
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T3 │                      │                 │                   │
     │                      │                 │ ← Redirect        │
     │                      │                 │ GET :8100?code=.. │
     │                      │                 │ &state=...        │
     │                      │                 │ ←←←←←←←←←←←←←←←←│
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T4 │                      │                 │ Exchange code     │
     │                      │                 │ for token         │
     │                      │                 ├────────────────────────────────→
     │                      │                 │ POST /oauth2/      │
     │                      │                 │   v2.0/token      │
     │                      │                 │ (with code_verifier)
     │                      │                 │ ←←←←←←←←←←←←←←←←│
     │                      │                 │ Receive:          │
     │                      │                 │ - access_token    │
     │                      │                 │ - id_token        │
     │                      │                 │ - expires_in      │
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T5 │                      │                 │ Create session    │
     │                      │                 │ Decode JWTs       │
     │                      │                 │ Extract claims    │
     │                      │                 │ Save to           │
     │                      │                 │ SessionStore      │
     │                      │                 │ Render HTML with  │
     │                      │                 │ session_token     │
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T6 │ postMessage from     │                 │ (auto-closing)    │
     │ auth popup           │                 │                   │
     │ OR continue polling  │                 │                   │
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T7 │ Poll                 │                 │                   │
     │ GET /auth/poll/      │                 │                   │
     │   {flow_id}          │                 │                   │
     ├──────────────────────────────────────→ │                   │
     │                      │ Check           │                   │
     │                      │ _flows[flow_id] │                   │
     │ ← {status: complete, │ status          │                   │
     │    session_token}    │ ←────────────────                   │
─────┼──────────────────────┼─────────────────┼───────────────────┼────────────
  T8 │ Save to localStorage │                 │                   │
     │ x_session_token      │                 │                   │
     │ Proceed to factory   │                 │                   │
     │ selection            │                 │                   │
     └──────────────────────┴─────────────────┴───────────────────┴────────────
```

### 5.2 Factory Discovery & Sync Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     FACTORY DISCOVERY & SYNC FLOW                            │
└──────────────────────────────────────────────────────────────────────────────┘

Frontend Wizard      │ Backend API         │ MetadataRepository  │ Azure ARM
                    │                     │                     │
Step 1: Subscriptions
─────────────────────┼─────────────────────┼─────────────────────┼──────────
GET /subscriptions   │                     │                     │
(with session token) │                     │                     │
    ─────────────────→ Check session       │                     │
                    │ If authenticated:    │                     │
                    │   Call ARM           │                     │
                    │     ─────────────────────────────────────→ │
                    │                     │                     │ GET /subscriptions
                    │                     │                     │
                    │ ←─────────────────────────────────────────
                    │                     │                     │
    ←──── Return 5 subscriptions ─────────────────────────────
    
Step 2: List Factories
─────────────────────┼─────────────────────┼─────────────────────┼──────────
Select subscription  │                     │                     │
    ─────────────────→ POST /subscriptions/factories
                    │ For each subscription:
                    │   - Call ARM API    │                     │
                    │     ─────────────────────────────────────→ │
                    │                     │ GET /subscriptions/  │
                    │                     │ {sub_id}/providers/  │
                    │                     │ DataFactory/factories│
                    │                     │                     │
                    │                     │ ←─────────────────────
                    │   - Check cache     │
                    │     ─────────────────→ is_synced = ?       │
                    │                     │ Check repo for       │
                    │   - Get timestamp   │ factory_name         │
                    │     ─────────────────→ last_refreshed_at   │
                    │ ←──────────────────────────────────────────
    ←──── Return factories with is_synced flag ─────────────────

Step 3: Sync Factory
─────────────────────┼─────────────────────┼─────────────────────┼──────────
Select factory      │                     │                     │
    ─────────────────→ POST /discovery/sync
                    │ For each factory:    │                     │
                    │   - Call ARM         │                     │
                    │     ─────────────────────────────────────→ │
                    │                     │                     │ GET /subscriptions
                    │                     │                     │ /{sub}/resourceGroups
                    │                     │                     │ /{rg}/providers/
                    │                     │                     │ DataFactory/{name}
                    │                     │                     │
                    │                     │                     │ GET .../pipelines
                    │                     │                     │
                    │                     │                     │ GET .../datasets
                    │                     │                     │
                    │                     │                     │ GET .../linkedservices
                    │                     │                     │
                    │ ←─────────────────────────────────────────
                    │ Parse & normalize   │                     │
                    │   ─────────────────→ Store in-memory      │
                    │                     │ Build KnowledgeGraph│
                    │                     │ Update timestamp    │
                    │ ←───────────────────
    ←──────────────── Return sync results ──────────────────────

Step 4: Workspace Ready
─────────────────────┼─────────────────────┼─────────────────────┼──────────
Workspace loads     │                     │                     │
GET /factories      │                     │                     │
(with session token)│                     │                     │
    ─────────────────→ repo.list_factories │                     │
                    │ ←──────────────────→ Return synced        │
    ←──────────────── Show sidebar with active factory ────────
```

### 5.3 AI Query Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      AI QUERY PROCESSING PIPELINE                            │
└──────────────────────────────────────────────────────────────────────────────┘

User Input (ChatContainer)
         │
         ├─→ "What happens if we delete sales_dataset?"
         │   selectedModel: "azure-openai"
         │
    POST /ai/ask {query, factory_name, model}
         │
         ▼
┌─────────────────────────────────────────┐
│    PIEReasoningEngine.ask()              │
│                                         │
│  1. Load env vars (.env)                │
│     ├─ GOOGLE_API_KEY                   │
│     ├─ AZURE_OPENAI_ENDPOINT            │
│     ├─ AZURE_OPENAI_API_KEY             │
│     └─ NVIDIA_API_KEY                   │
│                                         │
│  2. Route model                         │
│     "azure-openai" → AZURE_OPENAI       │
│     └─ Create LLMConfig                 │
│     └─ Create AzureAILLMProvider        │
│                                         │
│  3. Classify intent                     │
│     QueryIntentRouter.classify_intent() │
│     "delete" keyword → IMPACT           │
│                                         │
│  4. Extract target asset                │
│     Router.extract_target_asset()       │
│     → "sales_dataset"                   │
│     └─ Match against graph nodes        │
│                                         │
│  5. Build context                       │
│     MultiIntentContextBuilder           │
│     └─ Locate asset in graph            │
│     └─ Trace downstream consumers       │
│     └─ Build prompt context (MD)        │
│                                         │
│  6. Generate prompt                     │
│     intent == IMPACT                    │
│     → IMPACT_ANALYSIS_PROMPT template   │
│     │ format(asset_name, context)       │
│     └─→ "## Asset Deletion Analysis     │
│         Target: sales_dataset           │
│         Downstream: [...]               │
│                                         │
│  7. Call LLM provider                   │
│     llm_provider.complete(prompt)       │
└─────────────────────────────────────────┘
         │
    ┌────┴────────────────┬──────────────┬──────────────┐
    │                     │              │              │
    ▼                     ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Azure OpenAI  │  │ Google Gemini│ │NVIDIA NIM    │ │Mock Provider │
│              │  │              │ │              │ │ (fallback)   │
│POST endpoint │  │genai SDK     │ │OpenAI compat │ │Deterministic │
│with Bearer   │  │with api_key  │ │with api_key  │ │responses     │
└──────────────┘  └──────────────┘ └──────────────┘ └──────────────┘
    │                 │                  │                │
    │ (HTTP calls     │ (HTTP calls       │ (HTTP calls    │ (local)
    │  with timeout)  │  with timeout)    │  with timeout) │
    │                 │                  │                │
    └─────────────────┴──────────────────┴────────────────┘
                    │
                    ▼
         [LLM Response Received]
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
Parse response               Handle error
Generate tokens             → Use mock provider
                           → Return error response
    │
    ▼
┌─────────────────────────────────┐
│   ReasoningResponse             │
│  - response_markdown            │
│  - detected_intent: "IMPACT"    │
│  - target_asset: "sales_dataset"│
│  - cited_assets: [...]          │
│  - grounding_score: 100.0       │
│  - latency_ms: 1234             │
└─────────────────────────────────┘
         │
    200 OK response
         │
    ChatContainer receives
         │
         ▼
    Append to messages[]
    Display in chat UI
```

---

## Summary & Recommendations

### What's Working Well ✅
1. **OAuth2 PKCE flow** - Secure, no password in app, industry standard
2. **Intent classification** - Simple but effective keyword-based routing
3. **Pluggable LLM providers** - Easy to add new providers or switch
4. **Multi-tenant support** - Sessions scoped to tenant_id
5. **Graph-based context** - Rich metadata for grounding AI responses

### What Needs Fixing 🔧
1. **Persistent factory cache** - Add localStorage + database persistence
2. **API key security** - Use Azure Key Vault instead of .env file
3. **Session persistence** - Migrate SessionStore to Redis for HA
4. **Model selection persistence** - Save to localStorage
5. **Hardcoded factory name** - Make dynamic based on selection
6. **PKCE state cleanup** - Implement TTL-based garbage collection
7. **Error handling** - Add timeouts and fallbacks in AI pipeline
8. **HTTPS requirement** - Enforce for production deployment

### Architecture is Solid 💪
- Clean separation: Auth → Discovery → AI Pipeline
- Dependency injection via FastAPI Depends()
- Thread-safe session store
- Async/await for scalability
- SSE streaming for real-time chat

The codebase demonstrates good engineering practices with clear intent, but needs production hardening around state persistence, security, and error handling.

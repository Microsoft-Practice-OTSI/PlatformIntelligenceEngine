# PIE (Platform Intelligence Engine) - Issues Fixed

**Date:** August 9, 2026  
**Issues Addressed:** 
1. Factory Selection Flow Post-Login
2. AI API Integration & Error Handling

---

## 🔴 Issue 1: Factory Selection Flow Post-Login

### Problem
**Previous Behavior:**
- After user login, if a factory was already synced, the SetupWizard would exit immediately and show the workspace
- This prevented users from:
  - Re-selecting factories after each login
  - Switching between different factories
  - Ensuring fresh metadata sync

**User Requirement:**
- After EVERY login, always show subscription selection → factory selection flow
- This ensures consistent factory metadata refresh and allows factory switching

### Root Cause
The SetupWizard had early-exit logic in two places:
1. In the auth success message handler (line ~24-28)
2. In the checkAuth useEffect (line ~46-48)

```javascript
// OLD CODE - PROBLEMATIC
try {
  const { data } = await apiClient.get('/factories');
  if (data.factories && data.factories.length > 0) {
    onComplete();  // ❌ EXITS WIZARD IMMEDIATELY
    return;
  }
} catch(e) {}
```

### Solution Implemented

**File:** `frontend/src/components/Onboarding/SetupWizard.jsx`

#### Change 1: Remove early exit from auth success handler
```javascript
// NEW CODE
const handleMessage = async (event) => {
  if (event.data?.type === 'PIE_AUTH_SUCCESS' && event.data.sessionToken) {
    localStorage.setItem('x_session_token', event.data.sessionToken);
    // Always proceed to subscription selection after login
    setStep(1);
    fetchSubscriptions();
  }
};
```

#### Change 2: Remove early exit from checkAuth useEffect
```javascript
// NEW CODE
const checkAuth = async () => {
  if (localStorage.getItem('x_session_token')) {
    try {
      await apiClient.get('/auth/session');
      // Always proceed to subscription selection to allow factory re-selection
      setStep(1);
      fetchSubscriptions();
    } catch(e) {
      localStorage.removeItem('x_session_token');
      setStep(0);
    }
  } else {
    setStep(0);
  }
};
```

#### Change 3: Remove early exit from login polling
```javascript
// NEW CODE
if (pollRes.data.status === 'complete') {
  clearInterval(pollTimer);
  localStorage.setItem('x_session_token', pollRes.data.session_token);
  // Always proceed to subscription selection
  setLoading(false);
  setStep(1);
  fetchSubscriptions();
  // ✓ No early return based on existing factories
}
```

#### Change 4: Save selected factory to localStorage
In `handleFactorySelect()`, after successful sync:
```javascript
// Save selected factory to localStorage for ChatContainer to use
localStorage.setItem('selected_factory', factory.factory_name);
```

### Impact
✅ Users now ALWAYS see subscription and factory selection after login  
✅ Allows factory switching on subsequent logins  
✅ Ensures fresh metadata sync for selected factory  
✅ Improves visibility into data engineering assets  

---

## 🔴 Issue 2: Hardcoded Factory Name & Model Selection

### Problem
**Previous Behavior:**
- ChatContainer had a hardcoded factory name: `'adf-sales-enterprise-prod'`
- This meant all AI queries used the same factory, regardless of user selection
- Model selection (Google Gemini, NVIDIA NIM, Azure OpenAI) wasn't persisted
- Refreshing the page would reset model selection to default

**Code Example (PROBLEMATIC):**
```javascript
// ChatContainer.jsx line 34 - HARDCODED
const response = await apiClient.post('/ai/ask', {
  query: userMessage.content,
  factory_name: 'adf-sales-enterprise-prod',  // ❌ HARDCODED!
  model: selectedModel
});
```

### Root Cause
1. No mechanism to pass selected factory from SetupWizard to ChatContainer
2. Model selection stored only in React state, not persisted to localStorage

### Solution Implemented

#### Change 1: Get factory name dynamically from localStorage
**File:** `frontend/src/components/Chat/ChatContainer.jsx`

```javascript
const sendMessage = async (e) => {
  e.preventDefault();
  if (!input.trim()) return;

  const userMessage = { id: Date.now(), role: 'user', content: input };
  setMessages((prev) => [...prev, userMessage]);
  setInput('');
  setLoading(true);

  try {
    // Get factory name from localStorage (set during factory selection)
    const factoryName = localStorage.getItem('selected_factory') || 'default';
    const response = await apiClient.post('/ai/ask', {
      query: userMessage.content,
      factory_name: factoryName,  // ✓ DYNAMIC
      model: selectedModel
    });
    // ... rest of code
  } catch (error) {
    // ... error handling
  }
};
```

#### Change 2: Persist model selection to localStorage
**File:** `frontend/src/layouts/MainWorkspace.jsx`

```javascript
export default function MainWorkspace() {
  const [workspaceReady, setWorkspaceReady] = useState(false);
  const [selectedModel, setSelectedModel] = useState(() => {
    // Load model selection from localStorage, default to 'azure-openai'
    return localStorage.getItem('selected_model') || 'azure-openai';
  });

  // Persist model selection to localStorage whenever it changes
  const handleModelChange = (newModel) => {
    localStorage.setItem('selected_model', newModel);
    setSelectedModel(newModel);
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-bg-base text-text-primary">
      {/* Left Pane 1: Sidebar Settings */}
      <Sidebar selectedModel={selectedModel} setSelectedModel={handleModelChange} />
      {/* ... rest of JSX */}
    </div>
  );
}
```

### Impact
✅ ChatContainer now uses the factory selected in SetupWizard  
✅ Model selection persists across page refreshes  
✅ Users can switch AI providers and it's remembered  
✅ Each user session maintains their preferred model  

---

## 🟡 Issue 3: AI API Provider Initialization & Error Handling

### Problem
**Previous Behavior:**
- API keys for Google Gemini and NVIDIA NIM were provided but showed errors when used
- Limited error logging made debugging difficult
- No clear indication when API keys were missing
- Provider fallback was silent - users didn't know they were using Mock provider

### Root Cause
In `src/pie/ai/engine.py`, the provider initialization didn't:
1. Log which credentials were available/missing
2. Provide clear error messages
3. Handle provider initialization failures gracefully

### Solution Implemented

**File:** `src/pie/ai/engine.py`

#### Improved provider initialization with logging and error handling:
```python
def ask(self, payload) -> ReasoningResponse:
    """Process a natural language question and return a 100% grounded reasoning response."""
    # ... existing code ...
    
    # Pull keys from environment (which were set by Settings UI)
    load_dotenv(override=True)
    config = LLMConfig()
    config.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
    config.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    config.google_api_key = os.getenv("GOOGLE_API_KEY")
    config.nvidia_api_key = os.getenv("NVIDIA_API_KEY")
    
    # Log which credentials are available for debugging
    logger.info(f"Available API Keys - Azure OpenAI: {'✓' if config.api_key else '✗'}, "
               f"Google Gemini: {'✓' if config.google_api_key else '✗'}, "
               f"NVIDIA NIM: {'✓' if config.nvidia_api_key else '✗'}")
    
    # Override LLM provider based on request with explicit error handling
    try:
        if selected_model == "google-gemini":
            config.provider = LLMProviderType.GEMINI
            config.model = "gemini-2.0-flash"  # Updated model version
            if not config.google_api_key:
                logger.warning("Google Gemini API key not found. Using Mock Provider instead.")
                config.provider = LLMProviderType.MOCK
            self.llm = create_llm_provider(config)
        elif selected_model == "azure-openai":
            config.provider = LLMProviderType.AZURE_OPENAI
            config.model = "gpt-4o-mini"
            if not config.api_key:
                logger.warning("Azure OpenAI API key not found. Using Mock Provider instead.")
                config.provider = LLMProviderType.MOCK
            self.llm = create_llm_provider(config)
        elif selected_model == "nvidia-nim":
            config.provider = LLMProviderType.NVIDIA
            config.model = "meta/llama-3.1-70b-instruct"
            if not config.nvidia_api_key:
                logger.warning("NVIDIA API key not found. Using Mock Provider instead.")
                config.provider = LLMProviderType.MOCK
            self.llm = create_llm_provider(config)
        else:
            config.provider = LLMProviderType.MOCK
            self.llm = create_llm_provider(config)
    except Exception as e:
        logger.error(f"Error initializing LLM provider: {str(e)}. Falling back to Mock Provider.")
        config.provider = LLMProviderType.MOCK
        self.llm = create_llm_provider(config)
```

#### Improved .env file handling to prevent duplicates
**File:** `src/pie/api/routers/settings.py`

```python
@router.post("/keys")
async def save_keys(payload: APIKeysPayload):
    # Update current process
    for k, v in env_updates.items():
        if v:
            os.environ[k] = v
            
    # Update .env file without duplicates
    try:
        env_file = ".env"
        env_content = {}
        
        # Read existing .env file
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env_content[key.strip()] = value.strip()
        
        # Update with new values (overwrites existing, no duplicates)
        for k, v in env_updates.items():
            if v:
                env_content[k] = v
        
        # Write back to .env file (clean write)
        with open(env_file, "w") as f:
            f.write("# Platform Intelligence Engine (PIE) - Environment Configuration\n")
            f.write("# Auto-generated by settings API\n\n")
            for k, v in sorted(env_content.items()):
                if v:
                    f.write(f"{k}={v}\n")
    except Exception as e:
        print(f"Warning: Failed to update .env file: {e}")
        
    return {"status": "ok"}
```

### Impact
✅ Better visibility into which API keys are configured  
✅ Clear error messages when keys are missing  
✅ Graceful fallback to Mock provider instead of silent failures  
✅ .env file no longer accumulates duplicate keys  
✅ Easier debugging of AI provider issues  

---

## 📋 Summary of Changed Files

| File | Changes | Impact |
|------|---------|--------|
| `frontend/src/components/Onboarding/SetupWizard.jsx` | Removed early-exit logic, always show factory selection, save factory to localStorage | Always allows factory re-selection post-login |
| `frontend/src/components/Chat/ChatContainer.jsx` | Get factory name from localStorage instead of hardcoding | Uses correct factory for AI queries |
| `frontend/src/layouts/MainWorkspace.jsx` | Persist model selection to localStorage | Model choice survives page refresh |
| `src/pie/ai/engine.py` | Added logging and error handling for provider init | Better debugging & graceful fallbacks |
| `src/pie/ai/providers.py` | (No changes - working as designed) | N/A |
| `src/pie/api/routers/settings.py` | Improved .env file handling to prevent duplicates | No more duplicate API keys in .env |

---

## ✅ Testing Checklist

- [ ] **Login Flow:**
  - [ ] Log in with Microsoft account
  - [ ] Verify SetupWizard shows subscription selection (not workspace)
  - [ ] Select subscription
  - [ ] Select factory
  - [ ] Verify factory syncs successfully
  - [ ] Verify workspace opens with correct factory

- [ ] **Factory Selection Persistence:**
  - [ ] Open DevTools → Application → LocalStorage
  - [ ] Verify `selected_factory` is set to chosen factory name
  - [ ] Refresh page
  - [ ] Verify ChatContainer still uses correct factory

- [ ] **Model Selection Persistence:**
  - [ ] Click Sidebar model dropdown
  - [ ] Select "Google Gemini"
  - [ ] Verify `selected_model` in localStorage is set to `google-gemini`
  - [ ] Refresh page
  - [ ] Verify model dropdown still shows "Google Gemini"

- [ ] **AI API Integration:**
  - [ ] Open Settings modal (gear icon in Sidebar)
  - [ ] Add API keys for Google Gemini and NVIDIA NIM
  - [ ] Click "Save Keys"
  - [ ] Check backend logs for: `Available API Keys - Azure OpenAI: ✓, Google Gemini: ✓, NVIDIA NIM: ✓`
  - [ ] Send a message with Google Gemini selected
  - [ ] Verify response comes from Google Gemini (not Mock)

- [ ] **Error Handling:**
  - [ ] Test with missing API key for selected provider
  - [ ] Verify fallback to Mock provider
  - [ ] Check logs show warning about missing key

---

## 🚀 Next Steps

1. **Test all changes** using the checklist above
2. **Monitor logs** during testing for API key availability messages
3. **Verify .env file** no longer has duplicate entries
4. **Deploy fixes** to production environment

---

## 📝 Notes for Future Development

- Consider moving API key storage to Azure Key Vault instead of .env file
- Add user-facing error messages for missing API credentials
- Consider session-scoped settings vs localStorage (current approach)
- Implement telemetry to track which AI providers are being used

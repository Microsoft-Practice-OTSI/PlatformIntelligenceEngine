"""
Authentication router — Real OAuth2 PKCE browser login using Microsoft's Azure CLI public client.

Architecture:
  - A PERSISTENT HTTP server runs on :8100 for the entire lifetime of PIE.
  - Redirect URI registered with Azure CLI app: http://localhost:8100   (no path)
  - All login flows are tracked by `state` parameter in the callback URL.

Flow:
  1. POST /auth/login         → generate PKCE params, store state→flow mapping, return login_url
  2. User opens login_url     → authenticates → Microsoft redirects to http://localhost:8100?code=&state=
  3. :8100 server catches it  → exchanges code for token → creates PIE session
  4. GET  /auth/poll/{id}     → poll until session_token is ready
  5. GET  /auth/session       → inspect session with X-Session-Token header
  6. POST /auth/logout        → revoke session
"""

import base64
import hashlib
import http.server
import json
import os
import secrets
import threading
import urllib.parse
import urllib.request
import uuid
from typing import Optional

import msal
from fastapi import APIRouter, Header, HTTPException, status

from pie.api.models import SessionInfo
from pie.auth.session_store import get_session_store
from pie.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CLIENT_ID    = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"   # Azure CLI public client
_AUTHORITY    = "https://login.microsoftonline.com/common"
_REDIRECT_URI = "http://localhost:8100"
_SCOPES       = ["openid", "profile", "email", "https://management.azure.com/user_impersonation"]

# ---------------------------------------------------------------------------
# Shared state (module-level singletons)
# ---------------------------------------------------------------------------
# state_key → {flow_id, msal_flow}  (MSAL flow object contains PKCE verifier internally)
_pending_states: dict[str, dict] = {}
_pending_lock   = threading.Lock()

# flow_id → {status, session_token, error, user_id, display_name, tenant_id}
_flows: dict[str, dict] = {}
_flows_lock = threading.Lock()

# The persistent callback server instance
_callback_server: Optional[http.server.HTTPServer] = None
_server_lock = threading.Lock()


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------
def _msal_app() -> msal.PublicClientApplication:
    return msal.PublicClientApplication(client_id=_CLIENT_ID, authority=_AUTHORITY)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_pkce_flow() -> dict:
    """Build a Microsoft authorize URL without requiring network discovery."""
    state = str(uuid.uuid4())
    code_verifier = _b64url(secrets.token_bytes(48))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
    params = {
        "client_id": _CLIENT_ID,
        "response_type": "code",
        "redirect_uri": _REDIRECT_URI,
        "response_mode": "query",
        "scope": " ".join(_SCOPES),
        "state": state,
        "prompt": "select_account",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return {
        "auth_uri": f"{_AUTHORITY}/oauth2/v2.0/authorize?{urllib.parse.urlencode(params)}",
        "state": state,
        "code_verifier": code_verifier,
    }


def _decode_jwt_payload(token: str | None) -> dict:
    if not token or token.count(".") < 2:
        return {}
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except Exception:
        return {}


def _exchange_code_for_token(code: str, code_verifier: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "client_id": _CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _REDIRECT_URI,
            "scope": " ".join(_SCOPES),
            "code_verifier": code_verifier,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{_AUTHORITY}/oauth2/v2.0/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Persistent callback handler — handles every incoming request on :8100
# ---------------------------------------------------------------------------
class _CallbackHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))

        state = params.get("state")
        code  = params.get("code")
        error = params.get("error")

        # --- No state — just a stray browser hit ---
        if not state:
            self._send_html(_error_page("no_state", "Missing state parameter."), 400)
            return

        # --- Look up pending flow by state ---
        with _pending_lock:
            entry = _pending_states.pop(state, None)

        if not entry:
            self._send_html(
                _error_page("invalid_state", "Login session expired or not found. Please start again."), 400
            )
            return

        flow_id    = entry["flow_id"]
        pkce_flow  = entry["pkce_flow"]

        # --- Microsoft returned an error ---
        if error or not code:
            err_desc = params.get("error_description", error or "No code received")
            logger.warning(f"OAuth error for flow {flow_id[:8]}: {err_desc}")
            with _flows_lock:
                _flows[flow_id]["status"] = "error"
                _flows[flow_id]["error"]  = err_desc
            self._send_html(_error_page(error or "no_code", err_desc), 400)
            return

        # --- Exchange code for token using the stored PKCE verifier ---
        logger.info(f"Exchanging code for flow {flow_id[:8]}...")
        try:
            result = _exchange_code_for_token(code=code, code_verifier=pkce_flow["code_verifier"])
        except Exception as exc:
            logger.error(f"MSAL exception for flow {flow_id[:8]}: {exc}", exc_info=True)
            with _flows_lock:
                _flows[flow_id]["status"] = "error"
                _flows[flow_id]["error"]  = str(exc)
            self._send_html(_error_page("token_exchange_failed", str(exc)), 500)
            return

        if "error" in result:
            err_desc = result.get("error_description", result.get("error", "Token exchange failed"))
            logger.error(f"MSAL error for flow {flow_id[:8]}: {err_desc}")
            with _flows_lock:
                _flows[flow_id]["status"] = "error"
                _flows[flow_id]["error"]  = err_desc
            self._send_html(_error_page(result["error"], err_desc), 401)
            return

        # --- Create PIE session ---
        id_claims    = result.get("id_token_claims") or _decode_jwt_payload(result.get("id_token"))
        access_claims = _decode_jwt_payload(result.get("access_token"))
        access_token = result["access_token"]
        expires_in   = result.get("expires_in", 3600)
        tenant_id    = id_claims.get("tid") or access_claims.get("tid") or "unknown"
        user_id      = (id_claims.get("preferred_username")
                        or id_claims.get("upn")
                        or id_claims.get("email")
                        or access_claims.get("preferred_username")
                        or access_claims.get("upn")
                        or access_claims.get("email")
                        or access_claims.get("unique_name")
                        or f"{access_claims.get('oid', 'user')}@unknown")
        display_name = id_claims.get("name") or access_claims.get("name") or user_id

        session = get_session_store().create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            display_name=display_name,
            access_token=access_token,
            expires_in_seconds=expires_in,
        )

        logger.info(f"Session created for flow {flow_id[:8]}: user={user_id} tenant={tenant_id}")

        with _flows_lock:
            _flows[flow_id].update({
                "status":        "complete",
                "session_token": session.session_token,
                "user_id":       user_id,
                "display_name":  display_name,
                "tenant_id":     tenant_id,
            })

        self._send_html(
            _success_page(session.session_token, user_id, display_name, tenant_id), 200
        )

    def _send_html(self, body: str, code: int) -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass   # silence default Apache-style access log


# ---------------------------------------------------------------------------
# Persistent server lifecycle — called from app.py lifespan
# ---------------------------------------------------------------------------
def start_callback_server() -> None:
    """Start the persistent OAuth callback server on :8100. Safe to call multiple times."""
    print(">>> START_CALLBACK_SERVER CALLED <<<")
    global _callback_server
    with _server_lock:
        if _callback_server is not None:
            logger.info("Callback server already running")
            print(">>> CALLBACK SERVER ALREADY RUNNING <<<")
            return   # already running
        try:
            server = http.server.HTTPServer(("127.0.0.1", 8100), _CallbackHandler)
            _callback_server = server
            def run_server():
                print(">>> CALLBACK SERVER THREAD STARTING serve_forever <<<")
                try:
                    server.serve_forever()
                except Exception as e:
                    logger.error(f"Callback server thread crashed: {e}")
                    print(f">>> CALLBACK SERVER THREAD CRASHED: {e} <<<")
                    import traceback
                    traceback.print_exc()
            t = threading.Thread(target=run_server, daemon=True, name="pie-auth-callback-8100")
            t.start()
            # Give it a moment to start
            import time
            time.sleep(0.5)
            logger.info("PIE auth callback server started on http://127.0.0.1:8100")
            print(">>> CALLBACK SERVER STARTED ON PORT 8100 <<<")
        except OSError as exc:
            logger.warning(f"Could not start auth callback server on :8100 — {exc}")
            print(f">>> CALLBACK SERVER FAILED: {exc} <<<")
        except Exception as exc:
            logger.error(f"Unexpected error starting callback server: {exc}")
            print(f">>> CALLBACK SERVER UNEXPECTED ERROR: {exc} <<<")
            import traceback
            traceback.print_exc()


def stop_callback_server() -> None:
    """Gracefully shut down the callback server."""
    global _callback_server
    with _server_lock:
        if _callback_server:
            _callback_server.shutdown()
            _callback_server = None
            logger.info("PIE auth callback server stopped.")


# ---------------------------------------------------------------------------
# 1. Initiate login
# ---------------------------------------------------------------------------
@router.post("/login")
async def initiate_login(tenant: str = "common") -> dict:
    """
    Start a browser-based OAuth2 PKCE login.

    Returns a `login_url`. Open it in your browser and sign in with your Azure account.
    Microsoft redirects to http://localhost:8100, PIE catches it automatically.
    Poll GET /api/v1/auth/poll/{flow_id} every 2 seconds to get your session_token.
    """
    flow_id = str(uuid.uuid4())

    pkce_flow = _build_pkce_flow()
    login_url = pkce_flow["auth_uri"]
    state     = pkce_flow["state"]

    with _flows_lock:
        _flows[flow_id] = {"status": "pending", "session_token": None, "error": None}

    with _pending_lock:
        _pending_states[state] = {"flow_id": flow_id, "pkce_flow": pkce_flow}

    logger.info(f"Login flow {flow_id[:8]} initiated")
    return {
        "flow_id":   flow_id,
        "login_url": login_url,
        "message":   "Open login_url in your browser. Sign in with your Azure account.",
        "poll_url":  f"http://127.0.0.1:8001/api/v1/auth/poll/{flow_id}",
    }


# ---------------------------------------------------------------------------
# 2. Poll for completion
# ---------------------------------------------------------------------------
@router.get("/poll/{flow_id}")
async def poll_login(flow_id: str) -> dict:
    """
    Poll the status of a login flow.
      - pending  → keep polling every 2 seconds
      - complete → use session_token in X-Session-Token header
      - error    → authentication failed
    """
    with _flows_lock:
        entry = _flows.get(flow_id)

    if not entry:
        raise HTTPException(status_code=404, detail="Flow not found or expired.")

    if entry["status"] == "pending":
        return {"status": "pending", "message": "Waiting for browser login to complete..."}

    if entry["status"] == "error":
        return {"status": "error", "message": entry.get("error", "Authentication failed.")}

    return {
        "status":        "complete",
        "session_token": entry["session_token"],
        "user_id":       entry.get("user_id"),
        "display_name":  entry.get("display_name"),
        "tenant_id":     entry.get("tenant_id"),
        "message":       "Authenticated. Use X-Session-Token header in all API calls.",
    }


# ---------------------------------------------------------------------------
# 3. Session inspection
# ---------------------------------------------------------------------------
@router.get("/session", response_model=SessionInfo)
async def get_session(
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> SessionInfo:
    """Inspect the current PIE session."""
    if x_session_token:
        session = get_session_store().get_session(x_session_token)
        if session:
            return SessionInfo(
                authenticated=True,
                tenant_id=session.tenant_id,
                user_id=session.user_id,
                auth_mode=session.auth_mode,
                claims={
                    "display_name":     session.display_name,
                    "token_expires_at": session.token_expires_at.isoformat(),
                    "roles":            ["Reader", "DataEngineer", "Architect"],
                },
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Re-authenticate via POST /api/v1/auth/login",
        )

    return SessionInfo(
        authenticated=False,
        tenant_id="local",
        user_id="local-developer@company.local",
        auth_mode="unauthenticated",
        claims={"note": "POST /api/v1/auth/login to start browser login"},
    )


# ---------------------------------------------------------------------------
# 4. Logout
# ---------------------------------------------------------------------------
@router.post("/logout")
async def logout(
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> dict:
    """Revoke the current PIE session."""
    if x_session_token:
        get_session_store().delete_session(x_session_token)
        return {"status": "logged_out", "message": "Session revoked."}
    return {"status": "no_session", "message": "No active session to revoke."}


# ---------------------------------------------------------------------------
# HTML pages
def _success_page(session_token: str, user_id: str, display_name: str, tenant_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><title>PIE — Login Successful</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    html, body{{width:100%;height:100%;min-height:100vh;overflow:hidden}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
         background:#f8fafc;color:#0f172a;display:flex;align-items:center;
         justify-content:center}}
    .card{{background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;
           padding:44px 36px;max-width:420px;width:90%;text-align:center;
           box-shadow:0 12px 30px -4px rgba(15, 23, 42, 0.08), 0 4px 12px -2px rgba(15, 23, 42, 0.04);
           margin:auto}}
    .icon-wrapper{{width:60px;height:60px;margin:0 auto 18px;border-radius:16px;
                    background:#ecfdf5;border:1px solid #a7f3d0;
                    display:flex;align-items:center;justify-content:center;font-size:26px;color:#059669;font-weight:bold}}
    h1{{font-size:20px;font-weight:700;color:#0f172a;margin-bottom:8px;letter-spacing:-0.4px}}
    .user-name{{color:#0f172a;font-size:16px;font-weight:700;margin-bottom:4px}}
    .user-id{{color:#475569;font-size:13px;font-weight:500;margin-bottom:16px;word-break:break-all}}
    .badge{{display:inline-block;padding:5px 14px;background:#eff6ff;color:#2563eb;
             border:1px solid #bfdbfe;border-radius:20px;font-size:12px;font-weight:600;margin-bottom:20px}}
    .redirect-msg{{color:#334155;font-size:13px;font-weight:500;line-height:1.5;margin-bottom:20px}}
    .btn{{display:inline-block;padding:8px 22px;background:#f8fafc;color:#0f172a;
          border:1px solid #cbd5e1;border-radius:10px;font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s}}
    .btn:hover{{background:#f1f5f9;color:#0f172a;border-color:#94a3b8}}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-wrapper">✓</div>
    <h1>Authenticated Successfully</h1>
    <p class="user-name">{display_name}</p>
    <p class="user-id">{user_id}</p>
    <span class="badge">Session Connected</span>

    <p class="redirect-msg">Returning to Platform Intelligence Engine...<br>This window will close automatically.</p>
    <button class="btn" onclick="window.close()">Close Window</button>
  </div>
  <script>
    // Center popup window on the screen
    try {{
      const w = 560, h = 600;
      const left = Math.max(0, Math.floor((window.screen.availWidth - w) / 2));
      const top = Math.max(0, Math.floor((window.screen.availHeight - h) / 2));
      window.moveTo(left, top);
    }} catch (e) {{}}

    // Notify parent window and auto-close
    try {{
      window.opener?.postMessage({{ type: 'PIE_AUTH_SUCCESS', sessionToken: '{session_token}' }}, '*');
    }} catch (e) {{}}
    setTimeout(() => window.close(), 1200);
  </script>
</body></html>"""


def _error_page(error: str, description: Optional[str]) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><title>PIE — Auth Error</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
         background:#f8fafc;color:#0f172a;display:flex;align-items:center;
         justify-content:center;min-height:100vh}}
    .card{{background:#ffffff;border:1px solid #fee2e2;border-radius:18px;
           padding:40px 44px;max-width:460px;width:90%;text-align:center;
           box-shadow:0 12px 30px -4px rgba(15, 23, 42, 0.08), 0 4px 12px -2px rgba(15, 23, 42, 0.04)}}
    .icon-wrapper{{width:60px;height:60px;margin:0 auto 16px;border-radius:16px;
                    background:#fef2f2;border:1px solid #fecaca;
                    display:flex;align-items:center;justify-content:center;font-size:26px;color:#dc2626;font-weight:bold}}
    h1{{color:#dc2626;font-size:18px;font-weight:700;margin-bottom:8px}}
    p{{color:#64748b;font-size:13px;margin-top:8px;line-height:1.5}}
    code{{background:#f1f5f9;color:#b91c1c;padding:2px 6px;border-radius:4px;font-size:12px}}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-wrapper">✕</div>
    <h1>Authentication Failed</h1>
    <p><code>{error}</code></p>
    <p>{description or ''}</p>
    <p style="margin-top:20px;font-size:12px;color:#94a3b8">
      Start a new login in the PIE application.
    </p>
  </div>
</body></html>"""

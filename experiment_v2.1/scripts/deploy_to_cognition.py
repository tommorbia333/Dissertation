#!/usr/bin/env python3
"""Deploy experiment_v2.1 to Cognition.run via its MCP server.

This is a one-shot OAuth + MCP client. First run opens a browser for OAuth
authorization; subsequent runs reuse a refresh token cached in
~/.config/cognition_deploy/tokens.json.

What it does:
  1. OAuth 2.0 (PKCE) with dynamic client registration against cognition.run.
  2. Bundles every .js file in experiment_v2.1/ (in the same order index.html
     loads them) into a single source string. CSS is inlined as a <style> tag.
     SortableJS is loaded dynamically from CDN at runtime. jsPsych itself is
     provided by Cognition and is NOT bundled.
  3. Calls the Cognition MCP tools `list-tasks` / `create-task` /
     `update-source-code` / `update-task` to push the bundle to a task named
     "Experiment v2.1".
  4. Prints the public participant URL.

How to upload changes to Cognition (from your machine)
-------------------------------------------------------
1. Edit the experiment under `experiment_v2.1/` (the repo layout stays as-is;
   the script flattens and bundles for Cognition’s single-file “source” field).
2. From the repository root, run:
       python3 experiment_v2.1/scripts/deploy_to_cognition.py
   First time: your browser opens for OAuth at cognition.run; approve access.
3. The same command on later runs reuses the refresh token in
   `~/.config/cognition_deploy/tokens.json` (no browser) and updates the task
   you named with `--task-name` (default: "Experiment v2.1").
4. Useful flags: `--reset-auth` (new OAuth), `--dry-run --save-bundle /tmp/b.js`
   (inspect the bundle only).

Usage:
    python3 experiment_v2.1/scripts/deploy_to_cognition.py [--task-name NAME] [--reset-auth]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

COGNITION = "https://www.cognition.run"
AUTH_URL = f"{COGNITION}/oauth/authorize"
TOKEN_URL = f"{COGNITION}/oauth/token"
REGISTER_URL = f"{COGNITION}/oauth/register"
MCP_URL = f"{COGNITION}/mcp"

REPO_ROOT = Path(__file__).resolve().parents[2]
EXP_DIR = REPO_ROOT / "experiment_v2.1"

TOKENS_PATH = Path.home() / ".config" / "cognition_deploy" / "tokens.json"

# Match the load order of index.html (everything except CDN-hosted libs and
# assets/style.css, which are handled separately).
JS_LOAD_ORDER = [
    "src/config.js",
    "stimuli/stories.js",
    "stimuli/comprehension.js",
    "stimuli/event_cards.js",
    "stimuli/cf_probes.js",
    "stimuli/assignments.js",
    "src/utils.js",
    "src/condition.js",
    "src/selection.js",
    "src/data.js",
    "src/tasks/story_reading.js",
    "src/tasks/comprehension.js",
    "src/tasks/ordering.js",
    "src/tasks/pair_scaling.js",
    "src/tasks/counterfactual.js",
    "src/intro.js",
    "src/inter_story.js",
    "src/outro.js",
    "src/main.js",
]

CSS_PATH = "assets/style.css"

# CDN URL for SortableJS (used by the ordering task).
SORTABLE_CDN = "https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"

# Cognition's update-task only allows up to 8.0.2; index.html dev uses 8.2.1.
COGNITION_LIBRARY_VERSION = "8.0.2"

# -----------------------------------------------------------------------------
# OAuth 2.0 (Dynamic Client Registration + PKCE + authorization_code)
# -----------------------------------------------------------------------------


def _http_json(url: str, method: str = "GET", *, headers=None, data=None, form=None):
    """Tiny HTTP helper that always parses JSON responses."""
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    elif data is not None:
        body = json.dumps(data).encode()
        headers = {**(headers or {}), "Content-Type": "application/json"}
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode()
            return resp.status, dict(resp.headers), json.loads(payload) if payload else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {url}: {body}") from None


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


def _register_client(redirect_uri: str) -> dict:
    print(f"  Registering OAuth client at {REGISTER_URL} ...")
    _, _, body = _http_json(
        REGISTER_URL,
        method="POST",
        data={
            "client_name": "experiment_v2.1 deploy script",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": "mcp:use",
        },
    )
    print(f"  client_id = {body['client_id']}")
    return body


def _open_browser(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", url])
    elif sys.platform.startswith("linux"):
        subprocess.Popen(["xdg-open", url])
    else:
        import webbrowser

        webbrowser.open(url)


def _do_authorization_code_flow(client_id: str, redirect_uri: str) -> dict:
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    qs = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "mcp:use",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    auth_url = f"{AUTH_URL}?{qs}"

    captured: dict = {}
    port = int(urllib.parse.urlparse(redirect_uri).port)

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params and params.get("state", [""])[0] == state:
                captured["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<!doctype html><html><body style='font-family:sans-serif;"
                    b"text-align:center;padding-top:30vh'>"
                    b"<h1>Authorized.</h1>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                    b"</body></html>"
                )
            elif "error" in params:
                captured["error"] = params["error"][0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"OAuth error: {params['error'][0]}".encode())
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *args):
            return

    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print()
    print("  Opening browser for Cognition authorization ...")
    print(f"  If it does not open automatically, visit:\n    {auth_url}")
    print()
    _open_browser(auth_url)

    deadline = time.time() + 300
    while "code" not in captured and "error" not in captured and time.time() < deadline:
        time.sleep(0.2)
    server.shutdown()

    if "error" in captured:
        raise RuntimeError(f"Authorization failed: {captured['error']}")
    if "code" not in captured:
        raise RuntimeError("Timed out waiting for authorization (5 min).")

    print("  Authorization code received. Exchanging for access token ...")
    _, _, token = _http_json(
        TOKEN_URL,
        method="POST",
        form={
            "grant_type": "authorization_code",
            "code": captured["code"],
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    return token


def _refresh_access_token(client_id: str, refresh_token: str) -> dict:
    _, _, token = _http_json(
        TOKEN_URL,
        method="POST",
        form={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "scope": "mcp:use",
        },
    )
    return token


def _save_tokens(blob: dict) -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_PATH.write_text(json.dumps(blob, indent=2))
    try:
        os.chmod(TOKENS_PATH, 0o600)
    except OSError:
        pass


def _load_tokens() -> dict | None:
    if not TOKENS_PATH.exists():
        return None
    try:
        return json.loads(TOKENS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def get_access_token(*, reset: bool = False) -> str:
    """Returns a valid Bearer access token, prompting OAuth only when needed."""
    cached = None if reset else _load_tokens()

    # Try refresh first.
    if cached and cached.get("refresh_token") and cached.get("client_id"):
        try:
            print("Refreshing existing OAuth token ...")
            token = _refresh_access_token(cached["client_id"], cached["refresh_token"])
            _save_tokens(
                {
                    "client_id": cached["client_id"],
                    "redirect_uri": cached.get("redirect_uri"),
                    "refresh_token": token.get("refresh_token", cached["refresh_token"]),
                    "access_token": token["access_token"],
                    "expires_at": time.time() + int(token.get("expires_in", 3600)),
                }
            )
            return token["access_token"]
        except RuntimeError as exc:
            print(f"  Refresh failed ({exc}); falling back to full OAuth flow.")

    # Fresh OAuth.
    print("Starting fresh OAuth flow ...")
    port = _free_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    reg = _register_client(redirect_uri)
    token = _do_authorization_code_flow(reg["client_id"], redirect_uri)
    _save_tokens(
        {
            "client_id": reg["client_id"],
            "redirect_uri": redirect_uri,
            "refresh_token": token.get("refresh_token"),
            "access_token": token["access_token"],
            "expires_at": time.time() + int(token.get("expires_in", 3600)),
        }
    )
    return token["access_token"]


# -----------------------------------------------------------------------------
# Bundling
# -----------------------------------------------------------------------------


def build_bundle(exp_dir: Path = EXP_DIR) -> str:
    """Concatenate an experiment_v2.1-shaped directory into a single JS source
    string. `exp_dir` defaults to the live experiment_v2.1/ folder but can be
    pointed at any sibling folder with the same relative layout (src/,
    stimuli/, assets/style.css) — e.g. a filtered "fill gaps" variant meant
    to be deployed as a separate Cognition task under its own --task-name."""
    parts: list[str] = []
    parts.append(f"/* === {exp_dir.name} — auto-generated bundle for Cognition === */\n")

    css = (exp_dir / CSS_PATH).read_text()
    parts.append(
        "(function(){\n"
        "  var s = document.createElement('style');\n"
        f"  s.textContent = {json.dumps(css)};\n"
        "  document.head.appendChild(s);\n"
        "})();\n"
    )

    parts.append(
        "(function(){\n"
        "  if (window.Sortable) return;\n"
        "  var s = document.createElement('script');\n"
        f"  s.src = {json.dumps(SORTABLE_CDN)};\n"
        "  document.head.appendChild(s);\n"
        "})();\n"
    )

    for rel in JS_LOAD_ORDER:
        path = exp_dir / rel
        if not path.exists():
            raise FileNotFoundError(f"Expected {path} (referenced in JS_LOAD_ORDER)")
        parts.append(f"\n/* ----- {rel} ----- */\n")
        parts.append(path.read_text())

    return "\n".join(parts)


# -----------------------------------------------------------------------------
# MCP JSON-RPC client
# -----------------------------------------------------------------------------


class MCPClient:
    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._session_id: str | None = None
        self._req_id = 0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _post(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["mcp-session-id"] = self._session_id

        req = urllib.request.Request(
            MCP_URL,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if not self._session_id:
                    sid = resp.headers.get("mcp-session-id")
                    if sid:
                        self._session_id = sid
                raw = resp.read().decode()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise RuntimeError(f"MCP HTTP {exc.code}: {body}") from None

        # Server-Sent Events framing: extract last `data:` line if present.
        if raw.lstrip().startswith("event:") or "\ndata:" in raw:
            data_lines = [
                ln[5:].lstrip()
                for ln in raw.splitlines()
                if ln.startswith("data:")
            ]
            raw = data_lines[-1] if data_lines else raw

        return json.loads(raw)

    def initialize(self) -> dict:
        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "experiment_v2.1-deploy", "version": "0.1"},
                },
            }
        )
        # Per spec, send "initialized" notification.
        try:
            self._post(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                }
            )
        except Exception:
            pass
        return resp

    def call_tool(self, name: str, arguments: dict) -> dict:
        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in resp:
            raise RuntimeError(f"tool {name} failed: {resp['error']}")
        return resp.get("result", {})


def _structured(result: dict) -> object | None:
    """Return structuredContent if present, else parse first text content as JSON."""
    if "structuredContent" in result and result["structuredContent"] is not None:
        return result["structuredContent"]
    for item in result.get("content", []) or []:
        if item.get("type") == "text":
            txt = item.get("text", "").strip()
            try:
                return json.loads(txt)
            except json.JSONDecodeError:
                return txt
    return None


# -----------------------------------------------------------------------------
# Deploy
# -----------------------------------------------------------------------------


def _find_task_id(structured, task_name: str) -> int | None:
    """Walk a list-tasks response and find a task by name."""
    if structured is None:
        return None
    candidates = structured
    if isinstance(structured, dict):
        for key in ("tasks", "data", "items", "result"):
            if key in structured and isinstance(structured[key], list):
                candidates = structured[key]
                break
        else:
            candidates = [structured]
    if not isinstance(candidates, list):
        return None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        if item.get("name") == task_name:
            for key in ("id", "task_id", "taskId"):
                if key in item:
                    return item[key]
    return None


def _extract_task_id(structured) -> int | None:
    if isinstance(structured, dict):
        for key in ("id", "task_id", "taskId"):
            if key in structured:
                return structured[key]
        for key in ("task", "data"):
            inner = structured.get(key)
            if isinstance(inner, dict):
                tid = _extract_task_id(inner)
                if tid is not None:
                    return tid
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task-name",
        default="Experiment v2.1",
        help='Cognition task name to create or update (default: "Experiment v2.1").',
    )
    parser.add_argument(
        "--exp-dir",
        type=Path,
        default=None,
        help="Path to an experiment_v2.1-shaped source folder to bundle "
             "(default: the live experiment_v2.1/ folder next to this script). "
             "Use this with a distinct --task-name to deploy a variant "
             "(e.g. a filtered-assignments 'fill gaps' folder) as a separate "
             "Cognition task without touching the live one.",
    )
    parser.add_argument(
        "--reset-auth",
        action="store_true",
        help="Force a fresh OAuth flow (ignore cached refresh token).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the bundle and print stats; do not contact Cognition.",
    )
    parser.add_argument(
        "--save-bundle",
        type=Path,
        help="Optional path to write the bundled JS for inspection.",
    )
    args = parser.parse_args()
    exp_dir = args.exp_dir.resolve() if args.exp_dir else EXP_DIR

    print("== experiment_v2.1 → Cognition deploy ==")
    print(f"Repo:    {REPO_ROOT}")
    print(f"Source:  {exp_dir}")
    print(f"Task:    {args.task_name!r}")
    print()

    print("Step 1/4: Building bundle ...")
    source = build_bundle(exp_dir)
    print(f"  bundle size = {len(source):,} chars across {len(JS_LOAD_ORDER)} JS files + 1 CSS file")
    if args.save_bundle:
        args.save_bundle.parent.mkdir(parents=True, exist_ok=True)
        args.save_bundle.write_text(source)
        print(f"  wrote bundle to {args.save_bundle}")

    if args.dry_run:
        print("Dry-run requested; stopping before OAuth/MCP.")
        return 0

    print()
    print("Step 2/4: OAuth ...")
    access_token = get_access_token(reset=args.reset_auth)
    print("  access token acquired.")

    print()
    print("Step 3/4: MCP initialize + locate task ...")
    mcp = MCPClient(access_token)
    init = mcp.initialize()
    server_info = init.get("result", {}).get("serverInfo", {})
    print(f"  connected to {server_info.get('name','?')} v{server_info.get('version','?')}")

    print(f"  listing tasks ...")
    list_result = mcp.call_tool("list-tasks", {})
    list_struct = _structured(list_result)
    task_id = _find_task_id(list_struct, args.task_name)

    if task_id is None:
        print(f"  no task named {args.task_name!r}; creating ...")
        create_result = mcp.call_tool(
            "create-task", {"name": args.task_name, "lang": "en", "conditions": 8}
        )
        task_id = _extract_task_id(_structured(create_result))
        if task_id is None:
            print("  ERROR: could not extract task_id from create-task response:")
            print(json.dumps(create_result, indent=2))
            return 2
        print(f"  created task_id = {task_id}")
    else:
        print(f"  found existing task_id = {task_id}")

    print()
    print("Step 4/4: Pushing source code + setting library version ...")
    mcp.call_tool("update-source-code", {"task_id": task_id, "source": source})
    print("  update-source-code: ok")
    mcp.call_tool(
        "update-task",
        {"task_id": task_id, "library_version": COGNITION_LIBRARY_VERSION},
    )
    print(f"  update-task library_version = {COGNITION_LIBRARY_VERSION}: ok")

    print()
    print("Fetching task details for public URL ...")
    get_result = mcp.call_tool("get-task", {"task_id": task_id})
    get_struct = _structured(get_result)
    print()
    print("=== Deployed task ===")
    print(json.dumps(get_struct, indent=2)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""One-time Yahoo OAuth setup. Run this before starting the MCP server."""
import json
import os
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import httpx

TOKEN_FILE = Path.home() / ".yahoo_fantasy_tokens.json"
AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
REDIRECT_URI = "oob"


def main() -> None:
    client_id = os.getenv("YAHOO_CLIENT_ID", "")
    client_secret = os.getenv("YAHOO_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("Error: YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET must be set.")
        raise SystemExit(1)

    # Check if already authenticated with a valid refresh token
    if TOKEN_FILE.exists():
        tokens = json.loads(TOKEN_FILE.read_text())
        if tokens.get("refresh_token"):
            print("Existing token found. Refreshing...")
            try:
                tokens = _refresh(client_id, client_secret, tokens["refresh_token"])
                _save(tokens)
                print("Token refreshed successfully. MCP server is ready to use.")
                return
            except Exception as e:
                print(f"Refresh failed ({e}), re-authenticating...")

    # Full OAuth flow
    auth_url = f"{AUTH_URL}?{urlencode({
        'client_id': client_id,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'fspt-r',
        'language': 'en-us',
    })}"

    print("Opening Yahoo authorization page in your browser...")
    webbrowser.open(auth_url)
    print("After clicking Allow, Yahoo will display a code on the page.")

    code = input("Enter the code shown on the page: ").strip()
    if not code:
        print("No code entered. Aborting.")
        raise SystemExit(1)

    response = httpx.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
    )
    response.raise_for_status()
    tokens = response.json()
    _save(tokens)
    print("Authentication successful! MCP server is ready to use.")


def _refresh(client_id: str, client_secret: str, refresh_token: str) -> dict:
    response = httpx.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    response.raise_for_status()
    return response.json()


def _save(tokens: dict) -> None:
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    TOKEN_FILE.chmod(0o600)


if __name__ == "__main__":
    main()

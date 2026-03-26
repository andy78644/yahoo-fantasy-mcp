"""Yahoo Fantasy API OAuth client"""
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
API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"
REDIRECT_URI = "oob"


class YahooFantasyClient:
    def __init__(self):
        self.client_id = os.getenv("YAHOO_CLIENT_ID", "")
        self.client_secret = os.getenv("YAHOO_CLIENT_SECRET", "")
        self.auth_server = os.getenv("YAHOO_AUTH_SERVER", "").rstrip("/")
        self.tokens: dict = self._load_tokens()

    def _load_tokens(self) -> dict:
        if TOKEN_FILE.exists():
            return json.loads(TOKEN_FILE.read_text())
        return {}

    def _save_tokens(self, tokens: dict) -> None:
        TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
        TOKEN_FILE.chmod(0o600)
        self.tokens = tokens

    def is_authenticated(self) -> bool:
        return bool(self.tokens.get("access_token"))

    def authenticate(self, code: str | None = None) -> str:
        if self.auth_server:
            return self._authenticate_via_relay(code)
        return self._authenticate_direct(code)

    def _authenticate_via_relay(self, code: str | None) -> str:
        if code is None:
            resp = httpx.get(f"{self.auth_server}/auth/url", timeout=10)
            resp.raise_for_status()
            auth_url = resp.json()["url"]
            webbrowser.open(auth_url)
            return (
                "Browser opened. After clicking Allow on the Yahoo authorization page, "
                "a code will be displayed directly on the page.\n"
                "Copy that code and call authenticate again with it."
            )

        resp = httpx.post(f"{self.auth_server}/auth/exchange", json={"code": code}, timeout=10)
        resp.raise_for_status()
        tokens = resp.json()
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        self._save_tokens(tokens)
        return f"Authenticated via relay! Token valid for {tokens.get('expires_in', 3600) // 60} minutes."

    def _authenticate_direct(self, code: str | None) -> str:
        if not self.client_id:
            raise ValueError("Set YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET, or YAHOO_AUTH_SERVER.")

        if code is None:
            auth_url = f"{AUTH_URL}?{urlencode({
                'client_id': self.client_id,
                'redirect_uri': REDIRECT_URI,
                'response_type': 'code',
                'scope': 'fspt-r',
                'language': 'en-us',
            })}"
            webbrowser.open(auth_url)
            return (
                "Browser opened. After clicking Allow on the Yahoo authorization page, "
                "a code will be displayed directly on the page.\n"
                "Copy that code and call authenticate again with it."
            )

        response = httpx.post(
            TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        )
        response.raise_for_status()
        tokens = response.json()
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        self._save_tokens(tokens)
        return f"Authenticated! Token valid for {tokens.get('expires_in', 3600) // 60} minutes."

    def _refresh_if_needed(self) -> None:
        if not self.tokens.get("access_token"):
            raise RuntimeError("No valid token found. Ask Claude to authenticate with Yahoo Fantasy first.")
        if time.time() < self.tokens.get("expires_at", 0) - 60:
            return
        if self.auth_server:
            resp = httpx.post(
                f"{self.auth_server}/auth/refresh",
                json={"refresh_token": self.tokens["refresh_token"]},
                timeout=10,
            )
            resp.raise_for_status()
            tokens = resp.json()
        else:
            resp = httpx.post(
                TOKEN_URL,
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "refresh_token", "refresh_token": self.tokens["refresh_token"]},
            )
            resp.raise_for_status()
            tokens = resp.json()
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        self._save_tokens(tokens)

    def get(self, path: str, params: dict | None = None) -> dict:
        self._refresh_if_needed()
        response = httpx.get(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {self.tokens['access_token']}"},
            params={"format": "json", **(params or {})},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def put(self, path: str, xml_body: str) -> None:
        self._refresh_if_needed()
        response = httpx.put(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {self.tokens['access_token']}", "Content-Type": "application/xml"},
            content=xml_body.encode(),
            timeout=15,
        )
        response.raise_for_status()

    def post(self, path: str, xml_body: str) -> dict:
        self._refresh_if_needed()
        response = httpx.post(
            f"{API_BASE}{path}",
            headers={"Authorization": f"Bearer {self.tokens['access_token']}", "Content-Type": "application/xml"},
            content=xml_body.encode(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

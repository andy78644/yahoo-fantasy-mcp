"""Yahoo Fantasy OAuth Relay Server

A lightweight relay that holds client credentials and handles token exchange.
Users point YAHOO_AUTH_SERVER at this server — no client_id/secret needed on their end.

Endpoints:
  GET  /auth/url      → returns Yahoo authorization URL
  POST /auth/exchange → exchange OOB code for tokens
  POST /auth/refresh  → refresh an existing token
"""
import os
import time
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
REDIRECT_URI = "oob"

CLIENT_ID = os.environ["YAHOO_CLIENT_ID"]
CLIENT_SECRET = os.environ["YAHOO_CLIENT_SECRET"]

app = FastAPI(title="Yahoo Fantasy OAuth Relay")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/auth/url")
def get_auth_url() -> dict:
    url = f"{AUTH_URL}?{urlencode({
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'fspt-r',
        'language': 'en-us',
    })}"
    return {"url": url}


class ExchangeRequest(BaseModel):
    code: str


@app.post("/auth/exchange")
def exchange_code(body: ExchangeRequest) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "authorization_code", "code": body.code, "redirect_uri": REDIRECT_URI},
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    tokens = resp.json()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
        "expires_in": tokens.get("expires_in", 3600),
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/auth/refresh")
def refresh_token(body: RefreshRequest) -> dict:
    resp = httpx.post(
        TOKEN_URL,
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "refresh_token", "refresh_token": body.refresh_token},
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    tokens = resp.json()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", body.refresh_token),
        "expires_in": tokens.get("expires_in", 3600),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": int(time.time())}

# Yahoo Fantasy OAuth Relay

A lightweight relay server that holds Yahoo API credentials and handles token exchange on behalf of users.

## How it works

Users point `YAHOO_AUTH_SERVER` at this server. The relay holds `client_id` and `client_secret` — users don't need their own Yahoo Developer App.

## Run locally

```bash
pip install -r requirements.txt
YAHOO_CLIENT_ID=xxx YAHOO_CLIENT_SECRET=xxx uvicorn server:app --port 8000
```

## Deploy to Railway / Render / Fly.io

Set env vars `YAHOO_CLIENT_ID` and `YAHOO_CLIENT_SECRET`, then deploy.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/auth/url` | Get Yahoo authorization URL |
| POST | `/auth/exchange` | Exchange OOB code for tokens |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/health` | Health check |

## MCP config (for users of this relay)

```json
{
  "mcpServers": {
    "yahoo-fantasy": {
      "command": "/path/to/venv/bin/python3",
      "args": ["/path/to/server.py"],
      "env": {
        "YAHOO_AUTH_SERVER": "https://your-relay-url.com"
      }
    }
  }
}
```

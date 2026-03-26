# Yahoo Fantasy MCP

A Model Context Protocol (MCP) server for Yahoo Fantasy Baseball and Basketball. Lets Claude analyze your roster, check matchups, browse free agents, and more.

## Prerequisites

- Python 3.11+
- A Yahoo Developer App with `fspt-r` scope

## Setup

### 1. Create a Yahoo Developer App

1. Go to [Yahoo Developer Network](https://developer.yahoo.com/apps/)
2. Click **Create an App**
3. Fill in the details:
   - **Application Name**: anything you like
   - **Application Type**: Installed Application (Client)
   - **Callback Domain**: any valid HTTPS domain (e.g. `yahoo.com`) — not used in this flow
   - **API Permissions**: Fantasy Sports → **Read**
4. Note your **Client ID** and **Client Secret**

### 2. Install dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Claude Desktop / Claude Code

Add to your Claude config:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "yahoo-fantasy": {
      "command": "/path/to/yahoo-fantasy-mcp/venv/bin/python3",
      "args": ["/path/to/yahoo-fantasy-mcp/server.py"],
      "env": {
        "YAHOO_CLIENT_ID": "your_client_id_here",
        "YAHOO_CLIENT_SECRET": "your_client_secret_here"
      }
    }
  }
}
```

**Claude Code** (`~/.claude.json`):
```json
{
  "mcpServers": {
    "yahoo-fantasy": {
      "type": "stdio",
      "command": "/path/to/yahoo-fantasy-mcp/venv/bin/python3",
      "args": ["/path/to/yahoo-fantasy-mcp/server.py"],
      "env": {
        "YAHOO_CLIENT_ID": "your_client_id_here",
        "YAHOO_CLIENT_SECRET": "your_client_secret_here"
      }
    }
  }
}
```

### 4. First-time authentication

On first use, just ask Claude anything about your fantasy team. If not authenticated, Claude will automatically start the OAuth flow:

1. A browser window opens to Yahoo's authorization page
2. Click **Allow**
3. Yahoo displays a code on the page — copy it and give it to Claude
4. Done. The token is saved and auto-refreshed from now on.

You only need to do this once (or when the refresh token expires after ~1 year).

## Available Tools

| Tool | Description |
|------|-------------|
| `authenticate` | Start Yahoo OAuth flow (called automatically when needed) |
| `get_leagues` | List your MLB and NBA leagues |
| `get_roster` | View your current roster with positions and injury status |
| `get_matchup` | See this week's matchup and stat leaders |
| `get_free_agents` | Browse available free agents by position |
| `get_player_stats` | Get player stats for a given period |

## Logging out

To remove your local tokens:

```bash
python logout.py
```

## Example Usage

Just ask Claude naturally:

- "Show me my baseball roster"
- "Who's winning my matchup this week?"
- "Find me the best available SP on the waiver wire"
- "How has Gunnar Henderson been performing lately?"
- "Give me roster improvement suggestions"

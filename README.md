# Yahoo Fantasy MCP

A Model Context Protocol (MCP) server for Yahoo Fantasy Baseball and Basketball. Lets Claude analyze your roster, check matchups, browse free agents, and more.

## Setup

### 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Claude Desktop / Claude Code

There are two ways to authenticate — pick one:

---

#### Option A: Use a relay server (recommended, no Yahoo app needed)

Point the MCP at a relay server that handles credentials for you:

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "yahoo-fantasy": {
      "command": "/path/to/yahoo-fantasy-mcp/venv/bin/python3",
      "args": ["/path/to/yahoo-fantasy-mcp/server.py"],
      "env": {
        "YAHOO_AUTH_SERVER": "https://your-relay-url.com"
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
        "YAHOO_AUTH_SERVER": "https://your-relay-url.com"
      }
    }
  }
}
```

> Want to self-host your own relay? See [`relay/README.md`](relay/README.md).

---

#### Option B: Use your own Yahoo Developer App

1. Go to [Yahoo Developer Network](https://developer.yahoo.com/apps/) and create an app
2. Set **Application Type** to Installed Application, **API Permissions** to Fantasy Sports → Read
3. Note your **Client ID** and **Client Secret**

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

---

### 3. First-time authentication

On first use, just ask Claude anything about your fantasy team. If not authenticated, Claude will automatically start the OAuth flow:

1. A browser window opens to Yahoo's authorization page
2. Click **Allow**
3. Yahoo displays a code on the page — copy it and give it to Claude
4. Done. The token is saved and auto-refreshed from now on (~1 year before re-auth needed)

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

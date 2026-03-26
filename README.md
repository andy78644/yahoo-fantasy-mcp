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

### 3. Configure Claude Desktop

Add the following to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

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

### 4. Authenticate (one-time setup)

```bash
YAHOO_CLIENT_ID=your_client_id \
YAHOO_CLIENT_SECRET=your_client_secret \
venv/bin/python auth.py
```

A browser window will open. Click **Allow**, then copy the code displayed on the page and paste it into the terminal.

After this, your token is saved to `~/.yahoo_fantasy_tokens.json` and will be refreshed automatically. You only need to run `auth.py` again if the refresh token expires (~1 year).

## Available Tools

| Tool | Description |
|------|-------------|
| `authenticate` | Re-authenticate if token is invalid |
| `get_leagues` | List your MLB and NBA leagues |
| `get_roster` | View your current roster with positions and injury status |
| `get_matchup` | See this week's matchup and stat leaders |
| `get_free_agents` | Browse available free agents by position |
| `get_player_stats` | Get player stats for a given period |

## Example Usage

Once configured, just ask Claude:

- "Show me my baseball roster"
- "Who's winning my matchup this week?"
- "Find me the best available SP on the waiver wire"
- "How has Gunnar Henderson been performing lately?"

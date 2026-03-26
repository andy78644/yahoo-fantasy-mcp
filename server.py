#!/usr/bin/env python3
"""Yahoo Fantasy Sports MCP Server — MLB & NBA start/sit and roster analysis"""
import asyncio
import json

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from parsers import parse_free_agents, parse_leagues, parse_matchup, parse_player_stats, parse_roster
from yahoo_client import YahooFantasyClient

app = Server("yahoo-fantasy")
yahoo = YahooFantasyClient()

TOOLS = [
    types.Tool(
        name="authenticate",
        description="Yahoo OAuth two-step flow. Step 1: call with no args to open browser. Step 2: copy the `code` from the redirect URL and call again with it.",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The code= value from the redirect URL after Yahoo authorization (Step 2 only)"},
            },
        },
    ),
    types.Tool(
        name="get_leagues",
        description="List your MLB and NBA fantasy leagues. Returns league_key and my_team_key needed for other tools.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_roster",
        description="Get your current roster with positions, status, and injury notes.",
        inputSchema={"type": "object", "properties": {"team_key": {"type": "string", "description": "Your team key from get_leagues"}}, "required": ["team_key"]},
    ),
    types.Tool(
        name="get_matchup",
        description="Get current week/period matchup details including opponent stats.",
        inputSchema={"type": "object", "properties": {"team_key": {"type": "string"}}, "required": ["team_key"]},
    ),
    types.Tool(
        name="get_free_agents",
        description="Get top available free agents. Use for waiver wire and add/drop decisions.",
        inputSchema={
            "type": "object",
            "properties": {
                "league_key": {"type": "string"},
                "position": {"type": "string", "description": "MLB: SP/RP/C/1B/2B/3B/SS/OF  NBA: PG/SG/SF/PF/C"},
                "count": {"type": "integer", "default": 25, "description": "Max players to return"},
            },
            "required": ["league_key"],
        },
    ),
    types.Tool(
        name="get_player_stats",
        description="Get player stats for a specific period. Use to compare players for start/sit decisions.",
        inputSchema={
            "type": "object",
            "properties": {
                "player_key": {"type": "string"},
                "stat_period": {
                    "type": "string",
                    "enum": ["season", "lastweek", "last14", "last30"],
                    "default": "last14",
                    "description": "last14 is best for recent form analysis",
                },
            },
            "required": ["player_key"],
        },
    ),
    # set_lineup and make_transaction require fspt-w OAuth scope (currently read-only)
    # types.Tool(name="set_lineup", ...),
    # types.Tool(name="make_transaction", ...),
]


def _text(content: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=content)]


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        return _dispatch(name, arguments)
    except Exception as e:
        return _text(f"Error: {e}")


def _dispatch(name: str, args: dict) -> list[types.TextContent]:
    if name == "authenticate":
        return _text(yahoo.authenticate(args.get("code")))

    if name == "get_leagues":
        data = yahoo.get("/users;use_login=1/games;game_keys=mlb,nba/leagues/teams")
        return _text(json.dumps(parse_leagues(data), indent=2))

    if name == "get_roster":
        data = yahoo.get(f"/team/{args['team_key']}/roster/players")
        return _text(json.dumps(parse_roster(data), indent=2))

    if name == "get_matchup":
        data = yahoo.get(f"/team/{args['team_key']}/matchups")
        return _text(json.dumps(parse_matchup(data), indent=2))

    if name == "get_free_agents":
        path = f"/league/{args['league_key']}/players;status=FA;sort=AR;count={args.get('count', 25)}"
        if pos := args.get("position"):
            path += f";position={pos}"
        data = yahoo.get(path)
        return _text(json.dumps(parse_free_agents(data), indent=2))

    if name == "get_player_stats":
        period = args.get("stat_period", "last14")
        data = yahoo.get(f"/player/{args['player_key']}/stats;type={period}")
        return _text(json.dumps(parse_player_stats(data), indent=2))

    return _text(f"Unknown tool: {name}")



async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

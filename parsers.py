"""Parsers for Yahoo Fantasy API's deeply nested JSON responses"""


def _extract_info(items: list) -> dict:
    """Flatten Yahoo's list-of-dicts player/team info format into one dict."""
    result = {}
    for item in items:
        if isinstance(item, dict):
            result.update(item)
    return result


def parse_leagues(data: dict) -> list[dict]:
    """Parse /users;use_login=1/games;game_keys=mlb,nba/leagues"""
    users = data.get("fantasy_content", {}).get("users", {})
    user_parts = users.get("0", {}).get("user", [{}, {}])
    games = user_parts[1].get("games", {}) if len(user_parts) > 1 else {}

    leagues = []
    for i in range(games.get("count", 0)):
        game_parts = games.get(str(i), {}).get("game", [{}, {}])
        game_info = game_parts[0] if isinstance(game_parts[0], dict) else {}
        game_leagues = game_parts[1].get("leagues", {}) if len(game_parts) > 1 else {}

        for j in range(game_leagues.get("count", 0)):
            league_parts = game_leagues.get(str(j), {}).get("league", [{}])
            league_info = league_parts[0] if league_parts else {}

            my_team_key = _extract_my_team_key(league_parts)
            leagues.append({
                "sport": game_info.get("name"),
                "game_code": game_info.get("code"),
                "league_key": league_info.get("league_key"),
                "league_name": league_info.get("name"),
                "num_teams": league_info.get("num_teams"),
                "current_week": league_info.get("current_week") or league_info.get("current_period"),
                "scoring_type": league_info.get("scoring_type"),
                "my_team_key": my_team_key,
            })
    return leagues


def _extract_my_team_key(league_parts: list) -> str | None:
    if len(league_parts) < 2:
        return None
    teams = league_parts[1].get("teams", {})
    if not teams.get("count"):
        return None
    team_parts = teams.get("0", {}).get("team", [[]])
    team_info = _extract_info(team_parts[0]) if team_parts else {}
    return team_info.get("team_key")


def parse_roster(data: dict) -> list[dict]:
    """Parse /team/{key}/roster/players"""
    team_data = data.get("fantasy_content", {}).get("team", [{}, {}])
    roster_root = team_data[1].get("roster", {}) if len(team_data) > 1 else {}
    players_data = roster_root.get("0", {}).get("players", {})

    players = []
    for i in range(players_data.get("count", 0)):
        player_parts = players_data.get(str(i), {}).get("player", [[], {}])
        info = _extract_info(player_parts[0]) if player_parts else {}
        pos_data = player_parts[1] if len(player_parts) > 1 else {}

        sel_pos_list = pos_data.get("selected_position", [])
        sel_pos_info = sel_pos_list[1] if len(sel_pos_list) > 1 else {}
        selected_pos = sel_pos_info.get("position")
        is_flex = sel_pos_info.get("is_flex", 0)

        players.append({
            "name": info.get("name", {}).get("full", "Unknown"),
            "player_key": info.get("player_key"),
            "positions": [p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)],
            "selected_position": selected_pos,
            "is_bench": selected_pos == "BN",
            "is_injured_reserve": selected_pos in ("IL", "IL+", "NA"),
            "is_flex": bool(is_flex),
            "status": info.get("status", "Active"),
            "injury_note": info.get("injury_note", ""),
            "team": info.get("editorial_team_abbr", ""),
        })
    return players


def parse_player_search(data: dict) -> list[dict]:
    """Parse /league/{key}/players;search={name}"""
    league_data = data.get("fantasy_content", {}).get("league", [{}, {}])
    players_data = league_data[1].get("players", {}) if len(league_data) > 1 else {}

    players = []
    for i in range(players_data.get("count", 0)):
        player_parts = players_data.get(str(i), {}).get("player", [[], {}])
        info = _extract_info(player_parts[0]) if player_parts else {}
        players.append({
            "name": info.get("name", {}).get("full", "Unknown"),
            "player_key": info.get("player_key"),
            "positions": [p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)],
            "status": info.get("status", "Active"),
            "injury_note": info.get("injury_note", ""),
            "team": info.get("editorial_team_abbr", ""),
        })
    return players


def _is_nba_player(info: dict, player_stats: dict | None = None) -> bool:
    """Detect NBA vs MLB.
    Primary: basketball-only positions (PG/SG/SF/PF).
    Fallback for C/Util-only players: check for stat_id 9004003 (FGM/FGA, NBA-exclusive).
    """
    positions = {p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)}
    if positions & {"PG", "SG", "SF", "PF"}:
        return True
    if player_stats:
        stat_ids = {str(s["stat"]["stat_id"]) for s in player_stats.get("stats", []) if isinstance(s, dict) and "stat" in s}
        if "9004003" in stat_ids:
            return True
    return False


def _stat_map_for(info: dict, player_stats: dict | None = None) -> dict:
    return NBA_STAT_NAMES if _is_nba_player(info, player_stats) else MLB_STAT_NAMES


def _parse_stats_block(player_stats: dict, stat_map: dict) -> dict:
    """Extract named stats from a player_stats block."""
    named_stats = {}
    for s in player_stats.get("stats", []):
        if isinstance(s, dict) and "stat" in s:
            sid = str(s["stat"]["stat_id"])
            val = s["stat"]["value"]
            if val not in ("-", False, None):
                label = stat_map.get(sid, f"stat_{sid}")
                named_stats[label] = val
    return named_stats


def parse_roster_stats(data: dict) -> list[dict]:
    """Parse /team/{key}/roster/players/stats;type={period} — all players with stats in one call."""
    team_data = data.get("fantasy_content", {}).get("team", [{}, {}])
    roster_root = team_data[1].get("roster", {}) if len(team_data) > 1 else {}
    players_data = roster_root.get("0", {}).get("players", {})

    players = []
    for i in range(players_data.get("count", 0)):
        player_parts = players_data.get(str(i), {}).get("player", [[], {}])
        info = _extract_info(player_parts[0]) if player_parts else {}

        sel_pos_list = player_parts[1].get("selected_position", []) if len(player_parts) > 1 and isinstance(player_parts[1], dict) else []
        sel_pos_info = sel_pos_list[1] if len(sel_pos_list) > 1 else {}
        selected_pos = sel_pos_info.get("position")

        player_stats = player_parts[3].get("player_stats", {}) if len(player_parts) > 3 and isinstance(player_parts[3], dict) else {}
        coverage_type = player_stats.get("0", {}).get("coverage_type")

        player_key = info.get("player_key", "")
        players.append({
            "name": info.get("name", {}).get("full", "Unknown"),
            "player_key": player_key,
            "team": info.get("editorial_team_abbr", ""),
            "positions": [p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)],
            "selected_position": selected_pos,
            "is_bench": selected_pos == "BN",
            "is_injured_reserve": selected_pos in ("IL", "IL+", "NA"),
            "status": info.get("status", "Active"),
            "injury_note": info.get("injury_note", ""),
            "coverage_type": coverage_type,
            "stats": _parse_stats_block(player_stats, _stat_map_for(info, player_stats)),
        })
    return players


def parse_free_agents(data: dict, include_stats: bool = False) -> list[dict]:
    """Parse /league/{key}/players;status=FA"""
    league_data = data.get("fantasy_content", {}).get("league", [{}, {}])
    players_data = league_data[1].get("players", {}) if len(league_data) > 1 else {}

    players = []
    for i in range(players_data.get("count", 0)):
        player_parts = players_data.get(str(i), {}).get("player", [[], {}])
        info = _extract_info(player_parts[0]) if player_parts else {}

        player_key = info.get("player_key", "")
        entry = {
            "name": info.get("name", {}).get("full", "Unknown"),
            "player_key": player_key,
            "positions": [p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)],
            "status": info.get("status", "Active"),
            "injury_note": info.get("injury_note", ""),
            "team": info.get("editorial_team_abbr", ""),
            "percent_owned": _safe_percent_owned(info),
        }

        if include_stats and len(player_parts) > 1 and isinstance(player_parts[1], dict):
            player_stats = player_parts[1].get("player_stats", {})
            entry["coverage_type"] = player_stats.get("0", {}).get("coverage_type")
            entry["stats"] = _parse_stats_block(player_stats, _stat_map_for(info, player_stats))

        players.append(entry)
    return players


def _safe_percent_owned(info: dict) -> float:
    po = info.get("percent_owned", {})
    return float(po.get("value", 0)) if isinstance(po, dict) else 0.0


MLB_STAT_NAMES = {
    "0": "GP", "1": "AB", "2": "R", "3": "H", "4": "1B", "5": "2B", "6": "3B",
    "7": "HR", "8": "RBI", "9": "SB", "10": "CS", "11": "BB", "12": "IBB",
    "13": "HBP", "14": "SAC", "15": "SF", "16": "GIDP", "17": "SO", "18": "AVG",
    "19": "OBP", "20": "SLG", "21": "OPS", "22": "PA", "23": "XBH",
    "26": "NSB", "27": "IP", "28": "GS", "29": "W", "30": "L", "31": "SV",
    "32": "HLD", "33": "BS", "34": "ERA", "35": "WHIP", "36": "K", "37": "BB_P",
    "38": "QS", "39": "OUT", "40": "HA", "41": "HRA", "42": "BBA", "43": "ER",
    "44": "NSV", "45": "K/9", "46": "BB/9", "48": "K/BB",
    "50": "HR/9", "51": "G_P", "55": "W+SV+HLD", "56": "SVHD",
    "57": "Ks_swinging", "58": "GB%", "59": "FIP",
    "60": "OAV", "61": "BAA", "62": "SV+HLD",
}

NBA_STAT_NAMES = {
    "0": "GP", "1": "GS", "2": "MIN", "3": "FGA", "4": "FGM", "5": "FG%",
    "6": "3PTA", "7": "3PTM", "8": "3PT%", "9": "FTA", "10": "FTM", "11": "FT%",
    "12": "OREB", "13": "DREB", "14": "REB", "15": "AST", "16": "ST",
    "17": "BLK", "18": "TO", "19": "PTS", "20": "+/-",
}


def parse_player_stats(data: dict) -> dict:
    """Parse /player/{key}/stats;type={period}"""
    player_parts = data.get("fantasy_content", {}).get("player", [[], {}])
    info = _extract_info(player_parts[0]) if player_parts else {}
    player_stats = player_parts[1].get("player_stats", {}) if len(player_parts) > 1 else {}

    # coverage_type is nested under player_stats["0"]
    coverage_info = player_stats.get("0", {})
    coverage_type = coverage_info.get("coverage_type")

    player_key = info.get("player_key", "")
    return {
        "name": info.get("name", {}).get("full", "Unknown"),
        "player_key": player_key,
        "team": info.get("editorial_team_full_name", ""),
        "status": info.get("status", "Active"),
        "injury_note": info.get("injury_note", ""),
        "coverage_type": coverage_type,
        "stats": _parse_stats_block(player_stats, _stat_map_for(info, player_stats)),
    }


def parse_matchup(data: dict) -> dict:
    """Parse /team/{key}/matchups — returns only the current/most-recent matchup."""
    team_parts = data.get("fantasy_content", {}).get("team", [{}, {}])
    matchups_container = team_parts[1].get("matchups", {}) if len(team_parts) > 1 else {}

    current = None
    latest_week = -1
    for i in range(matchups_container.get("count", 0)):
        m = matchups_container.get(str(i), {}).get("matchup", {})
        status = m.get("status", "")
        week = m.get("week", 0)
        if status == "midevent":
            current = m
            break
        if status == "postevent" and week > latest_week:
            latest_week = week
            current = m

    if not current:
        return {"error": "No current matchup found"}

    teams_data = current.get("0", {}).get("teams", {})
    teams = []
    for i in range(teams_data.get("count", 0)):
        t_parts = teams_data.get(str(i), {}).get("team", [[], {}])
        t_info = _extract_info(t_parts[0]) if t_parts else {}
        t_stats = t_parts[1] if len(t_parts) > 1 else {}
        teams.append({
            "team_key": t_info.get("team_key"),
            "name": t_info.get("name"),
            "points": t_stats.get("team_points", {}).get("total"),
            "projected_points": t_stats.get("team_projected_points", {}).get("total"),
        })

    stat_winners = []
    for sw in current.get("stat_winners", []):
        if isinstance(sw, dict) and "stat_winner" in sw:
            s = sw["stat_winner"]
            stat_winners.append({
                "stat_id": s.get("stat_id"),
                "winner_team_key": s.get("winner_team_key"),
                "is_tied": s.get("is_tied"),
            })

    return {
        "week": current.get("week"),
        "week_start": current.get("week_start"),
        "week_end": current.get("week_end"),
        "status": current.get("status"),
        "is_playoffs": current.get("is_playoffs"),
        "teams": teams,
        "stat_winners": stat_winners,
    }

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


def _stat_map_for_ids(stat_ids) -> dict:
    """Pick MLB vs NBA map from a set of stat_ids (team-level, no player info).
    NBA stat_ids top out at 20; any id > 20 is an MLB category (IP/ERA/WHIP/QS/etc)."""
    for sid in stat_ids:
        s = str(sid)
        if s.isdigit() and int(s) > 20:
            return MLB_STAT_NAMES
    return NBA_STAT_NAMES


def _parse_team_category_stats(team_stats: dict) -> dict:
    """Flatten team_stats block into dual-indexed dict: both raw stat_id and human label point to the same value.
    e.g. {"7": "5", "HR": "5", "34": "3.21", "ERA": "3.21"}
    """
    raw = team_stats.get("stats", []) if isinstance(team_stats, dict) else []
    ids = [str(s["stat"]["stat_id"]) for s in raw if isinstance(s, dict) and "stat" in s]
    stat_map = _stat_map_for_ids(ids)

    out = {}
    for s in raw:
        if not isinstance(s, dict) or "stat" not in s:
            continue
        sid = str(s["stat"]["stat_id"])
        val = s["stat"].get("value")
        if val in ("-", None, "") or val is False:
            continue
        out[sid] = val
        label = stat_map.get(sid)
        if label:
            out[label] = val
    return out


def _parse_stats_block(player_stats: dict, stat_map: dict) -> dict:
    """Extract named stats from a player_stats block."""
    named_stats = {}
    for s in player_stats.get("stats", []):
        if isinstance(s, dict) and "stat" in s:
            sid = str(s["stat"]["stat_id"])
            val = s["stat"]["value"]
            if val not in ("-", None) and val is not False:
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

        sel_pos_list = []
        player_stats = {}
        for part in player_parts[1:]:
            if not isinstance(part, dict):
                continue
            if "selected_position" in part:
                sel_pos_list = part["selected_position"]
            if "player_stats" in part:
                player_stats = part["player_stats"]

        sel_pos_info = sel_pos_list[1] if len(sel_pos_list) > 1 else {}
        selected_pos = sel_pos_info.get("position")
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
    """Parse /league/{key}/players;status=FA

    Hitters carry an extra {starting_status, batting_order} block before stats,
    so player_stats lives at player_parts[2] for hitters vs [1] for pitchers.
    Iterate all trailing parts to find it regardless of position.
    """
    league_data = data.get("fantasy_content", {}).get("league", [{}, {}])
    players_data = league_data[1].get("players", {}) if len(league_data) > 1 else {}

    players = []
    for i in range(players_data.get("count", 0)):
        player_parts = players_data.get(str(i), {}).get("player", [[], {}])
        info = _extract_info(player_parts[0]) if player_parts else {}

        player_stats = {}
        percent_owned = 0.0
        percent_owned_delta = None
        for part in player_parts[1:]:
            if not isinstance(part, dict):
                continue
            if "player_stats" in part:
                player_stats = part["player_stats"]
            if "percent_owned" in part:
                percent_owned, percent_owned_delta = _extract_percent_owned(part["percent_owned"])

        entry = {
            "name": info.get("name", {}).get("full", "Unknown"),
            "player_key": info.get("player_key", ""),
            "positions": [p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)],
            "status": info.get("status", "Active"),
            "injury_note": info.get("injury_note", ""),
            "team": info.get("editorial_team_abbr", ""),
            "percent_owned": percent_owned,
            "percent_owned_delta": percent_owned_delta,
        }

        if include_stats and player_stats:
            entry["coverage_type"] = player_stats.get("0", {}).get("coverage_type")
            entry["stats"] = _parse_stats_block(player_stats, _stat_map_for(info, player_stats))

        players.append(entry)
    return players


def _extract_percent_owned(raw) -> tuple[float, float | None]:
    """percent_owned comes as [{coverage_type,...}, {value: N}, {delta: "N"}]."""
    value = 0.0
    delta = None
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "value" in item:
                try: value = float(item["value"])
                except (TypeError, ValueError): pass
            if "delta" in item:
                try: delta = float(item["delta"])
                except (TypeError, ValueError): pass
    return value, delta


MLB_STAT_NAMES = {
    # Source of truth: /game/469/stat_categories (2026 MLB game key).
    # Where hitter + pitcher share a Yahoo display_name, the pitcher version gets
    # a suffix (HA/RA/HRA/BBA/etc.) so team-level matchup stats don't collide.

    # Batting — counting
    "0": "GP", "6": "AB", "7": "R", "8": "H",
    "9": "1B", "10": "2B", "11": "3B", "12": "HR",
    "13": "RBI", "14": "SH", "15": "SF", "16": "SB",
    "17": "CS", "18": "BB", "19": "IBB", "20": "HBP",
    "21": "SO", "22": "GIDP", "23": "TB", "61": "XBH",
    "62": "NSB", "64": "CYC", "65": "PA", "66": "SLAM",
    # Batting — rate
    "3": "AVG", "4": "OBP", "5": "SLG", "55": "OPS",
    "60": "H/AB", "63": "SB%",

    # Pitching — counting
    "1": "GP_P", "2": "GS", "24": "APP", "25": "GS",
    "28": "W", "29": "L", "30": "CG", "31": "SHO",
    "32": "SV", "33": "OUT", "35": "TBF", "37": "ER",
    "42": "K", "43": "WP", "44": "BLK", "47": "SVOP",
    "48": "HLD", "50": "IP", "67": "PC", "70": "RW",
    "71": "RL", "72": "PICK", "73": "RAPP", "79": "NH",
    "80": "PG", "83": "QS", "84": "BSV", "85": "NSV",
    "89": "SV+H", "90": "NSVH", "91": "NW",
    # Pitching — "allowed" / inverse batter stats
    "34": "HA", "36": "RA", "38": "HRA", "39": "BB_P",
    "40": "IBB_P", "41": "HBP_P", "45": "SBA", "46": "GIDP_P",
    "49": "TBA", "68": "2BA", "69": "3BA", "76": "1BA",
    "82": "IRA",
    # Pitching — rate
    "26": "ERA", "27": "WHIP", "56": "K/BB", "57": "K/9",
    "74": "OBPA", "75": "WIN%", "77": "H/9", "78": "BB/9",
    "81": "SV%",

    # Fielding
    "51": "PO", "52": "A", "53": "E", "54": "FPCT",
    "86": "OFA", "87": "DPT", "88": "CI",
    # Meta
    "58": "TEAM", "59": "LEAGUE",
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
        week = int(m.get("week", 0))
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
            "stats": _parse_team_category_stats(t_stats.get("team_stats", {})),
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


def _parse_stat_winners(raw: list) -> list[dict]:
    out = []
    for sw in raw or []:
        if isinstance(sw, dict) and "stat_winner" in sw:
            s = sw["stat_winner"]
            out.append({
                "stat_id": s.get("stat_id"),
                "winner_team_key": s.get("winner_team_key"),
                "is_tied": s.get("is_tied"),
            })
    return out


def _team_brief(t_parts: list) -> dict:
    """Extract team_key, name, manager from a team node."""
    info = _extract_info(t_parts[0]) if t_parts else {}
    managers = info.get("managers", [])
    nicks = []
    for m in managers:
        if isinstance(m, dict) and "manager" in m:
            nick = m["manager"].get("nickname")
            if nick:
                nicks.append(nick)
    return {
        "team_key": info.get("team_key"),
        "name": info.get("name"),
        "manager": ", ".join(nicks) if nicks else None,
    }


def parse_league_teams(data: dict) -> list[dict]:
    """Parse /league/{key}/teams — all teams in the league."""
    league_data = data.get("fantasy_content", {}).get("league", [{}, {}])
    teams_root = league_data[1].get("teams", {}) if len(league_data) > 1 else {}

    teams = []
    for i in range(teams_root.get("count", 0)):
        t_parts = teams_root.get(str(i), {}).get("team", [[]])
        teams.append(_team_brief(t_parts))
    return teams


def parse_league_settings(data: dict) -> dict:
    """Parse /league/{key}/settings — returns scoring categories with sort_order."""
    league_data = data.get("fantasy_content", {}).get("league", [{}, {}])
    league_info = league_data[0] if league_data else {}
    settings_list = league_data[1].get("settings", [{}]) if len(league_data) > 1 else [{}]
    settings = settings_list[0] if settings_list else {}

    stat_categories_root = settings.get("stat_categories", {}).get("stats", [])
    stat_ids = []
    raw_cats = []
    for s in stat_categories_root:
        if not isinstance(s, dict) or "stat" not in s:
            continue
        stat = s["stat"]
        sid = str(stat.get("stat_id"))
        stat_ids.append(sid)
        raw_cats.append(stat)

    stat_map = _stat_map_for_ids(stat_ids)
    categories = []
    for stat in raw_cats:
        sid = str(stat.get("stat_id"))
        # skip display-only / non-scoring stats when possible
        if stat.get("is_only_display_stat") in (1, "1"):
            continue
        categories.append({
            "stat_id": sid,
            "label": stat_map.get(sid) or stat.get("display_name") or stat.get("name"),
            "sort_order": stat.get("sort_order"),
            "position_type": stat.get("position_type"),
        })

    return {
        "league_key": league_info.get("league_key"),
        "league_name": league_info.get("name"),
        "scoring_type": league_info.get("scoring_type"),
        "num_teams": league_info.get("num_teams"),
        "current_week": league_info.get("current_week"),
        "stat_categories": categories,
    }


def parse_league_scoreboard(data: dict) -> dict:
    """Parse /league/{key}/scoreboard — all matchups with category stats per team."""
    league_data = data.get("fantasy_content", {}).get("league", [{}, {}])
    league_info = league_data[0] if league_data else {}
    scoreboard = league_data[1].get("scoreboard", {}) if len(league_data) > 1 else {}
    matchups_root = scoreboard.get("0", {}).get("matchups", {})

    matchups = []
    for i in range(matchups_root.get("count", 0)):
        m = matchups_root.get(str(i), {}).get("matchup", {})
        teams_root = m.get("0", {}).get("teams", {})

        teams = []
        for j in range(teams_root.get("count", 0)):
            t_parts = teams_root.get(str(j), {}).get("team", [[], {}])
            t_info = _extract_info(t_parts[0]) if t_parts else {}
            t_stats = t_parts[1] if len(t_parts) > 1 else {}
            teams.append({
                "team_key": t_info.get("team_key"),
                "name": t_info.get("name"),
                "points": t_stats.get("team_points", {}).get("total"),
                "stats": _parse_team_category_stats(t_stats.get("team_stats", {})),
            })

        matchups.append({
            "status": m.get("status"),
            "is_playoffs": m.get("is_playoffs"),
            "is_tied": m.get("is_tied"),
            "winner_team_key": m.get("winner_team_key"),
            "teams": teams,
            "stat_winners": _parse_stat_winners(m.get("stat_winners", [])),
        })

    return {
        "league_key": league_info.get("league_key"),
        "week": scoreboard.get("week") or league_info.get("current_week"),
        "matchups": matchups,
    }

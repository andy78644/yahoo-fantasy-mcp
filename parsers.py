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
        selected_pos = sel_pos_list[1].get("position") if len(sel_pos_list) > 1 else None

        players.append({
            "name": info.get("name", {}).get("full", "Unknown"),
            "player_key": info.get("player_key"),
            "positions": [p.get("position") for p in info.get("eligible_positions", []) if isinstance(p, dict)],
            "selected_position": selected_pos,
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


def parse_free_agents(data: dict) -> list[dict]:
    """Parse /league/{key}/players;status=FA"""
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
            "percent_owned": _safe_percent_owned(info),
        })
    return players


def _safe_percent_owned(info: dict) -> float:
    po = info.get("percent_owned", {})
    return float(po.get("value", 0)) if isinstance(po, dict) else 0.0


MLB_STAT_NAMES = {
    # 打擊
    "0": "出賽數", "1": "打數", "2": "得分", "3": "安打", "4": "一壘安打", "5": "二壘安打",
    "6": "三壘安打", "7": "全壘打", "8": "打點", "9": "盜壘", "10": "盜壘失敗",
    "11": "四壞球", "12": "故意四壞", "13": "觸身球", "14": "犧牲觸擊", "15": "犧牲飛球",
    "16": "雙殺打", "17": "三振", "18": "打擊率", "19": "上壘率", "20": "長打率",
    "21": "整體攻擊指數", "22": "打席數", "23": "長打數",
    "26": "淨盜壘",
    # 投球
    "27": "投球局數", "28": "先發場次", "29": "勝", "30": "敗", "31": "救援成功",
    "32": "中繼成功", "33": "救援失敗", "34": "防禦率", "35": "每局被上壘率",
    "36": "投手三振", "37": "投手四壞球", "38": "優質先發", "39": "出局數",
    "40": "被安打", "41": "被全壘打", "42": "投手四壞", "43": "自責分",
    "44": "未成功救援", "45": "每九局三振", "46": "每九局四壞", "48": "三振/四壞比",
    "50": "每九局被全壘打", "51": "投手出賽數", "55": "勝+救援+中繼",
    "56": "救援+中繼合計", "57": "揮棒三振", "58": "滾地球%", "59": "FIP",
    "60": "對手整體攻擊指數", "61": "對手打擊率", "62": "救援+中繼",
}

NBA_STAT_NAMES = {
    "0": "出賽數", "1": "先發數", "2": "上場時間",
    "3": "出手次數", "4": "投籃命中", "5": "投籃命中率",
    "6": "三分出手", "7": "三分命中", "8": "三分命中率",
    "9": "罰球出手", "10": "罰球命中", "11": "罰球命中率",
    "12": "進攻籃板", "13": "防守籃板", "14": "籃板",
    "15": "助攻", "16": "抄截", "17": "阻攻", "18": "失誤", "19": "得分", "20": "正負值",
}


def parse_player_stats(data: dict) -> dict:
    """Parse /player/{key}/stats;type={period}"""
    player_parts = data.get("fantasy_content", {}).get("player", [[], {}])
    info = _extract_info(player_parts[0]) if player_parts else {}
    player_stats = player_parts[1].get("player_stats", {}) if len(player_parts) > 1 else {}

    # coverage_type is nested under player_stats["0"]
    coverage_info = player_stats.get("0", {})
    coverage_type = coverage_info.get("coverage_type")

    # Pick stat name mapping based on player key prefix (game id)
    player_key = info.get("player_key", "")
    stat_map = NBA_STAT_NAMES if player_key.startswith("41") else MLB_STAT_NAMES

    named_stats = {}
    for s in player_stats.get("stats", []):
        if isinstance(s, dict) and "stat" in s:
            sid = str(s["stat"]["stat_id"])
            val = s["stat"]["value"]
            if val not in ("-", False, None):
                label = stat_map.get(sid, f"stat_{sid}")
                named_stats[label] = val

    return {
        "name": info.get("name", {}).get("full", "Unknown"),
        "player_key": player_key,
        "team": info.get("editorial_team_full_name", ""),
        "status": info.get("status", "Active"),
        "injury_note": info.get("injury_note", ""),
        "coverage_type": coverage_type,
        "stats": named_stats,
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

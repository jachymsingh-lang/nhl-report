#!/usr/bin/env python3
"""NHL Agent: e-mail o Češích a Slovácích v NHL (odesílání přes Resend)."""
import datetime as dt
import html as _html
import os
import re
import sys
from zoneinfo import ZoneInfo

import requests

PRAGUE = ZoneInfo("Europe/Prague")
SCORE_URL = "https://api-web.nhle.com/v1/score/"
STATS_URL = "https://api.nhle.com/stats/rest/en"
NAT = '("CZE","SVK")'

CZ = {
    'Martin Necas': 'Martin Nečas', 'David Pastrnak': 'David Pastrňák', 'Lukas Dostal': 'Lukáš Dostál',
    'Ondrej Palat': 'Ondřej Palát', 'Tomas Hertl': 'Tomáš Hertl', 'Jiri Kulich': 'Jiří Kulich',
    'David Jiricek': 'David Jiříček', 'Adam Jiricek': 'Adam Jiříček', 'Dalibor Dvorsky': 'Dalibor Dvorský',
    'Erik Cernak': 'Erik Černák', 'Juraj Slafkovsky': 'Juraj Slafkovský', 'Martin Fehervary': 'Martin Fehérváry',
    'Simon Nemec': 'Šimon Nemec', 'Jakub Dobes': 'Jakub Dobeš', 'Martin Pospisil': 'Martin Pospíšil',
    'Dan Vladar': 'Daniel Vladař', 'Daniel Vladar': 'Daniel Vladař', 'Vitek Vanecek': 'Vítek Vaněček',
    'Jakub Vrana': 'Jakub Vrána', 'Tomas Nosek': 'Tomáš Nosek', 'Matej Blumel': 'Matěj Blümel',
    'Lukas Sedlak': 'Lukáš Sedlák', 'Matej Stransky': 'Matěj Stránský', 'Adam Sykora': 'Adam Sýkora',
    'Libor Hajek': 'Libor Hájek', 'Radim Simek': 'Radim Šimek', 'Tomas Tatar': 'Tomáš Tatar',
    'Michal Kempny': 'Michal Kempný', 'Filip Mesar': 'Filip Mešár', 'Adam Ruzicka': 'Adam Růžička',
    'Eduard Sale': 'Eduard Šalé', 'Matyas Sapovaliv': 'Matyáš Šapovaliv', 'Vojtech Port': 'Vojtěch Port',
    'David Spacek': 'David Špaček', 'Jaroslav Chmelar': 'Jaroslav Chmelař', 'Petr Mrazek': 'Petr Mrázek',
    'Jiri Patera': 'Jiří Patera', 'Stanislav Skorvanek': 'Stanislav Škorvánek', 'David Kampf': 'David Kämpf',
    'Ondrej Kase': 'Ondřej Kaše', 'Roman Cervenka': 'Roman Červenka', 'Marko Dano': 'Marko Daňo',
}
FLAG = {"SVK": "🇸🇰", "CZE": "🇨🇿"}

TEAMS = {
    "ANA": "Anaheim Ducks", "BOS": "Boston Bruins", "BUF": "Buffalo Sabres", "CGY": "Calgary Flames",
    "CAR": "Carolina Hurricanes", "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche",
    "CBJ": "Columbus Blue Jackets", "DAL": "Dallas Stars", "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers", "FLA": "Florida Panthers", "LAK": "Los Angeles Kings",
    "MIN": "Minnesota Wild", "MTL": "Montréal Canadiens", "NSH": "Nashville Predators",
    "NJD": "New Jersey Devils", "NYI": "New York Islanders", "NYR": "New York Rangers",
    "OTT": "Ottawa Senators", "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins",
    "SJS": "San Jose Sharks", "SEA": "Seattle Kraken", "STL": "St. Louis Blues",
    "TBL": "Tampa Bay Lightning", "TOR": "Toronto Maple Leafs", "UTA": "Utah Mammoth",
    "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights", "WSH": "Washington Capitals",
    "WPG": "Winnipeg Jets",
}


def tn(abbr):
    return TEAMS.get(abbr, abbr)


def nm(n):
    return CZ.get(n, n)


def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=30, headers={"User-Agent": "nhl-agent"})
    r.raise_for_status()
    return r.json()


def toi(sec):
    s = round(float(sec or 0))
    return f"{s // 60}:{s % 60:02d}"


def pm(v):
    v = v or 0
    return f"+{v}" if v > 0 else str(v)


def cz_date(iso):
    y, m, d = iso.split("-")
    return f"{int(d)}. {int(m)}. {y}"


def season_id(game_date):
    d = dt.date.fromisoformat(game_date)
    y = d.year if d.month >= 9 else d.year - 1
    return f"{y}{y + 1}"


def num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def gol(n):
    return "gól" if n == 1 else ("góly" if 2 <= n <= 4 else "gólů")


def bod(n):
    return "bod" if n == 1 else ("body" if 2 <= n <= 4 else "bodů")


def season_maps(game_date):
    """Sezónní statistiky Čechů a Slováků (součet přes všechny týmy, za které hráč hrál)."""
    sid = season_id(game_date)
    base = {"isAggregate": "false", "isGame": "false", "limit": "300"}
    exp = f"seasonId={sid} and gameTypeId=2 and nationalityCode in {NAT}"
    ss, sg = {}, {}
    try:
        for p in get_json(f"{STATS_URL}/skater/summary", {**base, "cayenneExp": exp}).get("data", []):
            x = ss.setdefault(p["playerId"], {"gp": 0, "g": 0, "a": 0, "p": 0})
            x["gp"] += p.get("gamesPlayed") or 0
            x["g"] += p.get("goals") or 0
            x["a"] += p.get("assists") or 0
            x["p"] += p.get("points") or 0
        for p in get_json(f"{STATS_URL}/goalie/summary", {**base, "cayenneExp": exp}).get("data", []):
            x = sg.setdefault(p["playerId"], {"gp": 0, "w": 0, "saves": 0, "sa": 0})
            x["gp"] += p.get("gamesPlayed") or 0
            x["w"] += p.get("wins") or 0
            x["saves"] += p.get("saves") or 0
            x["sa"] += p.get("shotsAgainst") or 0
    except (requests.RequestException, KeyError, ValueError) as exc:
        print(f"[WARN] Sezónní statistiky se nepodařilo načíst: {exc}", file=sys.stderr)
    return ss, sg


def season_str(pid, goalie, ss, sg):
    if goalie:
        s = sg.get(pid)
        if not s:
            return "–"
        pct = f"{s['saves'] / s['sa'] * 100:.1f}".replace(".", ",") if s["sa"] else "–"
        return f"{s['w']} V · {pct} %"
    s = ss.get(pid)
    if not s:
        return "–"
    return f"{s['p']} B ({s['g']}+{s['a']}) · {s['gp']} z"


def fetch(game_date):
    score = get_json(SCORE_URL + game_date)
    day = f'gameDate>="{game_date}" and gameDate<="{game_date}" and nationalityCode in {NAT}'
    bio = f"seasonId={season_id(game_date)} and nationalityCode in {NAT}"
    base = {"isAggregate": "false", "isGame": "true", "limit": "100"}
    bbase = {"isAggregate": "false", "isGame": "false", "limit": "200"}
    skaters = get_json(f"{STATS_URL}/skater/summary", {**base, "cayenneExp": day}).get("data", [])
    goalies = get_json(f"{STATS_URL}/goalie/summary", {**base, "cayenneExp": day}).get("data", [])
    rs = get_json(f"{STATS_URL}/skater/bios", {**bbase, "cayenneExp": bio}).get("data", [])
    rg = get_json(f"{STATS_URL}/goalie/bios", {**bbase, "cayenneExp": bio}).get("data", [])
    ss, sg = season_maps(game_date)
    return score, skaters, goalies, rs, rg, ss, sg


def build(game_date, score, skaters, goalies, rs, rg, ss, sg):
    nat = {}
    for p in rs + rg:
        nat[p["playerId"]] = {"code": p.get("nationalityCode"), "team": p.get("currentTeamAbbrev")}

    games = [g for g in score.get("games", []) if g.get("gameDate") == game_date]
    by_id, cards = {}, []
    for g in games:
        by_id[g["id"]] = g
        t = dt.datetime.fromisoformat(g["startTimeUTC"].replace("Z", "+00:00")).astimezone(PRAGUE).strftime("%H:%M")
        lpt = (g.get("gameOutcome") or {}).get("lastPeriodType")
        ext = "po prodloužení" if lpt == "OT" else ("po nájezdech" if lpt == "SO" else "")
        done = g.get("gameState") in ("OFF", "FINAL")
        counts = {}
        for x in g.get("goals", []):
            n = (x.get("name") or {}).get("default", "")
            counts[n] = counts.get(n, 0) + 1
        scorers = " · ".join(n + (f" ×{c}" if c > 1 else "") for n, c in counts.items())
        a, h = g["awayTeam"], g["homeTeam"]
        cards.append({
            "status": ("Dohráno" + (f" {ext}" if ext else "")) if done else "Probíhá / neodehráno",
            "time": t, "away": a["abbrev"], "home": h["abbrev"],
            "as": a.get("score", "-"), "hs": h.get("score", "-"),
            "scorers": scorers or "bez gólů", "done": done, "ext": ext,
        })

    def result_for(gid, team):
        g = by_id.get(gid)
        if not g:
            return "", "", None, None
        home = g["homeTeam"]["abbrev"] == team
        my = g["homeTeam"]["score"] if home else g["awayTeam"]["score"]
        op = g["awayTeam"]["score"] if home else g["homeTeam"]["score"]
        lpt = (g.get("gameOutcome") or {}).get("lastPeriodType")
        suf = " pp" if lpt == "OT" else (" sn" if lpt == "SO" else "")
        opp = g["awayTeam"]["abbrev"] if home else g["homeTeam"]["abbrev"]
        return opp, f"{my}:{op}{suf}", (my or 0) > (op or 0), home

    rows = []
    for p in skaters:
        opp, res, win, home = result_for(p.get("gameId"), p.get("teamAbbrev"))
        code = (nat.get(p["playerId"]) or {}).get("code") or "CZE"
        rows.append({
            "sort": p["points"] * 100 + p["goals"] * 10 + (p.get("timeOnIcePerGame") or 0) / 10000,
            "name": nm(p["skaterFullName"]), "nat": code, "goalie": False,
            "team": p["teamAbbrev"], "opp": opp, "res": res, "win": win,
            "g": p["goals"], "a": p["assists"], "b": p["points"], "pm": pm(p.get("plusMinus")),
            "shots": str(p.get("shots", 0)), "toi": toi(p.get("timeOnIcePerGame")),
            "season": season_str(p["playerId"], False, ss, sg),
            "p": p,
        })
    for p in goalies:
        opp, res, win, home = result_for(p.get("gameId"), p.get("teamAbbrev"))
        code = (nat.get(p["playerId"]) or {}).get("code") or "CZE"
        sa = p.get("shotsAgainst") or 0
        pct = f"{p['saves'] / sa * 100:.1f}".replace(".", ",") if sa else "–"
        rows.append({
            "sort": -1, "name": nm(p["goalieFullName"]), "nat": code, "goalie": True,
            "team": p["teamAbbrev"], "opp": opp, "res": res, "win": win,
            "g": "–", "a": "–", "b": "–", "pm": "–",
            "shots": f"{p['saves']}/{sa} zák. ({pct} %)", "toi": toi(p.get("timeOnIce")),
            "season": season_str(p["playerId"], True, ss, sg),
            "p": p, "pct": pct,
        })
    rows.sort(key=lambda r: -r["sort"])

    played = {p["playerId"] for p in skaters} | {p["playerId"] for p in goalies}
    not_played = sorted(
        {nm(p.get("skaterFullName") or p.get("goalieFullName")) for p in rs + rg
         if p["playerId"] not in played and p.get("currentTeamAbbrev")},
        key=str.lower,
    )
    return games, cards, rows, not_played


def upcoming_players(next_date, rs, rg):
    """Dnešní zápasy NHL (včetně nočních) a kteří Češi a Slováci za dané týmy hrají (podle soupisek)."""
    try:
        score = get_json(SCORE_URL + next_date)
    except requests.RequestException as exc:
        print(f"[WARN] Dnešní program se nepodařilo načíst: {exc}", file=sys.stderr)
        return []

    by_team = {}
    for p in rs + rg:
        team = p.get("currentTeamAbbrev")
        if not team:
            continue
        by_team.setdefault(team, []).append({
            "name": nm(p.get("skaterFullName") or p.get("goalieFullName")),
            "nat": p.get("nationalityCode") or "",
            "team": team,
            "goalie": "goalieFullName" in p,
        })

    out = []
    for g in sorted(score.get("games", []), key=lambda x: x.get("startTimeUTC", "")):
        if g.get("gameDate") != next_date:
            continue
        a, h = g["awayTeam"]["abbrev"], g["homeTeam"]["abbrev"]
        players = by_team.get(a, []) + by_team.get(h, [])
        if not players:
            continue
        out.append({
            "away": a, "home": h,
            "players": sorted(players, key=lambda x: (x["team"], x["name"])),
        })
    return out


# ----------------------------- TEXT A ZAJÍMAVOSTI -----------------------------


def team_abbr(x):
    t = x.get("teamAbbrev")
    if isinstance(t, dict):
        t = t.get("default")
    return t or ""


def facts_for(games):
    """Zajímavosti spočítané z dat té noci (oficiální rekordy a milníky NHL API neposkytuje)."""
    facts, scorer = [], {}
    best_g, best_t = None, -1
    big_g, big_m = None, -1
    ot, so, shut = [], [], []

    for g in games:
        if g.get("gameState") not in ("OFF", "FINAL"):
            continue
        a, h = g["awayTeam"], g["homeTeam"]
        sa, sh = a.get("score") or 0, h.get("score") or 0
        line = f'{tn(a["abbrev"])} {sa}:{sh} {tn(h["abbrev"])}'
        if sa + sh > best_t:
            best_t, best_g = sa + sh, line
        if abs(sa - sh) > big_m:
            big_m, big_g = abs(sa - sh), g
        lpt = (g.get("gameOutcome") or {}).get("lastPeriodType")
        if lpt == "OT":
            ot.append(line)
        elif lpt == "SO":
            so.append(line)
        if sa == 0 or sh == 0:
            w, l = (h, a) if sa == 0 else (a, h)
            shut.append(f'{tn(w["abbrev"])} – {tn(l["abbrev"])} {max(sa, sh)}:0')
        for x in g.get("goals", []):
            key = ((x.get("name") or {}).get("default", ""), team_abbr(x))
            scorer[key] = scorer.get(key, 0) + 1

    for (name, team), c in scorer.items():
        if c >= 3:
            facts.append(f"🎩 **Hattrick:** {name} ({tn(team)}), {c} {gol(c)}")
    twos = [f"{name} ({tn(team)})" for (name, team), c in scorer.items() if c == 2]
    if twos:
        facts.append("🔥 **Dva góly:** " + ", ".join(twos[:4]))
    if big_g is not None and big_m >= 4:
        a, h = big_g["awayTeam"], big_g["homeTeam"]
        sa, sh = a.get("score") or 0, h.get("score") or 0
        w, l = (a, h) if sa > sh else (h, a)
        facts.append(f'💥 **Největší rozdíl:** {tn(w["abbrev"])} porazil {tn(l["abbrev"])} o **{big_m} {gol(big_m)}**')
    if best_g and best_t >= 8:
        facts.append(f"🎯 **Nejvíc gólů:** {best_g} ({best_t} {gol(best_t)})")
    for s in shut:
        facts.append(f"🧱 **Čisté konto:** {s}")
    for s in ot:
        facts.append(f"⏱️ **Prodloužení:** {s}")
    for s in so:
        facts.append(f"🥅 **Nájezdy:** {s}")
    return facts[:5]


def article(game_date, games, cards, rows, not_played):
    n = len(cards)
    word = "zápas" if n == 1 else ("zápasy" if n < 5 else "zápasů")
    total = sum((g["awayTeam"].get("score") or 0) + (g["homeTeam"].get("score") or 0) for g in games)
    out = [f"V noci na {cz_date(game_date)} se v NHL hrálo **{n} {word}** a padlo **{total} {gol(total)}**."]

    skaters = [r for r in rows if not r["goalie"]]
    goalies = [r for r in rows if r["goalie"]]
    scorers = [r for r in skaters if isinstance(r["b"], int) and r["b"] > 0]

    if scorers:
        b = scorers[0]
        out.append(f'Nejlepší z Čechů a Slováků: **{b["name"]}** ({tn(b["team"])}), '
                   f'**{b["b"]} {bod(b["b"])}** ({b["g"]}+{b["a"]}), v sezóně **{b["season"]}**.')
        if len(scorers) > 1:
            more = ", ".join(f'**{r["name"]}** ({r["b"]})' for r in scorers[1:])
            out.append(f"Bodovali také: {more}.")
    elif skaters:
        out.append("Žádný Čech ani Slovák v poli nebodoval.")
    else:
        out.append("Žádný Čech ani Slovák v noci nenastoupil.")

    for r in goalies:
        w = "výhra" if r["win"] else "prohra"
        out.append(f'Brankář **{r["name"]}** ({tn(r["team"])}): {r["shots"]}, {w}.')
    if not_played:
        out.append(f"Nenastoupilo dalších **{len(not_played)}** Čechů a Slováků.")
    return out, facts_for(games)


def compact_text(game_date, rows, upcoming):
    head = f"🏒 NHL report — {cz_date(game_date)}"
    if not rows:
        text = head + "\n\n📊 Češi a Slováci v noci nehráli."
    else:
        lines = []
        for r in rows:
            if r["goalie"]:
                lines.append(f'• {r["name"]} ({r["team"]}): {r["shots"]} | sezóna: {r["season"]}')
            else:
                lines.append(f'• {r["name"]} ({r["team"]}): {r["g"]}+{r["a"]}={r["b"]} B, {r["pm"]}, {r["toi"]} | sezóna: {r["season"]}')
        text = head + "\n\n📊 Češi a Slováci:\n" + "\n".join(lines)
    if upcoming:
        today_lines = []
        for u in upcoming:
            names = ", ".join(f'{x["name"]} ({x["team"]})' for x in u["players"])
            today_lines.append(f'• {tn(u["away"])} @ {tn(u["home"])}: {names}')
        text += "\n\n📅 Dnes hrají:\n" + "\n".join(today_lines)
    return text


# ----------------------------- VZHLED E-MAILU -----------------------------


def to_html(game_date, paras, facts, cards, rows, upcoming, stats):
    e = lambda s: _html.escape(str(s if s is not None else ""))
    C = dict(bg="#0b1220", card="#111a2e", line="#1f2b45", text="#e6ecf5", mute="#8a9bb8",
             acc="#38bdf8", win="#22c55e", loss="#ef4444", gold="#fbbf24")

    def fmt(t):
        return re.sub(r"\*\*(.+?)\*\*", r'<b style="color:#ffffff;">\1</b>', e(t))

    d = cz_date(game_date)

    def sec(title, inner, color=None):
        color = color or C["acc"]
        return (f'<tr><td style="padding:0 0 16px;"><div style="background:{C["card"]};border:1px solid {C["line"]};'
                f'border-top:3px solid {color};border-radius:16px;padding:20px;">'
                f'<div style="font-size:12px;color:{color};font-weight:800;letter-spacing:1.2px;text-transform:uppercase;'
                f'margin-bottom:14px;">{title}</div>{inner}</div></td></tr>')

    # --- hlavička ---
    header = (f'<tr><td style="padding:0 0 16px;"><div style="background:#0c4a6e;'
              f'background-image:linear-gradient(135deg,#0ea5e9,#1e3a8a);border-radius:16px;padding:22px 24px;">'
              f'<span style="background:#ffffff;color:#0c4a6e;font-weight:900;border-radius:10px;padding:8px 11px;font-size:13px;">NHL</span>'
              f'<span style="font-size:24px;font-weight:800;color:#ffffff;margin-left:12px;">NHL Agent</span>'
              f'<div style="font-size:13px;color:#dbeafe;margin-top:10px;">Report za noc na {e(d)}</div></div></td></tr>')

    # --- dlaždice ---
    def tile(v, label):
        return (f'<td align="center" style="padding:4px;width:33%;"><div style="background:{C["bg"]};border:1px solid {C["line"]};'
                f'border-radius:12px;padding:14px 6px;"><div style="font-size:28px;font-weight:800;color:{C["acc"]};">{e(v)}</div>'
                f'<div style="font-size:10px;color:{C["mute"]};text-transform:uppercase;letter-spacing:.7px;margin-top:3px;">{e(label)}</div>'
                f'</div></td>')

    tiles = (f'<table width="100%" style="border-collapse:collapse;margin-bottom:14px;"><tr>'
             f'{tile(stats["games"], "zápasů")}{tile(stats["goals"], "gólů")}{tile(stats["points"], "bodů Čechů a Slováků")}'
             f'</tr></table>')

    ps = "".join(f'<p style="margin:0 0 10px;line-height:1.6;color:{C["text"]};font-size:15px;">{fmt(p)}</p>' for p in paras)
    fs = "".join(
        f'<div style="padding:9px 12px;background:{C["bg"]};border-left:3px solid {C["gold"]};border-radius:8px;'
        f'margin-bottom:8px;font-size:14px;line-height:1.5;color:{C["text"]};">{fmt(f)}</div>' for f in facts)
    facts_html = (f'<div style="font-size:11px;color:{C["gold"]};font-weight:800;letter-spacing:1px;text-transform:uppercase;'
                  f'margin:14px 0 8px;">Zajímavosti noci</div>{fs}') if facts else ""
    summary = sec(f"Co se stalo", tiles + ps + facts_html)

    # --- tabulka výkonů (beze změny) ---
    def th(t, al="center"):
        return f'<th style="text-align:{al};padding:8px 6px;font-size:11px;color:{C["mute"]};border-bottom:1px solid {C["line"]};">{t}</th>'

    def td(t, al="center", extra=""):
        return f'<td style="text-align:{al};padding:9px 6px;font-size:13px;color:{C["text"]};border-bottom:1px solid {C["line"]};{extra}">{t}</td>'

    body = ""
    for r in rows:
        wl = "" if r["win"] is None else (f' <span style="color:{C["win"]};">W</span>' if r["win"] else f' <span style="color:{C["loss"]};">L</span>')
        body += ("<tr>" + td(f"<b>{e(r['name'])}</b>" + ("<br><small>brankář</small>" if r["goalie"] else ""), "left")
                 + td(f'{FLAG.get(r["nat"], "")} {e(r["nat"])}', "left") + td(f'{e(r["team"])} vs {e(r["opp"])}', "left")
                 + td(e(r["res"]) + wl) + td(e(r["g"])) + td(e(r["a"])) + td(f"<b>{e(r['b'])}</b>") + td(e(r["pm"]))
                 + td(e(r["shots"])) + td(e(r["toi"])) + td(f"<b>{e(r['season'])}</b>") + "</tr>")
    table = (f'<table width="100%" style="border-collapse:collapse;"><tr>{th("Hráč","left")}{th("Národ","left")}{th("Zápas","left")}'
             f'{th("Výsledek")}{th("G")}{th("A")}{th("B")}{th("+/-")}{th("Střely / zákroky")}{th("Čas")}{th("Sezóna")}</tr>{body}</table>') if rows \
        else f'<p style="color:{C["mute"]};">Žádný Čech ani Slovák v noci nenastoupil.</p>'
    perf = sec(f"Výkony Čechů a Slováků · {e(d)}", f'<div style="overflow-x:auto;">{table}</div>')

    # --- dnes hrají ---
    if upcoming:
        ucards = ""
        for u in upcoming:
            lines = "".join(
                f'<div style="font-size:13px;color:{C["text"]};padding:4px 0;">{FLAG.get(x["nat"], "")} <b>{e(x["name"])}</b> '
                f'<span style="color:{C["mute"]};">· {e(tn(x["team"]))}{" · brankář" if x["goalie"] else ""}</span></div>'
                for x in u["players"])
            ucards += (f'<div style="background:{C["bg"]};border:1px solid {C["line"]};border-radius:12px;padding:14px;margin-bottom:10px;">'
                       f'<div style="font-size:15px;font-weight:700;color:{C["text"]};">{e(tn(u["away"]))} '
                       f'<span style="color:{C["mute"]};font-weight:400;">@</span> {e(tn(u["home"]))}</div>'
                       f'<div style="margin-top:8px;border-top:1px solid {C["line"]};padding-top:6px;">{lines}</div></div>')
        upcoming_html = ucards + f'<div style="font-size:11px;color:{C["mute"]};">Podle soupisek týmů, nastoupení není jisté (zranění, vynechání).</div>'
    else:
        upcoming_html = f'<p style="color:{C["mute"]};margin:0;">Dnes žádný Čech ani Slovák nehraje.</p>'
    today = sec("Dnes hrají", upcoming_html, C["win"])

    # --- noční program ---
    def team_row(abbr, score, win):
        nc = C["text"] if win else C["mute"]
        sc = C["win"] if win else C["mute"]
        return (f'<tr><td style="font-size:14px;font-weight:{700 if win else 500};color:{nc};padding:3px 0;">{e(tn(abbr))}</td>'
                f'<td align="right" style="font-size:20px;font-weight:800;color:{sc};padding:3px 0;">{e(score)}</td></tr>')

    cs = []
    for c in cards:
        a, h = num(c["as"]), num(c["hs"])
        a_win = c["done"] and a is not None and h is not None and a > h
        h_win = c["done"] and a is not None and h is not None and h > a
        cs.append(
            f'<td style="padding:6px;vertical-align:top;width:50%;"><div style="background:{C["bg"]};border:1px solid {C["line"]};border-radius:12px;padding:14px;">'
            f'<div style="font-size:11px;color:{C["win"]};text-transform:uppercase;font-weight:700;">{e(c["status"])}</div>'
            f'<div style="font-size:11px;color:{C["mute"]};margin-bottom:8px;">{e(c["time"])} (Praha)</div>'
            f'<table width="100%" style="border-collapse:collapse;">{team_row(c["away"], c["as"], a_win)}{team_row(c["home"], c["hs"], h_win)}</table>'
            f'<div style="font-size:12px;color:{C["mute"]};margin-top:8px;border-top:1px solid {C["line"]};padding-top:8px;">{e(c["scorers"])}</div></div></td>')
    grid = ""
    for i in range(0, len(cs), 2):
        grid += "<tr>" + cs[i] + (cs[i + 1] if i + 1 < len(cs) else '<td style="width:50%;"></td>') + "</tr>"
    night = sec("Noční program NHL", f'<table width="100%" style="border-collapse:collapse;">{grid}</table>', "#a78bfa")

    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
            f'<body style="margin:0;background:{C["bg"]};font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
            f'<table width="100%" style="background:{C["bg"]};"><tr><td align="center" style="padding:24px 12px;">'
            f'<table width="100%" style="max-width:720px;border-collapse:collapse;">'
            + header + summary + perf + today + night
            + f'<tr><td style="font-size:11px;color:{C["mute"]};text-align:center;padding-top:4px;">Data: veřejné NHL API · odesláno automaticky v 06:30 (Europe/Prague)</td></tr>'
            f'</table></td></tr></table></body></html>')


def send_mail(subject, html_body, plain):
    to = os.environ.get("MAIL_TO") or os.environ["GMAIL_USER"]
    key = os.environ["RESEND_API_KEY"].strip()
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "from": "NHL Agent <onboarding@resend.dev>",
            "to": [to.strip()],
            "subject": subject,
            "html": html_body,
            "text": plain,
        },
        timeout=30,
    )
    if not r.ok:
        print(r.text, file=sys.stderr)
    r.raise_for_status()


def main():
    now = dt.datetime.now(PRAGUE)
    if os.environ.get("FORCE") != "1" and now.hour != 6:
        print(f"V Praze je {now:%H:%M}, čekám na 6. hodinu, nic neposílám.")
        return
    game_date = os.environ.get("DATE") or (now - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (dt.date.fromisoformat(game_date) + dt.timedelta(days=1)).isoformat()

    score, skaters, goalies, rs, rg, ss, sg = fetch(game_date)
    games, cards, rows, not_played = build(game_date, score, skaters, goalies, rs, rg, ss, sg)
    if not games:
        print(f"Na {game_date} se nehrálo, e-mail neposílám.")
        return

    upcoming = upcoming_players(next_date, rs, rg)
    paras, facts = article(game_date, games, cards, rows, not_played)
    stats = {
        "games": len(games),
        "goals": sum((g["awayTeam"].get("score") or 0) + (g["homeTeam"].get("score") or 0) for g in games),
        "points": sum(r["b"] for r in rows if not r["goalie"] and isinstance(r["b"], int)),
    }
    compact = compact_text(game_date, rows, upcoming)
    html_body = to_html(game_date, paras, facts, cards, rows, upcoming, stats)
    subject = f"🏒 NHL report — {cz_date(game_date)}"
    if os.environ.get("DRY_RUN") == "1":
        open("preview.html", "w", encoding="utf-8").write(html_body)
        print(compact)
        print("Náhled uložen do preview.html")
        return
    send_mail(subject, html_body, compact)
    print("E-mail odeslán.")


if __name__ == "__main__":
    main()

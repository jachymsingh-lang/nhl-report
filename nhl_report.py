#!/usr/bin/env python3
"""Puck Morning Report: ranní e-mail o Češích a Slovácích v NHL."""
import datetime as dt
import html as _html
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
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


def nm(n):
    return CZ.get(n, n)


def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=30, headers={"User-Agent": "puck-morning-report"})
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
    return score, skaters, goalies, rs, rg


def build(game_date, score, skaters, goalies, rs, rg):
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


def article(game_date, cards, rows, not_played):
    out = []
    n = len(cards)
    word = "zápas" if n == 1 else ("zápasy" if n < 5 else "zápasů")
    res = ", ".join(f'{c["away"]} {c["as"]}:{c["hs"]} {c["home"]}' + (f' ({c["ext"]})' if c["ext"] else "") for c in cards)
    out.append(f"V noci na {cz_date(game_date)} se v NHL hrálo {n} {word}. Výsledky (hosté první): {res}.")

    skaters = [r for r in rows if not r["goalie"]]
    goalies = [r for r in rows if r["goalie"]]

    def line(r):
        w = "výhra" if r["win"] else "prohra"
        return (f'{r["name"]} ({r["team"]} vs {r["opp"]}, {r["res"]}, {w}): {r["g"]} G, {r["a"]} A, '
                f'{r["b"]} B, +/- {r["pm"]}, {r["shots"]} střel, čas na ledě {r["toi"]}')

    if skaters:
        out.append("Nejlepší výkon Čecha nebo Slováka: " + line(skaters[0]) + ".")
    if len(skaters) > 1:
        out.append("Další Češi a Slováci: " + "; ".join(line(r) for r in skaters[1:]) + ".")
    for r in goalies:
        w = "výhra" if r["win"] else "prohra"
        out.append(f'Brankář {r["name"]} ({r["team"]} vs {r["opp"]}, {r["res"]}, {w}): {r["shots"]}, odchytal {r["toi"]}.')
    if not rows:
        out.append("Žádný Čech ani Slovák v noci nenastoupil.")
    if not_played:
        out.append("Do hry nezasáhli: " + ", ".join(not_played) + ".")
    return out


def compact_text(game_date, rows):
    head = f"🏒 NHL ranní report — {cz_date(game_date)}"
    if not rows:
        return head + "\n\n📊 Češi a Slováci v noci nehráli."
    lines = []
    for r in rows:
        if r["goalie"]:
            lines.append(f'• {r["name"]} ({r["team"]}): {r["shots"]}')
        else:
            lines.append(f'• {r["name"]} ({r["team"]}): {r["g"]}+{r["a"]}={r["b"]} B, {r["pm"]}, {r["toi"]}')
    return head + "\n\n📊 Češi a Slováci:\n" + "\n".join(lines)


def to_html(game_date, paras, cards, rows, compact):
    e = lambda s: _html.escape(str(s if s is not None else ""))
    C = dict(bg="#0b1220", card="#111a2e", line="#1f2b45", text="#e6ecf5", mute="#8a9bb8", acc="#38bdf8", win="#22c55e", loss="#ef4444")

    ps = "".join(f'<p style="margin:0 0 14px;line-height:1.6;color:{C["text"]};font-size:15px;">{e(p)}</p>' for p in paras)

    cs = []
    for c in cards:
        cs.append(
            f'<td style="padding:6px;vertical-align:top;width:50%;"><div style="background:{C["bg"]};border:1px solid {C["line"]};border-radius:10px;padding:12px;">'
            f'<div style="font-size:11px;color:{C["win"]};text-transform:uppercase;">{e(c["status"])}</div>'
            f'<div style="font-size:11px;color:{C["mute"]};margin-bottom:8px;">{e(c["time"])} (Praha)</div>'
            f'<table width="100%" style="border-collapse:collapse;font-size:18px;font-weight:700;color:{C["text"]};">'
            f'<tr><td>{e(c["away"])}</td><td align="right">{e(c["as"])}</td></tr>'
            f'<tr><td>{e(c["home"])}</td><td align="right">{e(c["hs"])}</td></tr></table>'
            f'<div style="font-size:12px;color:{C["mute"]};margin-top:8px;">{e(c["scorers"])}</div></div></td>')
    grid = ""
    for i in range(0, len(cs), 2):
        grid += "<tr>" + cs[i] + (cs[i + 1] if i + 1 < len(cs) else '<td style="width:50%;"></td>') + "</tr>"

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
                 + td(e(r["shots"])) + td(e(r["toi"])) + "</tr>")
    table = (f'<table width="100%" style="border-collapse:collapse;"><tr>{th("Hráč","left")}{th("Národ","left")}{th("Zápas","left")}'
             f'{th("Výsledek")}{th("G")}{th("A")}{th("B")}{th("+/-")}{th("Střely / zákroky")}{th("Čas")}</tr>{body}</table>') if rows \
        else f'<p style="color:{C["mute"]};">Žádný Čech ani Slovák v noci nenastoupil.</p>'

    def sec(title, inner):
        return (f'<tr><td style="padding:0 0 16px;"><div style="background:{C["card"]};border:1px solid {C["line"]};border-radius:14px;padding:20px;">'
                f'<div style="font-size:12px;color:{C["acc"]};font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:14px;">{title}</div>{inner}</div></td></tr>')

    d = cz_date(game_date)
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>'
            f'<body style="margin:0;background:{C["bg"]};font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
            f'<table width="100%" style="background:{C["bg"]};"><tr><td align="center" style="padding:24px 12px;">'
            f'<table width="100%" style="max-width:720px;border-collapse:collapse;">'
            f'<tr><td style="padding:0 0 18px;"><span style="background:{C["acc"]};color:{C["bg"]};font-weight:900;border-radius:10px;padding:10px 12px;">PMR</span>'
            f'<span style="font-size:20px;font-weight:800;color:{C["text"]};margin-left:12px;">Puck Morning Report</span></td></tr>'
            + sec(f"Ranní zpráva — noc na {e(d)}", ps)
            + sec("Noční program NHL", f'<table width="100%" style="border-collapse:collapse;">{grid}</table>')
            + sec(f"Výkony Čechů a Slováků · {e(d)}", f'<div style="overflow-x:auto;">{table}</div>')
            + sec("Rychlý přehled", f'<pre style="margin:0;white-space:pre-wrap;font-family:inherit;font-size:14px;line-height:1.55;color:{C["text"]};">{e(compact)}</pre>')
            + f'<tr><td style="font-size:11px;color:{C["mute"]};text-align:center;">Data: veřejné NHL API · odesláno automaticky v 06:30 (Europe/Prague)</td></tr>'
            f'</table></td></tr></table></body></html>')


def send_mail(subject, html_body, plain):
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("MAIL_TO") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, formataddr(("Puck Morning Report", user)), to
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)


def main():
    now = dt.datetime.now(PRAGUE)
    if os.environ.get("FORCE") != "1" and now.hour != 6:
        print(f"V Praze je {now:%H:%M}, čekám na 6. hodinu, nic neposílám.")
        return
    game_date = os.environ.get("DATE") or (now - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    games, cards, rows, not_played = build(game_date, *fetch(game_date))
    if not games:
        print(f"Na {game_date} se nehrálo, e-mail neposílám.")
        return
    compact = compact_text(game_date, rows)
    html_body = to_html(game_date, article(game_date, cards, rows, not_played), cards, rows, compact)
    subject = f"🏒 NHL ranní report — {cz_date(game_date)}"
    if os.environ.get("DRY_RUN") == "1":
        open("preview.html", "w", encoding="utf-8").write(html_body)
        print(compact)
        print("Náhled uložen do preview.html")
        return
    send_mail(subject, html_body, compact)
    print("E-mail odeslán.")


if __name__ == "__main__":
    main()

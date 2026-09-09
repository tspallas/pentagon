#!/usr/bin/env python3
"""
Build The Pentagon (thepentagon.football).

Pulls NFL regular-season standings from ESPN's public feed, merges them with the
league roster data in data/seasons.json, and writes a fully static index.html.

No dependencies beyond the Python standard library.

    python3 scripts/build.py            # refresh live seasons, use cache for finished ones
    python3 scripts/build.py --all      # re-fetch every season
    python3 scripts/build.py --offline  # cache only, never hit the network
"""
import json, os, sys, urllib.request, urllib.error, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, CACHE = os.path.join(ROOT, "data"), os.path.join(ROOT, "data", "standings")
FEED = "https://site.api.espn.com/apis/v2/sports/football/nfl/standings?season={y}&seasontype=2"
GAMES_PER_TEAM = 17

ABBR = {"Cardinals":"ARI","Falcons":"ATL","Ravens":"BAL","Bills":"BUF","Panthers":"CAR",
        "Bears":"CHI","Bengals":"CIN","Browns":"CLE","Cowboys":"DAL","Broncos":"DEN",
        "Lions":"DET","Packers":"GB","Texans":"HOU","Colts":"IND","Jaguars":"JAX",
        "Chiefs":"KC","Chargers":"LAC","Rams":"LAR","Raiders":"LV","Dolphins":"MIA",
        "Vikings":"MIN","Patriots":"NE","Saints":"NO","Giants":"NYG","Jets":"NYJ",
        "Eagles":"PHI","Steelers":"PIT","Seahawks":"SEA","49ers":"SF","Buccaneers":"TB",
        "Titans":"TEN","Commanders":"WSH"}
ALIAS = {"Boys":"Cowboys","Niners":"49ers","Jags":"Jaguars","Pats":"Patriots",
         "Cards":"Cardinals","Bucs":"Buccaneers","Football Team":"Commanders",
         "Washington":"Commanders","Redskins":"Commanders","Oakland":"Raiders"}


def abbr(name):
    n = ALIAS.get(name, name)
    if n in ABBR:
        return ABBR[n]
    if n.upper() in ABBR.values():
        return n.upper()
    raise SystemExit(f"build.py: unknown team name {name!r} in data/seasons.json")


# ESPN's edge is picky about User-Agent and has changed which ones it accepts.
# Try a few rather than betting the whole build on one string.
AGENTS = ["curl/8.7.1", "curl/8.0", "Wget/1.21", "python-urllib/3"]


def _get(url):
    last = None
    for ua in AGENTS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
    raise last


def fetch(year):
    """Pull one season's standings from ESPN. Returns {ABBR: [w, l, t]}."""
    doc = _get(FEED.format(y=year))
    out = {}
    for conf in doc.get("children", []):
        for e in conf.get("standings", {}).get("entries", []):
            st = {s["name"]: s.get("value") for s in e.get("stats", [])}
            key = abbr(e["team"]["displayName"].split()[-1])
            out[key] = [int(st.get("wins", 0)), int(st.get("losses", 0)), int(st.get("ties", 0))]
    if len(out) != 32:
        raise ValueError(f"expected 32 teams for {year}, got {len(out)}")
    return out


def standings(year, mode):
    """Fetch with cache fallback. Never lets a network blip destroy good data."""
    path = os.path.join(CACHE, f"{year}.json")
    cached = json.load(open(path)) if os.path.exists(path) else None
    if mode == "offline":
        if cached is None:
            raise SystemExit(f"build.py: --offline but no cache for {year}")
        return cached, False
    # A finished season never changes; don't re-fetch unless asked.
    if cached and mode != "all" and sum(sum(v) for v in cached.values()) >= 32 * GAMES_PER_TEAM:
        return cached, False
    try:
        fresh = fetch(year)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
        if cached is None:
            raise SystemExit(f"build.py: could not fetch {year} and no cache exists ({e})")
        print(f"  {year}: fetch failed ({e}) — keeping cache", file=sys.stderr)
        return cached, False
    changed = fresh != cached
    if changed:
        os.makedirs(CACHE, exist_ok=True)
        with open(path, "w") as f:
            json.dump(fresh, f, indent=1, sort_keys=True)
    return fresh, changed


def draft_of(season, roster_abbrs):
    """Derive draft picks. Absolute pick numbers only when the seat order is known."""
    seats, size = season.get("seats"), len(next(iter(roster_abbrs.values())))
    picks = []
    for p, teams in roster_abbrs.items():
        for i, ab in enumerate(teams):
            rd = i + 1
            pick = None
            if seats:
                s = seats.index(p)
                n = len(seats)
                # snake: odd rounds run left to right, even rounds right to left
                pick = (rd - 1) * n + (s + 1 if rd % 2 else n - s)
            picks.append({"p": p, "ab": ab, "rd": rd, "pick": pick})
    picks.sort(key=lambda d: (d["pick"] if d["pick"] else 0, d["rd"], d["p"]))
    return picks, size


def main():
    mode = "all" if "--all" in sys.argv else "offline" if "--offline" in sys.argv else "auto"
    cfg = json.load(open(os.path.join(DATA, "seasons.json")))
    league, out_seasons, rec, any_change = cfg["league"], {}, {}, False

    for year in sorted(cfg["seasons"]):
        s = cfg["seasons"][year]
        table, changed = standings(int(year), mode)
        any_change = any_change or changed
        rec[year] = table

        rosters = {p: [abbr(t) for t in teams] for p, teams in s["rosters"].items()}
        seen = [ab for teams in rosters.values() for ab in teams]
        if len(seen) != len(set(seen)):
            dupes = sorted({x for x in seen if seen.count(x) > 1})
            raise SystemExit(f"build.py: {year} drafts these teams twice: {', '.join(dupes)}")

        picks, size = draft_of(s, rosters)
        played = sum(sum(v) for v in table.values())
        status = "final" if played >= 32 * GAMES_PER_TEAM else "live"

        out_seasons[year] = {
            "players": s["colOrder"], "size": size,
            "colOrder": s["colOrder"], "seats": s.get("seats"),
            "draft": picks, "rosters": rosters, "weekly": s.get("weekly"),
            "pot": s.get("pot"), "pun": s.get("pun"), "punWho": s.get("punWho"),
            "photos": s.get("photos", []), "status": status,
        }
        if s.get("baseline"):
            out_seasons[year]["baseline"] = s["baseline"]

        tot = {p: sum(table[a][0] + table[a][2] * league["tieValue"] for a in t)
               for p, t in rosters.items()}
        lead = max(tot, key=tot.get)
        print(f"  {year} [{status:5s}] {played // 2:3d} games · "
              + "  ".join(f"{p} {v:g}" for p, v in sorted(tot.items(), key=lambda x: -x[1]))
              + f"   <- {lead}")

    players = league["players"]
    blob = (
        "const REC=" + json.dumps(rec, separators=(",", ":")) + ";\n"
        "const SEASONS=" + json.dumps(out_seasons, separators=(",", ":")) + ";\n"
        "const CALL=" + json.dumps({k: v["call"] for k, v in players.items()}, separators=(",", ":")) + ";\n"
        "const FULL=" + json.dumps({k: v["full"] for k, v in players.items()}, separators=(",", ":")) + ";\n"
        "const YEARS=" + json.dumps(sorted(out_seasons, reverse=True), separators=(",", ":")) + ";\n"
        "const BUILT=" + json.dumps(datetime.datetime.now(datetime.timezone.utc)
                                    .strftime("%Y-%m-%d %H:%M")) + ";\n"
    )
    tpl = open(os.path.join(ROOT, "template.html")).read()
    if "/*__DATA__*/" not in tpl:
        raise SystemExit("build.py: template.html is missing its /*__DATA__*/ marker")
    html = tpl.replace("/*__DATA__*/", blob)
    with open(os.path.join(ROOT, "index.html"), "w") as f:
        f.write(html)
    print(f"built index.html ({len(html):,} bytes) · standings changed: {any_change}")


if __name__ == "__main__":
    main()

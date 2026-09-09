# The Pentagon

Season-long NFL franchise draft league. Five players, six teams each, most collective
regular-season wins takes it. Last place serves a punishment.

Live at **[thepentagon.football](https://thepentagon.football)**.

## How it stays current

`scripts/build.py` pulls regular-season standings from ESPN's public feed, merges them
with the league data in `data/seasons.json`, and writes a fully static `index.html`.
A GitHub Action runs it every morning and commits the result, so the site updates itself
whether or not anyone's laptop is on. No API key, no server, no database.

A season flips from *live* to *final* automatically once all 32 teams have played 17 games.

## Rules encoded here

- Ties count as **half a win**.
- **Par** is the wins an average roster would collect: `272 / 32 × teams-per-roster`.
  2023 ran 4 players × 8 teams (par 68); 2024 onward runs 5 × 6 (par 51). Raw totals are
  not comparable across those eras — distance from par is.
- **Draft value** is a pick's wins minus the average of every team taken in the same round
  that year. It is zero-sum, so it measures drafting rather than draft position.
- Draft order is drawn at random each season.

## Editing the league

Everything hand-maintained lives in `data/seasons.json`. Team names are plain
(`"Eagles"`, `"49ers"`); the build resolves them and will fail loudly on a typo or a
team drafted twice.

To add a season, copy the previous block and change the rosters. To record a punishment,
set `pun` and `punWho`.

This site carries no photos or video by design — it is public, and the punishment footage
stays out of it. Commit and push — the Action rebuilds and publishes within a couple of minutes.

## Running it locally

```bash
python3 scripts/build.py            # refresh live seasons, cache finished ones
python3 scripts/build.py --all      # re-fetch every season
python3 scripts/build.py --offline  # build from cache, no network
open index.html
```

Standard library only — no `pip install` step.

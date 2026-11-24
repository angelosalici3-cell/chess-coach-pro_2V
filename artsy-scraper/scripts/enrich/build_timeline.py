"""Build yearly timelines, yearly quadrants, transitions and primary-market prices.

Usage: python3 build_timeline.py <history dir> <matrix.csv> <out dir>

Inputs in <history dir>: history_yearly.csv, wiki_pageviews.csv, listings.csv, fx_samples.csv
Outputs in <out dir>:
  artist_timeline.csv      one row per artist and year (FIRST..LAST)
  quadrant_transitions.csv counts of artists moving between quadrants FROM_YEAR -> TO_YEAR
  artist_trends.csv        one row per artist: trends, quadrant then and now, primary market prices

Yearly quadrant (only artists with a Wikipedia page, since that is the only popularity
signal with a history):
  popularity  = Wikipedia page views in the year (current year annualised), percentile
  recognition = rolling 5-year sum of 3*institutional shows + 2*solo shows + 1*Artsy articles
                + 0.5*other shows, percentile
  quadrant    = same 75th-percentile rule as the main matrix
"""
import bisect
import csv
import datetime as dt
import math
import os
import statistics
import sys
from collections import Counter, defaultdict

FIRST, LAST = 2015, dt.date.today().year
FROM_YEAR, TO_YEAR = 2019, LAST
hist_dir, matrix_csv, out_dir = sys.argv[1:4]
os.makedirs(out_dir, exist_ok=True)
P = lambda n: os.path.join(hist_dir, n)

matrix = {r["slug"]: r for r in csv.DictReader(open(matrix_csv, encoding="utf-8"))}
hist = defaultdict(dict)
for r in csv.DictReader(open(P("history_yearly.csv"), encoding="utf-8")):
    hist[r["slug"]][int(r["year"])] = r

# Wikipedia views per year; the current year is annualised from the months available
views, months_seen = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
has_wiki = set()
if os.path.exists(P("wiki_pageviews.csv")):
    for r in csv.DictReader(open(P("wiki_pageviews.csv"), encoding="utf-8")):
        has_wiki.add(r["slug"])
        if r["month"]:
            y = int(r["month"][:4])
            views[r["slug"]][y] += int(r["views"])
            months_seen[r["slug"]][y] += 1
cur_months = max((m for d in months_seen.values() for m in [d.get(LAST, 0)]), default=0)

slugs = sorted(set(hist) | has_wiki)
rows = []
for s in slugs:
    roll = []
    for y in range(FIRST, LAST + 1):
        h = hist[s].get(y, {})
        g = lambda k: int(h.get(k) or 0)
        pts = 3 * g("inst_shows") + 2 * g("solo_shows") + g("articles") + 0.5 * max(0, g("shows") - g("inst_shows") - g("solo_shows"))
        roll.append(pts)
        v = views[s].get(y, 0)
        if v is not None and y == LAST and cur_months:
            v = round(v * 12 / cur_months)
        rows.append({
            "slug": s, "name": matrix.get(s, {}).get("name", s), "year": y,
            "wiki_views": v if s in has_wiki else "",
            "shows": g("shows"), "inst_shows": g("inst_shows"), "solo_shows": g("solo_shows"),
            "fair_shows": g("fair_shows"), "articles": g("articles"),
            "lots_offered": g("lots_offered"), "lots_sold": g("lots_sold"),
            "median_price_usd": h.get("median_price_usd", ""), "median_unique_usd": h.get("median_unique_usd", ""),
            "price_to_estimate": h.get("median_price_to_estimate", ""),
            "recognition_5y": sum(roll[-5:]),
        })

by_year = defaultdict(list)
for r in rows:
    by_year[r["year"]].append(r)
for y, rs in by_year.items():
    pop = sorted(float(r["wiki_views"]) for r in rs if r["wiki_views"] != "")
    rec = sorted(r["recognition_5y"] for r in rs if r["slug"] in has_wiki)
    for r in rs:
        if r["wiki_views"] == "" or not pop:
            r["popularity_pct"] = r["recognition_pct"] = r["quadrant"] = ""
            continue
        pp = round(100 * bisect.bisect_left(pop, float(r["wiki_views"])) / len(pop), 1)
        rp = round(100 * bisect.bisect_left(rec, r["recognition_5y"]) / len(rec), 1)
        r["popularity_pct"], r["recognition_pct"] = pp, rp
        r["quadrant"] = ("established" if pp >= 75 and rp >= 75 else "hype" if pp >= 75
                         else "insider" if rp >= 75 else "emerging")

fields = ["slug", "name", "year", "wiki_views", "popularity_pct", "shows", "inst_shows", "solo_shows", "fair_shows",
          "articles", "recognition_5y", "recognition_pct", "quadrant", "lots_offered", "lots_sold",
          "median_price_usd", "median_unique_usd", "price_to_estimate"]
with open(os.path.join(out_dir, "artist_timeline.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

# Transitions
q_at = defaultdict(dict)
for r in rows:
    if r["quadrant"]:
        q_at[r["slug"]][r["year"]] = r["quadrant"]
trans = Counter((d[FROM_YEAR], d[TO_YEAR]) for d in q_at.values() if FROM_YEAR in d and TO_YEAR in d)
Q = ["insider", "established", "hype", "emerging"]
with open(os.path.join(out_dir, "quadrant_transitions.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["from_quadrant", "to_quadrant", "artists", "from_year", "to_year"])
    for a in Q:
        for b in Q:
            w.writerow([a, b, trans.get((a, b), 0), FROM_YEAR, TO_YEAR])

# Primary market (works for sale now), converted to USD with rates taken from auction results
fx = defaultdict(list)
for r in csv.DictReader(open(P("fx_samples.csv"), encoding="utf-8")):
    if int(r["year"]) >= LAST - 1:
        fx[r["currency"]].append(float(r["usd_per_unit"]))
rate = {c: statistics.median(v) for c, v in fx.items() if len(v) >= 5}
rate["USD"] = 1.0
lst = defaultdict(lambda: {"all": [], "unique": [], "n": 0, "skipped": 0})
for r in csv.DictReader(open(P("listings.csv"), encoding="utf-8")):
    d = lst[r["slug"]]
    d["n"] += 1
    if r["currency"] not in rate:
        d["skipped"] += 1
        continue
    usd = float(r["price"]) * rate[r["currency"]]
    d["all"].append(usd)
    if r["is_unique"] == "1":
        d["unique"].append(usd)


def slope(points):
    """Yearly growth of log10(value) by least squares; None with fewer than 3 points."""
    if len(points) < 3:
        return None
    xs, ys = [p[0] for p in points], [math.log10(p[1]) for p in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else None


tl = defaultdict(dict)
for r in rows:
    tl[r["slug"]][r["year"]] = r
trend_rows = []
for s in slugs:
    t = tl[s]
    vv = [(y, float(t[y]["wiki_views"])) for y in range(FIRST, LAST) if t[y]["wiki_views"] not in ("", 0, "0")]
    pp = [(y, float(t[y]["median_price_usd"])) for y in range(FIRST, LAST + 1)
          if t[y]["median_price_usd"] and int(t[y]["lots_sold"]) >= 3]
    sv, sp = slope(vv), slope(pp)
    recent = sum(t[y]["inst_shows"] + t[y]["solo_shows"] for y in range(LAST - 2, LAST + 1))
    before = sum(t[y]["inst_shows"] + t[y]["solo_shows"] for y in range(LAST - 5, LAST - 2))
    d = lst.get(s)
    q0, q1 = q_at[s].get(FROM_YEAR, ""), q_at[s].get(TO_YEAR, "")
    trend_rows.append({
        "slug": s, "name": matrix.get(s, {}).get("name", s),
        "wiki_views_growth_pct_per_year": round(100 * (10 ** sv - 1), 1) if sv is not None else "",
        "price_growth_pct_per_year": round(100 * (10 ** sp - 1), 1) if sp is not None else "",
        "price_years_used": len(pp),
        "major_shows_last3y": recent, "major_shows_prev3y": before,
        f"quadrant_{FROM_YEAR}": q0, f"quadrant_{TO_YEAR}": q1,
        "quadrant_move": f"{q0}→{q1}" if q0 and q1 and q0 != q1 else ("" if not (q0 and q1) else "stable"),
        "listings_for_sale": d["n"] if d else 0,
        "median_list_price_usd": round(statistics.median(d["all"])) if d and d["all"] else "",
        "median_list_price_unique_usd": round(statistics.median(d["unique"])) if d and d["unique"] else "",
    })
with open(os.path.join(out_dir, "artist_trends.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(trend_rows[0]))
    w.writeheader()
    w.writerows(trend_rows)
print(f"{len(slugs):,} artists, {len(rows):,} artist-years; with quadrant history: {sum(1 for d in q_at.values() if d):,}")
print("fx rates:", {k: round(v, 3) for k, v in rate.items()})
moves = Counter(r["quadrant_move"] for r in trend_rows if r["quadrant_move"])
print("moves", FROM_YEAR, "->", TO_YEAR, moves.most_common(8))

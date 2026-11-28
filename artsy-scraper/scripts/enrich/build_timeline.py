"""Build yearly timelines, yearly quadrants, transitions and primary-market prices.

Usage: python3 build_timeline.py <history dir> <matrix.csv> <out dir>

Inputs in <history dir>: history_yearly.csv, wiki_pageviews.csv, listings.csv, fx_samples.csv
Outputs in <out dir>:
  artist_timeline.csv      one row per artist and year (FIRST..LAST)
  quadrant_transitions.csv counts of artists moving between quadrants FROM_YEAR -> TO_YEAR
  artist_trends.csv        one row per artist: trends, quadrant then and now, primary market prices

Yearly quadrant, for every artist with Artsy history:
  Each year's counts are first divided by that year's total across all artists (times the
  average yearly total), because Artsy records ~4x more shows in 2026 than in 2015.
  attention   = rolling 3-year sum of normalised auction lots offered + 5*Artsy articles
                (market and media attention; Artsy followers have no history), percentile
  recognition = today's expert score from Artsy insights (museum collections, biennials,
                reviews...), back-cast to each year by the share of the artist's normalised
                cumulative activity (3*institutional + 2*solo shows + top fairs + 0.5*other shows,
                since 2010) reached by that year. Percentile against one fixed yardstick: the
                expert scores of all artists in the main matrix, so 2026 matches today's quadrant.
                Careers documented on Artsy before 2010 start from at least half of today's score.
                Recognition accumulates: it can grow or hold, not vanish. Validated against
                Artsy's current signals (show records alone agreed only ~52%).
  quadrant    = 75th-percentile rule with hysteresis: an artist already above the threshold on
                an axis stays above until it drops under the 65th percentile
Deceased artists are left out of the transitions table (living = no death date on Artsy).
Wikipedia page views (annual, current year annualised) are kept as a separate column.
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

# top art fairs per year (from artist_extras.py), optional
fairs = defaultdict(dict)
if os.path.exists(P("extras/fairs_yearly.csv")):
    for r in csv.DictReader(open(P("extras/fairs_yearly.csv"), encoding="utf-8")):
        fairs[r["slug"]][int(r["year"])] = int(r["top_fairs"])

slugs = sorted(set(hist) | has_wiki)
HALF_LIFE, HYST = 5.0, 65.0
# yearly totals across all artists, to remove growth in Artsy's coverage
tot = defaultdict(lambda: defaultdict(float))
for s_, years in hist.items():
    for y_, h_ in years.items():
        for k_ in ("shows", "inst_shows", "solo_shows", "fair_shows", "lots_offered", "articles"):
            tot[y_][k_] += int(h_.get(k_) or 0)
    for y_, n_ in fairs[s_].items():
        tot[y_]["top_fairs"] += n_
YEARS_ALL = sorted(y_ for y_ in tot if 2010 <= y_ <= LAST)
def norm_factor(k_):
    vals = [tot[y_][k_] for y_ in YEARS_ALL if tot[y_][k_] > 0]
    avg = sum(vals) / len(vals) if vals else 1
    return {y_: (avg / tot[y_][k_] if tot[y_][k_] else 1) for y_ in YEARS_ALL}
NF = {k_: norm_factor(k_) for k_ in ("shows", "inst_shows", "solo_shows", "top_fairs", "lots_offered", "articles")}
living = {s_ for s_ in slugs if not (matrix.get(s_, {}).get("deathday") or "").strip()}
rows = []
for s in slugs:
    roll, att = [], []
    rec_score = 0.0
    for y0 in range(2010, FIRST):  # warm up the cumulative score from 2010
        h0 = hist[s].get(y0, {})
        g0 = lambda k: int(h0.get(k) or 0) * NF.get(k, {}).get(y0, 1)
        other0 = max(0, int(h0.get("shows") or 0) - int(h0.get("inst_shows") or 0) - int(h0.get("solo_shows") or 0) - int(h0.get("fair_shows") or 0)) * NF["shows"].get(y0, 1)
        rec_score = rec_score + 3 * g0("inst_shows") + 2 * g0("solo_shows") + fairs[s].get(y0, 0) * NF["top_fairs"].get(y0, 1) + 0.5 * other0
    for y in range(FIRST, LAST + 1):
        h = hist[s].get(y, {})
        g = lambda k: int(h.get(k) or 0)
        tf = fairs[s].get(y, 0)
        n_ = lambda k: NF[k].get(y, 1)
        other = max(0, g("shows") - g("inst_shows") - g("solo_shows") - g("fair_shows"))
        pts = 3 * g("inst_shows") * n_("inst_shows") + 2 * g("solo_shows") * n_("solo_shows") + tf * n_("top_fairs") + 0.5 * other * n_("shows")
        rec_score = rec_score + pts
        roll.append(pts)
        att.append(g("lots_offered") * n_("lots_offered") + 5 * g("articles") * n_("articles"))
        v = views[s].get(y, 0)
        if v is not None and y == LAST and cur_months:
            v = round(v * 12 / cur_months)
        rows.append({
            "slug": s, "name": matrix.get(s, {}).get("name", s), "year": y,
            "wiki_views": v if s in has_wiki else "",
            "shows": g("shows"), "inst_shows": g("inst_shows"), "solo_shows": g("solo_shows"),
            "fair_shows": g("fair_shows"), "top_fairs": tf, "articles": g("articles"),
            "lots_offered": g("lots_offered"), "lots_sold": g("lots_sold"),
            "median_price_usd": h.get("median_price_usd", ""), "median_unique_usd": h.get("median_unique_usd", ""),
            "price_to_estimate": h.get("median_price_to_estimate", ""),
            "cum_activity": rec_score, "attention_3y": round(sum(att[-3:]), 3),
        })

# back-cast expert recognition: today's expert score x share of cumulative activity reached
# careers documented before Artsy's records start (~2010) already had recognition then
first_doc = {}
if os.path.exists(P("extras/extras.csv")):
    for r in csv.DictReader(open(P("extras/extras.csv"), encoding="utf-8")):
        ys = [int(x) for x in (r.get("first_show_year"), r.get("first_lot_year")) if x and x.isdigit()]
        if ys:
            first_doc[r["slug"]] = min(ys)
EARLY_FLOOR = 0.5
final_cum = {}
for r in rows:
    if r["year"] == LAST:
        final_cum[r["slug"]] = r["cum_activity"]
for r in rows:
    es = float(matrix.get(r["slug"], {}).get("expert_score") or 0)
    fc = final_cum.get(r["slug"], 0)
    share = r["cum_activity"] / fc if fc > 0 else 1.0
    if first_doc.get(r["slug"], 9999) < 2010:
        share = max(share, EARLY_FLOOR)
    r["recognition_score"] = round(es * share, 3)

REC_REF = sorted(float(r.get("expert_score") or 0) for r in matrix.values())
by_year = defaultdict(list)
for r in rows:
    r.setdefault("attention_pct", ""); r.setdefault("recognition_pct", ""); r.setdefault("quadrant", "")
    by_year[r["year"]].append(r)
prev_hi = defaultdict(lambda: [False, False])  # per artist: [attention high, recognition high]
for y in sorted(by_year):
    rs = [r for r in by_year[y] if r["slug"] in hist]
    pop = sorted(r["attention_3y"] for r in rs)
    rec = REC_REF  # one fixed yardstick for every year: today's expert scores of all matrix artists
    for r in rs:
        pp = round(100 * bisect.bisect_left(pop, r["attention_3y"]) / len(pop), 1)
        rp = round(100 * bisect.bisect_left(rec, r["recognition_score"]) / len(rec), 1)
        r["attention_pct"], r["recognition_pct"] = pp, rp
        ph = prev_hi[r["slug"]]
        ah = pp >= 75 or (ph[0] and pp >= HYST)
        rh = rp >= 75 or (ph[1] and rp >= HYST)
        prev_hi[r["slug"]] = [ah, rh]
        r["quadrant"] = ("established" if ah and rh else "hype" if ah else "insider" if rh else "emerging")

fields = ["slug", "name", "year", "wiki_views", "attention_3y", "attention_pct", "shows", "inst_shows", "solo_shows", "fair_shows", "top_fairs",
          "articles", "recognition_score", "recognition_pct", "quadrant", "lots_offered", "lots_sold",
          "median_price_usd", "median_unique_usd", "price_to_estimate"]
with open(os.path.join(out_dir, "artist_timeline.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

# Transitions
q_at = defaultdict(dict)
for r in rows:
    if r["quadrant"]:
        q_at[r["slug"]][r["year"]] = r["quadrant"]
trans = Counter((d[FROM_YEAR], d[TO_YEAR]) for s_, d in q_at.items() if s_ in living and FROM_YEAR in d and TO_YEAR in d)
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
    # price trend on unique works (no prints/multiples) when there are >= 3 such years
    pu = [(y, float(t[y]["median_unique_usd"])) for y in range(FIRST, LAST + 1)
          if t[y]["median_unique_usd"] and int(t[y]["lots_sold"]) >= 3]
    pa = [(y, float(t[y]["median_price_usd"])) for y in range(FIRST, LAST + 1)
          if t[y]["median_price_usd"] and int(t[y]["lots_sold"]) >= 3]
    pp, basis = (pu, "unique works") if len(pu) >= 3 else (pa, "all lots")
    sv, sp = slope(vv), slope(pp)
    ratios = [float(t[y]["price_to_estimate"]) for y in range(LAST - 2, LAST + 1) if t[y]["price_to_estimate"]]
    ratios_before = [float(t[y]["price_to_estimate"]) for y in range(LAST - 5, LAST - 2) if t[y]["price_to_estimate"]]
    recent = sum(t[y]["inst_shows"] + t[y]["solo_shows"] for y in range(LAST - 2, LAST + 1))
    before = sum(t[y]["inst_shows"] + t[y]["solo_shows"] for y in range(LAST - 5, LAST - 2))
    d = lst.get(s)
    q0, q1 = q_at[s].get(FROM_YEAR, ""), q_at[s].get(TO_YEAR, "")
    trend_rows.append({
        "slug": s, "name": matrix.get(s, {}).get("name", s),
        "wiki_views_growth_pct_per_year": round(100 * (10 ** sv - 1), 1) if sv is not None else "",
        "price_growth_pct_per_year": round(100 * (10 ** sp - 1), 1) if sp is not None else "",
        "price_years_used": len(pp), "price_trend_basis": basis if sp is not None else "",
        "price_to_estimate_last3y": round(statistics.median(ratios), 2) if ratios else "",
        "price_to_estimate_prev3y": round(statistics.median(ratios_before), 2) if ratios_before else "",
        "major_shows_last3y": recent, "major_shows_prev3y": before,
        f"quadrant_{FROM_YEAR}": q0, f"quadrant_{TO_YEAR}": q1, "living": int(s in living),
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

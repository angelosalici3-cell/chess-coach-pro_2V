"""Radar v7: lot-level prices (size + currency), market-proven rule, coherence audit, social, synthesis.

Usage: python3 radar_v7.py <history_dir> <dash_dir> <data_dir>
Inputs
  history_dir/lots*.csv (+ lotsB/, lotsC/)  lot-level auction results (auction_lots.py)
  history_dir/listings.csv                    works for sale now (native currency)
  dash_dir/artist_matrix_v6.csv, timeline_v3.csv
  data_dir/ig_search_results.csv              Instagram handles + follower counts from search snippets
Outputs (dash_dir)
  artist_matrix_v7.csv, timeline_v4.csv, quadrant_transitions_v4.csv,
  lots_radar.csv (compact lots for the profile chart), radar_audit.csv, radar_summary.json
"""
import bisect, csv, json, math, os, re, statistics, sys
from collections import Counter, defaultdict

H, D, DATA = sys.argv[1:4]
YEAR_NOW, SINCE = 2026, 2016          # analysis window for prices: last 10 years
PROVEN_USD = 100_000                  # one sold lot at or above this: no longer "emerging"
REF_AREA = 10_000                     # cm² (1 m²): reference size for size-adjusted prices
UNIQUE_2D = {"Painting", "Work on Paper"}
CAT_CODE = {"Painting": "P", "Work on Paper": "C", "Sculpture": "S", "Print": "M", "Photography": "F"}

# ---------- 1. lots: merge workers, parse size, verify currency ----------
lots, seen = [], set()
files = [os.path.join(H, "lots.csv"), os.path.join(H, "lotsB", "lots.csv"), os.path.join(H, "lotsC", "lots.csv"), os.path.join(H, "lotsD", "lots.csv")]
for f in files:
    if not os.path.exists(f):
        continue
    here = set()
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if r["slug"] in seen:
            continue
        here.add(r["slug"]); lots.append(r)
    seen |= here

DIM = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)(?:\s*[x×]\s*(\d+(?:[.,]\d+)?))?\s*(cm|mm|in\b|inches|\")", re.I)


def area_cm2(txt, h, w):
    t = (txt or "").replace(",", ".")
    ms = list(DIM.finditer(t))
    if ms:
        m = next((m for m in ms if m.group(4).lower() == "cm"), ms[0])
        a, b, u = float(m.group(1)), float(m.group(2)), m.group(4).lower()
        k = 2.54 if u in ("in", "inches", '"') else 0.1 if u == "mm" else 1.0
        ar = a * k * b * k
    else:
        try:
            ar = float(h) * float(w)  # Artsy's parsed dimensions, cm
        except (TypeError, ValueError):
            return None
    return ar if 10 <= ar <= 2_000_000 else None


def major_from_display(disp):
    m = re.findall(r"[\d,.]+", disp or "")
    if not m:
        return None
    s = max(m, key=len).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# currency check: Artsy stores 'cents' in minor units, except zero-decimal currencies (JPY, KRW, HUF...)
factor_votes, rate = defaultdict(Counter), defaultdict(list)
for r in lots:
    if r["cents"] and r["display"] and r["currency"] and r["currency"] != "USD":
        mj = major_from_display(r["display"])
        if mj:
            f = float(r["cents"]) / mj
            factor_votes[r["currency"]][100 if f > 30 else 1] += 1
FACTOR = {c: v.most_common(1)[0][0] for c, v in factor_votes.items()}
FACTOR["USD"] = 100
for r in lots:
    c = r["currency"]
    if r["cents"] and r["cents_usd"] and c in FACTOR:
        yr = r["sale_date"][:4]
        rate[(c, yr)].append(float(r["cents_usd"]) / 100 / (float(r["cents"]) / FACTOR[c]))
RATE = {k: statistics.median(v) for k, v in rate.items() if v}
RATE_C = defaultdict(list)
for (c, yr), v in RATE.items():
    RATE_C[c].append(v)
RATE_C = {c: statistics.median(v) for c, v in RATE_C.items()}

fx_fixed, sold = 0, []
offered = Counter(); unsold = Counter()  # sell-through over the analysis window, from single lots
for r in lots:
    if r["sale_date"][:4].isdigit() and SINCE <= int(r["sale_date"][:4]) <= YEAR_NOW:
        offered[r["slug"]] += 1; unsold[r["slug"]] += r["bought_in"] == "1"
for r in lots:
    if r["bought_in"] == "1" or not r["cents"] or not r["sale_date"][:4].isdigit():
        continue
    yr = int(r["sale_date"][:4])
    if yr < 2010 or yr > YEAR_NOW:
        continue
    c = r["currency"] or "USD"
    major = float(r["cents"]) / FACTOR.get(c, 100)
    ref = RATE.get((c, str(yr))) or RATE_C.get(c)
    usd = float(r["cents_usd"]) / 100 if r["cents_usd"] else None
    if ref and (usd is None or abs(usd / (major * ref) - 1) > 0.25):  # missing or inconsistent conversion
        usd = major * ref; fx_fixed += 1
    if not usd or usd <= 0:
        continue
    sold.append({"slug": r["slug"], "date": r["sale_date"], "year": yr, "usd": usd, "cur": c, "major": major,
                 "cat": r["category"], "area": area_cm2(r["dimension_text"], r["height"], r["width"]),
                 "title": r["title"], "dim": r["dimension_text"]})

# ---------- 2. size elasticity (within artist-year, unique 2D works) ----------
cells = defaultdict(list)
for s in sold:
    if s["cat"] in UNIQUE_2D and s["area"]:
        cells[(s["slug"], s["year"])].append((math.log(s["area"]), math.log(s["usd"])))
num = den = 0.0
n_beta = 0
for pts in cells.values():
    if len(pts) < 2:
        continue
    mx = sum(p[0] for p in pts) / len(pts); my = sum(p[1] for p in pts) / len(pts)
    for x, y in pts:
        num += (x - mx) * (y - my); den += (x - mx) ** 2; n_beta += 1
BETA = round(num / den, 3) if den else 0.5
for s in sold:
    s["adj"] = s["usd"] * (REF_AREA / s["area"]) ** BETA if (s["cat"] in UNIQUE_2D and s["area"]) else None

# ---------- 3. per-artist price metrics ----------
by = defaultdict(list)
for s in sold:
    by[s["slug"]].append(s)


def slope_log(points):  # yearly medians -> % growth per year (OLS on log)
    if len(points) < 3:
        return None
    xs = [p[0] for p in points]; ys = [math.log(p[1]) for p in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    d = sum((x - mx) ** 2 for x in xs)
    return round(100 * (math.exp(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / d) - 1), 1) if d else None


P = {}
for slug, L in by.items():
    rec = [s for s in L if s["year"] >= SINCE]
    adj = [s["adj"] for s in rec if s["adj"]]
    mx = max(L, key=lambda s: s["usd"])
    proven = sorted(s["year"] for s in L if s["usd"] >= PROVEN_USD)
    yr_adj = defaultdict(list); yr_raw = defaultdict(list)
    for s in rec:
        yr_raw[s["year"]].append(s["usd"])
        if s["adj"]:
            yr_adj[s["year"]].append(s["adj"])
    P[slug] = {
        "lots_sold_10y": len(rec),
        "lots_sized_2d": len(adj),
        "median_usd_10y": round(statistics.median([s["usd"] for s in rec])) if rec else "",
        "max_lot_usd": round(mx["usd"]), "max_lot_year": mx["year"], "max_lot_title": mx["title"][:80],
        "max_lot_dim": mx["dim"][:40], "max_lot_currency": mx["cur"],
        "price_1m2_usd": round(statistics.median(adj)) if len(adj) >= 3 else "",
        "price_per_m2_usd": round(statistics.median([s["usd"] / (s["area"] / 1e4) for s in rec if s["adj"]])) if len(adj) >= 3 else "",
        "adj_growth_pct_per_year": slope_log([(y, statistics.median(v)) for y, v in yr_adj.items() if len(v) >= 1]) if len(adj) >= 6 else "",
        "raw_growth_pct_per_year": slope_log([(y, statistics.median(v)) for y, v in yr_raw.items()]) if len(rec) >= 6 else "",
        "market_proven_year": proven[0] if proven else "",
        "foreign_currency_share": round(sum(s["cur"] != "USD" for s in rec) / len(rec), 2) if rec else "",
        "sell_through_10y": round(100 * (1 - unsold[slug] / offered[slug]), 1) if offered[slug] >= 5 else "",
    }
    P[slug] = {k: ("" if v is None else v) for k, v in P[slug].items()}

# ---------- 4. listings with corrected FX ----------
lst = defaultdict(list)
listing_fixed = Counter()
old_rate = defaultdict(list)
for r in csv.DictReader(open(os.path.join(H, "fx_samples.csv"))):
    old_rate[r["currency"]].append(float(r["usd_per_unit"]))
old_rate = {c: statistics.median(v) for c, v in old_rate.items() if len(v) >= 5}
for r in csv.DictReader(open(os.path.join(H, "listings.csv"), encoding="utf-8")):
    c = r["currency"]
    rt = 1.0 if c == "USD" else RATE.get((c, str(YEAR_NOW))) or RATE.get((c, str(YEAR_NOW - 1))) or RATE_C.get(c)
    if not rt:
        continue
    if c in old_rate and abs(old_rate[c] / rt - 1) > 0.5:
        listing_fixed[c] += 1
    if r["is_unique"] == "1":
        lst[r["slug"]].append(float(r["price"]) * rt)

# ---------- 5. Instagram ----------
IG = {}
IG_ROWS = list(csv.DictReader(open(os.path.join(DATA, "ig_search_results.csv"), encoding="utf-8")))
_top = os.path.join(DATA, "ig_top300_results.csv")  # second, targeted search on the synthesis top 300: overrides
if os.path.exists(_top):
    IG_ROWS += list(csv.DictReader(open(_top, encoding="utf-8")))
for r in IG_ROWS:
    if r["slug"] in IG and not (r["instagram"] and r["confidence"] in ("alta", "media")):
        IG.pop(r["slug"])
    if r["instagram"] and r["confidence"] in ("alta", "media"):
        try:
            fol = int(float(r["followers_snippet"]))
        except (TypeError, ValueError):
            fol = None
        IG[r["slug"]] = {"ig_handle": r["instagram"], "ig_confidence": r["confidence"], "ig_followers": fol}
DEATH = {}
for r in IG_ROWS:
    ev = r["evidence"] or ""
    if re.search(r"decedut|Estate|estate", ev):
        m = re.search(r"decedut[oa]\s+(\d{4})", ev) or re.search(r"\d{4}\s*[-–]\s*(\d{4})", ev)
        DEATH[r["slug"]] = m.group(1) if m else ""
dead_ig = set(DEATH)

# ---------- 6. matrix v7 ----------
rows = list(csv.DictReader(open(os.path.join(D, "artist_matrix_v6.csv"), encoding="utf-8")))
pct = lambda arr: (lambda v: round(100 * bisect.bisect_right(arr, v) / len(arr), 1)) if arr else (lambda v: "")
audit = Counter()
for r in rows:
    p = P.get(r["slug"], {})
    for k in ["lots_sold_10y", "lots_sized_2d", "median_usd_10y", "max_lot_usd", "max_lot_year", "max_lot_title", "max_lot_dim",
              "max_lot_currency", "price_1m2_usd", "price_per_m2_usd", "adj_growth_pct_per_year", "raw_growth_pct_per_year",
              "market_proven_year", "foreign_currency_share", "sell_through_10y"]:
        r[k] = p.get(k, "")
    L = lst.get(r["slug"])
    old = r["median_list_price_unique_usd"]
    r["median_list_price_unique_usd"] = round(statistics.median(L)) if L else ""
    if old and r["median_list_price_unique_usd"] and float(old) > 3 * float(r["median_list_price_unique_usd"]):
        audit["listing_price_was_inflated"] += 1
    g = IG.get(r["slug"], {})
    r["ig_handle"] = g.get("ig_handle", "") or (r.get("instagram") or "")
    r["instagram"] = r["ig_handle"]
    r["ig_followers"] = g.get("ig_followers") or ""
    r["ig_confidence"] = g.get("ig_confidence", "")
    r["deceased_flag"] = int(r["slug"] in dead_ig)
    r["death_year"] = DEATH.get(r["slug"], "")
    if r["deceased_flag"]:
        r["age_artsy"] = r["age"]; r["age"] = ""          # Artsy lists them as living: correct the matrix
        audit["deceased_corrected_in_matrix"] += 1
    else:
        r["age_artsy"] = r["age"]
    r["living"] = int(r["age"] != "" and not r["deceased_flag"])
    # market-proven rule
    r["quadrant_before_rule"] = r["quadrant"]
    r["quadrant_rule"] = ""
    if r["quadrant"] == "emerging" and r["market_proven_year"]:
        r["quadrant"] = "hype"; r["quadrant_rule"] = f"lotto ≥ {PROVEN_USD//1000}k USD nel {r['market_proven_year']}"
        audit["emerging_to_hype_market_rule"] += 1
    if r["quadrant_borderline"] == "emerging" and r["market_proven_year"]:
        r["quadrant_borderline"] = ""
    # size bias: raw vs size-adjusted growth disagree in sign
    if r["adj_growth_pct_per_year"] != "" and r["raw_growth_pct_per_year"] != "":
        a, b = float(r["adj_growth_pct_per_year"]), float(r["raw_growth_pct_per_year"])
        if (a > 5 and b < -5) or (a < -5 and b > 5):
            audit["growth_sign_flips_after_size_adjustment"] += 1

# percentiles
def col(k, cond=lambda r: True):
    return sorted(float(r[k]) for r in rows if r[k] not in ("", None) and cond(r))
adj_sorted = col("price_1m2_usd")
ig_sorted = sorted(math.log1p(float(r["ig_followers"])) for r in rows if r["ig_followers"])
for r in rows:
    r["price_adj_pct"] = pct(adj_sorted)(float(r["price_1m2_usd"])) if r["price_1m2_usd"] != "" else ""
    r["ig_pct"] = pct(ig_sorted)(math.log1p(float(r["ig_followers"]))) if r["ig_followers"] else ""
    pub = [float(r["followers_pct"])] + ([float(r["ig_pct"])] if r["ig_pct"] != "" else [])
    r["public_pct"] = round(sum(pub) / len(pub), 1)
    r["public_vs_price_gap"] = round(r["public_pct"] - r["price_adj_pct"], 1) if r["price_adj_pct"] != "" else ""
    r["interest_vs_price_gap_adj"] = round(float(r["interest_pct"]) - r["price_adj_pct"], 1) if r["price_adj_pct"] != "" else ""

# momentum components -> percentile
def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
MOVE = {"emerging→insider": 1, "emerging→hype": .5, "emerging→established": 1, "hype→established": 1, "insider→established": 1,
        "hype→insider": .5, "stable": 0, "insider→emerging": -1, "established→insider": -.5, "established→hype": -.5,
        "hype→emerging": -.5, "established→emerging": -1, "insider→hype": -.5}
comp = {"shows": [], "wiki": [], "price": []}
for r in rows:
    a, b = num(r["major_shows_last3y"]), num(r["major_shows_prev3y"])
    r["_shows"] = (a - b) if a is not None and b is not None else None
    r["_wiki"] = num(r["wiki_views_growth_pct_per_year"])
    pg = num(r["adj_growth_pct_per_year"])
    r["_price"] = max(-50, min(100, pg)) if pg is not None else None
    for k in comp:
        if r["_" + k] is not None:
            comp[k].append(r["_" + k])
for k in comp:
    comp[k].sort()
for r in rows:
    parts = [pct(comp[k])(r["_" + k]) for k in comp if r["_" + k] is not None]
    mv = MOVE.get(r["quadrant_move"])
    if mv is not None:
        parts.append(50 + 50 * mv)
    r["momentum_pct"] = round(sum(parts) / len(parts), 1) if parts else ""

# synthesis score (living, not flagged deceased)
raw_pct = pct(sorted(float(r["median_usd_10y"]) for r in rows if r["median_usd_10y"] != "" and int(r["lots_sold_10y"] or 0) >= 3))
W = {"rec": .35, "mom": .20, "pub": .15, "value": .20, "solid": .10}
for r in rows:
    living = r["living"] == 1
    parts = {"rec": num(r["recognition_pct_now"]), "mom": num(r["momentum_pct"]), "pub": num(r["public_pct"])}
    g = num(r["interest_vs_price_gap_adj"])
    if g is None and r["median_usd_10y"] != "" and int(r["lots_sold_10y"] or 0) >= 3:
        g = float(r["interest_pct"]) - raw_pct(float(r["median_usd_10y"]))  # fallback: all lots, not size-adjusted
        r["value_basis"] = "prezzo mediano (senza dimensioni)"
    else:
        r["value_basis"] = "prezzo a 1 m²" if g is not None else ""
    parts["value"] = 50 + g / 2 if g is not None else None
    st, pe = num(r["sell_through_10y"]), num(r["price_to_estimate_last3y"])
    parts["solid"] = (min(100, st) * .5 + min(100, 50 * pe) * .5) if st is not None and pe is not None else (st if st is not None else None)
    have = {k: v for k, v in parts.items() if v is not None}
    wsum = sum(W[k] for k in have)
    r["score_synthesis"] = round(sum(W[k] * v for k, v in have.items()) / wsum, 1) if wsum >= .6 else ""
    r["score_coverage"] = round(wsum, 2)
    r["score_parts"] = ";".join(f"{k}={round(v)}" for k, v in have.items())
    r["eligible_synthesis"] = int(bool(living and r["score_synthesis"] != "" and int(r["lots_sold_10y"] or 0) >= 3))
    for k in ("_shows", "_wiki", "_price"):
        r.pop(k, None)


# ---------- 6b. correlations on size-adjusted prices + pipeline counts ----------
def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); rk = [0.0] * len(v); i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return rk
def spear(x, y):
    if len(x) < 30:
        return ""
    rx, ry = ranks(x), ranks(y); n = len(x); mx, my = sum(rx) / n, sum(ry) / n
    c = sum((a - mx) * (b - my) for a, b in zip(rx, ry)); sx = math.sqrt(sum((a - mx) ** 2 for a in rx)); sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(c / (sx * sy), 3) if sx and sy else ""
priced = [r for r in rows if r["price_1m2_usd"] != ""]
with open(os.path.join(D, "price_correlations_v2.csv"), "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["group", "artists", "rho_price_followers", "rho_price_expert", "rho_price_interest", "median_price_usd", "rho_price_instagram", "artists_with_instagram"])
    for name, g in [("all", priced)] + [(q, [r for r in priced if r["quadrant"] == q]) for q in ("insider", "established", "hype", "emerging")]:
        if len(g) < 30:
            continue
        pr = [float(r["price_1m2_usd"]) for r in g]
        gi = [r for r in g if r["ig_followers"]]
        w.writerow([name, len(g), spear(pr, [float(r["artsy_followers"]) for r in g]), spear(pr, [float(r["expert_score"]) for r in g]),
                    spear(pr, [float(r["interest_pct"]) for r in g]), round(statistics.median(pr)),
                    spear([float(r["price_1m2_usd"]) for r in gi], [float(r["ig_followers"]) for r in gi]), len(gi)])
pl = list(csv.DictReader(open(os.path.join(D, "pipeline.csv"))))[0]
pl["instagram_in_matrix"] = sum(1 for r in rows if r["instagram"])
pl["instagram_matched"] = int(pl["instagram_matched"]) + sum(1 for k, v in IG.items())
pl["instagram_with_followers"] = sum(1 for r in rows if r["ig_followers"])
with open(os.path.join(D, "pipeline_v2.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(pl.keys())); w.writeheader(); w.writerow(pl)

fields = list(rows[0].keys())
with open(os.path.join(D, "artist_matrix_v7.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields); w.writeheader(); w.writerows(rows)

# ---------- 7. timeline v4: per-year lots, adj price, market rule, coherence ----------
yr_lots = defaultdict(lambda: defaultdict(list))
for s in sold:
    yr_lots[s["slug"]][s["year"]].append(s)
tl = list(csv.DictReader(open(os.path.join(D, "timeline_v3.csv"), encoding="utf-8")))
proven_year = {k: v["market_proven_year"] for k, v in P.items() if v["market_proven_year"]}
for r in tl:
    y, L = int(r["year"]), yr_lots[r["slug"]].get(int(r["year"]), [])
    adj = [s["adj"] for s in L if s["adj"]]
    r["lots_sold_detail"] = len(L)
    r["median_adj_usd"] = round(statistics.median(adj)) if adj else ""
    r["max_lot_usd"] = round(max(s["usd"] for s in L)) if L else ""
    r["quadrant_before_rule"] = r["quadrant"]
    py = proven_year.get(r["slug"])
    if r["quadrant"] == "emerging" and py and y >= int(py):
        r["quadrant"] = "hype"
by_slug = defaultdict(list)
for r in tl:
    by_slug[r["slug"]].append(r)
flap = rec_drop = 0
for slug, L in by_slug.items():
    L.sort(key=lambda r: int(r["year"]))
    qs = [r["quadrant"] for r in L if r["quadrant"] and int(r["year"]) >= 2016]
    if sum(a != b for a, b in zip(qs, qs[1:])) >= 4:
        flap += 1
    hi = [r["quadrant"] in ("insider", "established") for r in L if r["quadrant"]]
    if any(a and not b for a, b in zip(hi, hi[1:])):
        rec_drop += 1
audit["timeline_quadrant_flapping_4plus_changes"] = flap
audit["timeline_recognition_high_to_low"] = rec_drop
audit["timeline_emerging_to_hype_market_rule"] = sum(1 for r in tl if r["quadrant"] != r["quadrant_before_rule"])
with open(os.path.join(D, "timeline_v4.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(tl[0].keys())); w.writeheader(); w.writerows(tl)
q_at = defaultdict(dict)
for r in tl:
    if r["quadrant"]:
        q_at[r["slug"]][int(r["year"])] = r["quadrant"]
living = {r["slug"] for r in csv.DictReader(open(os.path.join(DATA, "timeline", "artist_trends.csv"), encoding="utf-8")) if r["living"] == "1"} - dead_ig
def q_year(slug, Y):  # timeline rows exist only in years with data: carry the last known quadrant forward
    d = q_at.get(slug, {})
    ys = [y for y in d if y <= Y]
    q = d[max(ys)] if ys else "emerging"
    py = proven_year.get(slug)
    return "hype" if q == "emerging" and py and Y >= int(py) else q
tr = Counter((q_year(s_, 2019), q_year(s_, 2026)) for s_ in living)
with open(os.path.join(D, "quadrant_transitions_v4.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["from_quadrant", "to_quadrant", "artists", "from_year", "to_year"])
    QS = ["insider", "established", "hype", "emerging"]
    for a in QS:  # all 16 pairs, zeros included: the page's heat table marks every cell
        for b in QS:
            w.writerow([a, b, tr.get((a, b), 0), 2019, 2026])

# ---------- 8. compact lots for the dashboard (last 10 years, max 60 per artist) ----------
with open(os.path.join(D, "lots_radar.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["slug", "d", "usd", "a", "c", "cur", "orig"])
    for slug, L in by.items():
        L = sorted((s for s in L if s["year"] >= SINCE), key=lambda s: s["date"], reverse=True)[:40]
        for s in L:
            w.writerow([slug, s["date"][:7], round(s["usd"]),
                        round(s["area"]) if s["area"] else "", CAT_CODE.get(s["cat"], "A"),
                        "" if s["cur"] == "USD" else s["cur"], "" if s["cur"] == "USD" else round(s["major"])])

audit["lots_sold_parsed"] = len(sold)
audit["lots_with_size"] = sum(1 for s in sold if s["area"])
audit["lots_fx_recomputed"] = fx_fixed
audit["artists_with_lots"] = len(by)
audit["artists_market_proven"] = len(proven_year)
audit["deceased_flagged_from_instagram_search"] = sum(r["deceased_flag"] for r in rows)
with open(os.path.join(D, "radar_audit.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["check", "value"]); w.writerows(sorted(audit.items()))
summary = {"beta_size_elasticity": BETA, "beta_obs": n_beta, "zero_decimal_currencies": sorted(c for c, f in FACTOR.items() if f == 1),
           "listing_currencies_fixed": dict(listing_fixed), "quadrants": Counter(r["quadrant"] for r in rows),
           "audit": audit, "transitions": {f"{a}->{b}": n for (a, b), n in tr.items()}}
json.dump(summary, open(os.path.join(D, "radar_summary.json"), "w"), indent=1, default=int)
print(json.dumps(summary, indent=1, default=int))

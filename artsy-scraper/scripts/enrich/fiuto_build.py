"""Join venue rosters and works for sale with the radar matrix.
Usage: python3 fiuto_build.py fiuto_dir dash_dir
Writes fiuto_dir/fiuto_artists.csv (one row per artist) and fiuto_works.csv (works with price in USD)."""
import csv, statistics, sys
from collections import defaultdict
F, D = sys.argv[1:3]
M = {r["slug"]: r for r in csv.DictReader(open(f"{D}/artist_matrix_v7.csv", encoding="utf-8"))}
rate = defaultdict(list)
for r in csv.DictReader(open(f"{D}/lots_radar.csv")):
    if r["cur"] and r["orig"] and r["d"][:4] in ("2025", "2026"):
        rate[r["cur"]].append(float(r["usd"]) / float(r["orig"]))
RATE = {c: statistics.median(v) for c, v in rate.items() if len(v) >= 5}; RATE["USD"] = 1.0
V = {r["venue"]: r for r in csv.DictReader(open(f"{F}/venues.csv", encoding="utf-8"))}
links = defaultdict(list)
for r in csv.DictReader(open(f"{F}/venue_artists.csv", encoding="utf-8")):
    links[r["artist_slug"]].append(r)
MULTI = {"Print", "Posters", "Books and Portfolios", "Ephemera or Merchandise", "Reproduction", "Other"}
works = list(csv.DictReader(open(f"{F}/artworks_for_sale.csv", encoding="utf-8")))
by = defaultdict(list); tot = {}
for w in works:
    lo = float(w["price_min"]) if w["price_min"] else None
    rt = RATE.get(w["currency"] or "USD")
    w["price_usd"] = round(lo * rt) if lo is not None and rt else ""
    w["price_known"] = int(w["price_usd"] != "")
    w["multiple"] = int(w["category"] in MULTI)
    by[w["artist_slug"]].append(w); tot[w["artist_slug"]] = w["for_sale_total"]
with open(f"{F}/fiuto_works.csv", "w", newline="", encoding="utf-8") as fh:
    cols = ["artist_slug", "artist_name", "slug", "title", "date", "medium", "category", "unique", "dimensions_cm", "price_usd", "price_min", "currency", "sale_message", "seller", "multiple"]
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(works)
keep = ["name", "quadrant", "age", "nationality", "living", "score_synthesis", "eligible_synthesis", "expert_score", "museum_collections", "biennials",
        "artsy_followers", "ig_followers", "ig_handle", "median_usd_10y", "price_1m2_usd", "max_lot_usd", "lots_sold_10y", "sell_through_10y",
        "price_to_estimate_last3y", "top_galleries", "net_track_venues"]
rows = []
for a, L in links.items():
    m = M.get(a, {})
    priced = [float(x["price_usd"]) for x in by.get(a, []) if x["price_usd"] != "" and not x["multiple"]]
    r_uniq = sum(1 for x in by.get(a, []) if not x["multiple"])
    r = {"slug": a, "name": m.get("name") or next((x["artist_name"] for x in by.get(a, [])), a)}
    for k in keep[1:]:
        r[k] = m.get(k, "")
    if r.get("eligible_synthesis") != "1":
        r["score_synthesis"] = ""
    r["in_radar"] = int(bool(m))
    r["venues"] = "; ".join(sorted({V[x["venue"]]["venue_name"] for x in L if x["venue"] in V}))
    r["venue_ids"] = "|".join(sorted({x["venue"] for x in L}))
    r["represented"] = int(any(x["link"] == "rappresentato" for x in L))
    r["works_for_sale"] = tot.get(a, 0) or 0
    r["works_listed"] = len(by.get(a, [])); r["unique_listed"] = r_uniq
    r["min_price_usd"] = round(min(priced)) if priced else ""
    r["median_list_usd"] = round(statistics.median(priced)) if priced else ""
    rows.append(r)
rows.sort(key=lambda r: (-(float(r["score_synthesis"]) if r["score_synthesis"] else -1), r["name"]))
with open(f"{F}/fiuto_artists.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("artists", len(rows), "in radar", sum(r["in_radar"] for r in rows), "with works", sum(1 for r in rows if int(r["works_for_sale"] or 0) > 0),
      "works", len(works), "priced", sum(1 for x in works if x["price_usd"] != ""))

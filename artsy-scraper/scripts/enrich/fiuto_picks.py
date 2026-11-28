"""50 artists we would buy among those at venues with a track record, independent of the radar's scores.
Rule (curatorial backing, not market scores): living, not established, aged up to 55, not already expensive
(auction median <= 50k USD and cheapest unique work listed <= 50k USD when known).
backing = 1.5 x sum of the lifts of the venues with a track record that show the artist
          + 0.4 per biennial (max 5) + 0.3 per museum collection (max 6) + 0.5 if represented.
Only artists one can actually buy: represented by a gallery, works for sale on Artsy, or an auction record.
Usage: python3 fiuto_picks.py fiuto_dir  -> fiuto_dir/fiuto_picks.csv"""
import csv, sys
from collections import defaultdict
F = sys.argv[1]
V = {v["venue"]: v for v in csv.DictReader(open(f"{F}/venues.csv", encoding="utf-8"))}
W = defaultdict(list)
for w in csv.DictReader(open(f"{F}/fiuto_works.csv", encoding="utf-8")):
    if w["multiple"] == "0":
        W[w["artist_slug"]].append(w)
num = lambda x: float(x) if x not in ("", None) else None
rows = []
for a in csv.DictReader(open(f"{F}/fiuto_artists.csv", encoding="utf-8")):
    age = num(a["age"])
    if a["in_radar"] != "1" or a["living"] != "1" or a["quadrant"] == "established" or age is None or age > 55:
        continue
    if (num(a["median_usd_10y"]) or 0) > 50000 or (num(a["min_price_usd"]) or 0) > 50000:
        continue
    ids = [i for i in a["venue_ids"].split("|") if i in V]
    bi, mu = min(int(a["biennials"] or 0), 5), min(int(a["museum_collections"] or 0), 6)
    backing = 1.5 * sum(float(V[i]["lift"]) for i in ids) + 0.4 * bi + 0.3 * mu + 0.5 * (a["represented"] == "1")
    ws = W.get(a["slug"], [])
    if not (a["represented"] == "1" or ws or a["median_usd_10y"]):
        continue
    pr = sorted(float(w["price_usd"]) for w in ws if w["price_usd"])
    why = [f"{len(ids)} sedi con fiuto ({a['venues']})" if len(ids) > 1 else f"sede con fiuto: {a['venues']}"]
    if bi: why.append("1 biennale" if a["biennials"] == "1" else f"{a['biennials']} biennali")
    if mu: why.append("1 museo" if a["museum_collections"] == "1" else f"{a['museum_collections']} musei")
    why.append(f"asta: mediana {int(float(a['median_usd_10y'])):,} USD".replace(",", ".") if a["median_usd_10y"] else "nessun passaggio d'asta")
    why.append(("1 opera unica in vendita" if len(ws) == 1 else f"{len(ws)} opere uniche in vendita") + ((" da " + f"{int(pr[0]):,}".replace(",", ".") + " USD") if pr else ", prezzo su richiesta") if ws else "nessuna opera in vendita su Artsy")
    rows.append({"slug": a["slug"], "name": a["name"], "quadrant": a["quadrant"], "age": int(age), "nationality": a["nationality"],
                 "backing": round(backing, 2), "venues_n": len(ids), "venues": a["venues"], "biennials": a["biennials"], "museum_collections": a["museum_collections"],
                 "median_usd_10y": a["median_usd_10y"], "unique_for_sale": len(ws), "min_unique_usd": int(pr[0]) if pr else "",
                 "score_synthesis": a["score_synthesis"], "why": "; ".join(why)})
rows.sort(key=lambda r: (-r["backing"], r["age"]))
rows = rows[:50]
for i, r in enumerate(rows, 1):
    r["rank"] = i
with open(f"{F}/fiuto_picks.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["rank"] + [k for k in rows[0] if k != "rank"]); w.writeheader(); w.writerows(rows)
for r in rows:
    print(r["rank"], r["name"], r["quadrant"], r["age"], r["nationality"], r["backing"], "|", r["why"][:150])

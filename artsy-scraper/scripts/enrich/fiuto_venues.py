"""Artists and artworks for sale at the venues with a track record ("sedi con fiuto").

Usage: python3 fiuto_venues.py partner_track_record.csv network_dir out_dir
Writes out_dir/venues.csv, venue_artists.csv, artworks_for_sale.csv.
Galleries: artists they represent on Artsy; institutions (or galleries without a roster): artists in their 2023-2026 shows.
Artworks: up to 20 works for sale per artist on Artsy, whoever sells them (seller and price as published).
"""
import csv, os, sys, time
import requests

TR, NET, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session(); s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})


def gql(q, v):
    for attempt in range(7):
        try:
            r = s.post(GQL, json={"query": q, "variables": v}, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            d = r.json()
            if d.get("data") is None:
                raise requests.HTTPError(str(d.get("errors"))[:300])
            return d["data"]
        except (requests.RequestException, ValueError) as e:
            print(f"  retry {2 ** attempt}s {e!r}"[:200], flush=True); time.sleep(2 ** attempt)
    raise RuntimeError("too many failures")


QP = """query($id:String!){ partner(id:$id){ slug name type locationsConnection(first:3){ edges{ node{ city country } } }
 artistsConnection(first:100, representedBy:true){ totalCount edges{ node{ slug name } } } } }"""
QA = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){ slug name
 filterArtworksConnection(first:20, forSale:true){ counts{ total } edges{ node{ slug title date medium category isUnique
   dimensions{ cm } saleMessage partner{ name slug }
   listPrice{ ... on Money{ major currencyCode } ... on PriceRange{ minPrice{ major currencyCode } maxPrice{ major } } } } } } } }"""

venues = [r for r in csv.DictReader(open(TR, encoding="utf-8"))
          if r["role"] == "sceglie" and int(r["early_bets"]) >= 3 and r["lift"] and float(r["lift"]) >= 1.3]
shows = {r["show_slug"]: r for r in csv.DictReader(open(f"{NET}/shows.csv", encoding="utf-8"))}
members = {}
for f in ("show_artists.csv", "artist_shows.csv"):
    for r in csv.DictReader(open(f"{NET}/{f}", encoding="utf-8")):
        a, sh = (r["artist_slug"], r["show_slug"])
        members.setdefault(sh, set()).add(a)
recent = {}
for sh, r in shows.items():
    p = r["partner_slug"] or ("ext:" + r["partner_name"])
    if r["start"][:4].isdigit() and int(r["start"][:4]) >= 2023 and r["kind"] != "fair" and r["fair_booth"] != "1":
        recent.setdefault(p, set()).update(members.get(sh, ()))

vrows, links = [], []
for v in venues:
    p = v["partner"]; roster = []; city = v["city"]; name = v["name"]; typ = v["type"]
    if not p.startswith("ext:"):
        d = gql(QP, {"id": p}).get("partner") or {}
        roster = [(e["node"]["slug"], "rappresentato") for e in ((d.get("artistsConnection") or {}).get("edges") or []) if e.get("node")]
        locs = [e["node"] for e in ((d.get("locationsConnection") or {}).get("edges") or []) if e.get("node")]
        city = city or ", ".join(sorted({l["city"] for l in locs if l.get("city")}))
        time.sleep(0.3)
    seen = {a for a, _ in roster}
    rec = [(a, "mostra 2023-2026") for a in sorted(recent.get(p, set())) if a not in seen]
    for a, how in roster + rec:
        links.append([p, a, how])
    vrows.append([p, name, typ, city, v["early_bets"], v["hits"], v["lift"], len(roster), len(rec)])
    print(name, len(roster), len(rec), flush=True)

with open(f"{OUT}/venues.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["venue", "venue_name", "venue_type", "city", "early_bets", "hits", "lift", "represented", "recent_show_artists"]); w.writerows(vrows)
with open(f"{OUT}/venue_artists.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["venue", "artist_slug", "link"]); w.writerows(links)

arts = sorted({a for _, a, _ in links})
print(len(arts), "artists: fetching works for sale", flush=True)
with open(f"{OUT}/artworks_for_sale.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["artist_slug", "artist_name", "for_sale_total", "slug", "title", "date", "medium", "category", "unique", "dimensions_cm",
                "price_min", "price_max", "currency", "sale_message", "seller", "seller_slug"])
    for i in range(0, len(arts), 4):
        chunk = arts[i:i + 4]
        for a in gql(QA, {"s": chunk, "n": len(chunk)}).get("artists") or []:
            if not a:
                continue
            fc = a.get("filterArtworksConnection") or {}
            tot = (fc.get("counts") or {}).get("total") or 0
            for e in fc.get("edges") or []:
                n = e.get("node") or {}; lp = n.get("listPrice") or {}
                if "major" in lp:
                    lo, hi, cur = lp.get("major"), lp.get("major"), lp.get("currencyCode")
                else:
                    lo, hi, cur = (lp.get("minPrice") or {}).get("major"), (lp.get("maxPrice") or {}).get("major"), (lp.get("minPrice") or {}).get("currencyCode")
                pt = n.get("partner") or {}
                w.writerow([a["slug"], a["name"], tot, n.get("slug"), (n.get("title") or "")[:120], n.get("date") or "", (n.get("medium") or "")[:120],
                            n.get("category") or "", int(bool(n.get("isUnique"))), (n.get("dimensions") or {}).get("cm") or "",
                            lo if lo is not None else "", hi if hi is not None else "", cur or "", n.get("saleMessage") or "", pt.get("name") or "", pt.get("slug") or ""])
        fh.flush()
        if (i // 4) % 50 == 0:
            print(f"  {i + len(chunk)}/{len(arts)}", flush=True)
        time.sleep(0.3)
print("done", flush=True)

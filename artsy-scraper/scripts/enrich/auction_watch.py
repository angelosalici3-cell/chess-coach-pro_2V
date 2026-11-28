"""Check whether the watched artists have works coming up at auction.

Usage: python3 auction_watch.py [picks.csv ...] [--out data/radar/auction_watch]
Sources (Artsy public GraphQL):
  1. works in auctions open on Artsy now or soon (filterArtworksConnection atAuction), with estimate and current bid;
  2. upcoming lots announced by auction houses (auctionResultsConnection state UPCOMING).
Writes out/latest.csv (all lots found now), out/seen.csv (every lot ever reported), out/report.md (new lots first).
"""
import argparse, csv, datetime as dt, os, time
import requests

GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session(); s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})
Q = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){ slug name
 onArtsy: filterArtworksConnection(first:30, atAuction:true){ edges{ node{ slug title date category medium dimensions{ cm }
   saleArtwork{ lotLabel estimate currentBid{ display } } sale{ name startAt endAt isClosed partner{ name } } } } }
 upcoming: auctionResultsConnection(first:30, state: UPCOMING, sort: DATE_DESC){ edges{ node{ internalID title saleDate saleTitle
   organization location lotNumber currency estimate{ display } dimensionText mediumText categoryText } } } } }"""
F = ["key", "artist_slug", "artist", "source", "auction_house", "sale", "date", "lot", "title", "category", "medium", "dimensions", "estimate", "current_bid", "url"]


def gql(v):
    for attempt in range(7):
        try:
            r = s.post(GQL, json={"query": Q, "variables": v}, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            d = r.json()
            if d.get("data") is None:
                raise requests.HTTPError(str(d.get("errors"))[:300])
            return d["data"]["artists"] or []
        except (requests.RequestException, ValueError) as e:
            print(f"  retry {2 ** attempt}s {e!r}"[:200], flush=True); time.sleep(2 ** attempt)
    raise RuntimeError("Artsy did not answer")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("lists", nargs="*", default=[os.path.join(root, "data/radar/fiuto/fiuto_picks.csv"), os.path.join(root, "data/radar/buy_list.csv")])
    ap.add_argument("--out", default=os.path.join(root, "data/radar/auction_watch"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    watch = {}
    for path in a.lists:
        for r in csv.DictReader(open(path, encoding="utf-8")):
            if path.endswith("buy_list.csv") and not r.get("pick_tier"):
                continue  # from the buy list only the ten picks
            watch[r["slug"]] = r["name"]
    found = []
    slugs = sorted(watch)
    for i in range(0, len(slugs), 5):
        for art in gql({"s": slugs[i:i + 5], "n": len(slugs[i:i + 5])}):
            if not art:
                continue
            for e in ((art.get("onArtsy") or {}).get("edges") or []):
                n = e.get("node") or {}; sa = n.get("saleArtwork") or {}; sale = n.get("sale") or {}
                if sale.get("isClosed"):
                    continue
                found.append({"key": "artsy:" + n["slug"], "artist_slug": art["slug"], "artist": art["name"], "source": "asta su Artsy",
                              "auction_house": (sale.get("partner") or {}).get("name") or "", "sale": sale.get("name") or "",
                              "date": (sale.get("endAt") or sale.get("startAt") or "")[:10], "lot": sa.get("lotLabel") or "", "title": n.get("title") or "",
                              "category": n.get("category") or "", "medium": (n.get("medium") or "")[:100], "dimensions": (n.get("dimensions") or {}).get("cm") or "",
                              "estimate": sa.get("estimate") or "", "current_bid": (sa.get("currentBid") or {}).get("display") or "",
                              "url": f"https://www.artsy.net/artwork/{n['slug']}"})
            for e in ((art.get("upcoming") or {}).get("edges") or []):
                n = e.get("node") or {}
                found.append({"key": "house:" + (n.get("internalID") or ""), "artist_slug": art["slug"], "artist": art["name"], "source": "asta annunciata",
                              "auction_house": n.get("organization") or "", "sale": n.get("saleTitle") or "", "date": (n.get("saleDate") or "")[:10],
                              "lot": n.get("lotNumber") or "", "title": n.get("title") or "", "category": n.get("categoryText") or "",
                              "medium": (n.get("mediumText") or "")[:100], "dimensions": n.get("dimensionText") or "",
                              "estimate": (n.get("estimate") or {}).get("display") or "", "current_bid": "",
                              "url": f"https://www.artsy.net/artist/{art['slug']}/auction-results"})
        time.sleep(0.3)
    for r in found:
        for k, v in r.items():
            r[k] = " ".join(str(v).split())
    seen_p = os.path.join(a.out, "seen.csv")
    seen = {r["key"] for r in csv.DictReader(open(seen_p, encoding="utf-8"))} if os.path.exists(seen_p) else set()
    new = [r for r in found if r["key"] not in seen]
    with open(os.path.join(a.out, "latest.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=F); w.writeheader(); w.writerows(found)
    first = not os.path.exists(seen_p)
    with open(seen_p, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=F + ["first_seen"])
        if first:
            w.writeheader()
        today = dt.date.today().isoformat()
        for r in new:
            w.writerow(dict(r, first_seen=today))
    line = lambda r: f"- **{r['artist']}**, «{r['title']}» ({r['category'] or 'n.d.'}) · {r['auction_house']}, {r['sale']} · {r['date'] or 'data n.d.'} · lotto {r['lot'] or '–'} · stima {r['estimate'] or 'n.d.'}" + (f" · offerta attuale {r['current_bid']}" if r['current_bid'] else "") + f" · {r['url']}"
    md = [f"# Controllo aste del {dt.date.today().isoformat()}", "",
          f"Artisti controllati: {len(watch)}. Lotti trovati: {len(found)}, di cui nuovi rispetto ai controlli precedenti: {len(new)}.", ""]
    md += ["## Nuovi", ""] + ([line(r) for r in new] or ["Nessun lotto nuovo."]) + [""]
    md += ["## Tutti i lotti in corso o annunciati", ""] + ([line(r) for r in found] or ["Nessuno."])
    open(os.path.join(a.out, "report.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()

"""Lot-level auction results per artist from Artsy's public GraphQL endpoint.

Usage: python3 auction_lots.py slugs.txt out_dir [--batch 4] [--lots 200]

Writes (append/resume) out_dir/lots.csv and out_dir/lots_done.txt.
One row per lot (most recent `--lots` per artist, upcoming sales skipped):
  slug, sale_date, title, category, medium, dimension_text, height, width, depth,
  currency, cents, cents_usd, display, est_low, est_high, bought_in, organization
Prices are kept in the sale currency (cents = minor units as Artsy reports them) so the
USD conversion can be checked and redone later (see lots_clean.py).
"""
from __future__ import annotations

import argparse
import csv
import os
import time

import requests

GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session()
s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})
Q = """query($s:[String]!,$n:Int!,$lots:Int!){ artists(slugs:$s, size:$n){ slug
 auctionResultsConnection(first:$lots, sort: DATE_DESC){ edges{ node{ title saleDate boughtIn isUpcoming
   categoryText mediumText dimensionText currency organization dimensions{ height width depth }
   priceRealized{ cents centsUSD display } estimate{ low high } } } } } }"""
F = ["slug", "sale_date", "title", "category", "medium", "dimension_text", "height", "width", "depth",
     "currency", "cents", "cents_usd", "display", "est_low", "est_high", "bought_in", "organization"]


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
            wait = 2 ** attempt
            print(f"  retry in {wait}s: {e!r}"[:300], flush=True)
            time.sleep(wait)
    raise RuntimeError("too many failures")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs")
    ap.add_argument("outdir")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lots", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.2)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    out, donep = os.path.join(a.outdir, "lots.csv"), os.path.join(a.outdir, "lots_done.txt")
    slugs = [x.strip() for x in open(a.slugs, encoding="utf-8") if x.strip()]
    done = set(open(donep).read().split()) if os.path.exists(donep) else set()
    todo = [x for x in slugs if x not in done]
    print(f"{len(todo):,} artists to fetch", flush=True)
    new = not os.path.exists(out)
    fh = open(out, "a", newline="", encoding="utf-8")
    w = csv.writer(fh)
    if new:
        w.writerow(F)
    dfh = open(donep, "a")
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        got = {x["slug"]: x for x in gql({"s": chunk, "n": len(chunk), "lots": a.lots}) if x}
        for slug in chunk:
            for e in ((got.get(slug) or {}).get("auctionResultsConnection") or {}).get("edges") or []:
                n = (e or {}).get("node") or {}
                if n.get("isUpcoming"):
                    continue
                pr, est, dim = n.get("priceRealized") or {}, n.get("estimate") or {}, n.get("dimensions") or {}
                w.writerow([slug, (n.get("saleDate") or "")[:10], (n.get("title") or "")[:120],
                            n.get("categoryText") or "", (n.get("mediumText") or "")[:120],
                            n.get("dimensionText") or "", dim.get("height") or "", dim.get("width") or "",
                            dim.get("depth") or "", n.get("currency") or "", pr.get("cents") or "",
                            pr.get("centsUSD") or "", pr.get("display") or "", est.get("low") or "",
                            est.get("high") or "", int(bool(n.get("boughtIn"))), n.get("organization") or ""])
            dfh.write(slug + "\n")
        fh.flush()
        dfh.flush()
        if (i // a.batch) % 100 == 0:
            print(f"  {i + len(chunk):,}/{len(todo):,}", flush=True)
        time.sleep(a.delay)
    print("done", flush=True)


if __name__ == "__main__":
    main()

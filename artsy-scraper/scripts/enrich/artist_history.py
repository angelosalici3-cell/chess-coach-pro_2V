"""Yearly history per artist from Artsy's public GraphQL endpoint.

Usage: python3 artist_history.py slugs.txt outdir [--batch 3]

Writes (append/resume):
  outdir/history_yearly.csv  slug, year, shows, inst_shows, solo_shows, fair_shows, articles,
                             lots_offered, lots_sold, median_price_usd, median_unique_usd,
                             median_price_to_estimate
  outdir/listings.csv        slug, currency, price, is_unique, category   (works for sale now)
  outdir/fx_samples.csv      currency, year, usd_per_unit                  (from sold lots)
  outdir/done.txt            slugs already processed

Shows and articles only cover what Artsy lists (its partners and its own editorial).
price_to_estimate = realized price / mid estimate, both in the sale currency.
Unique = auction category not Print / Multiple / Photograph edition / Ephemera.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import time
from collections import defaultdict

import requests

GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session()
s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})
Q = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){ slug
 showsConnection(first:100, sort: START_AT_DESC){ edges{ node{ startAt kind partner{ ... on Partner{ type } } } } }
 articlesConnection(first:100, sort: PUBLISHED_AT_DESC){ edges{ node{ publishedAt } } }
 auctionResultsConnection(first:200, sort: DATE_DESC){ edges{ node{ saleDate boughtIn isUpcoming categoryText currency
   estimate{ low high } priceRealized{ cents centsUSD } } } }
 filterArtworksConnection(first:30, forSale:true){ edges{ node{ isUnique category
   listPrice{ ... on Money{ major currencyCode } ... on PriceRange{ minPrice{ major currencyCode } maxPrice{ major } } } } } } } }"""
NOT_UNIQUE = {"print", "multiple", "ephemera or merchandise", "books and portfolios", "posters"}
FIRST_YEAR = 2010
YF = ["slug", "year", "shows", "inst_shows", "solo_shows", "fair_shows", "articles", "lots_offered",
      "lots_sold", "median_price_usd", "median_unique_usd", "median_price_to_estimate"]


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


def edges(a, key):
    return [e["node"] for e in ((a.get(key) or {}).get("edges") or []) if e and e.get("node")]


def process(a):
    y = defaultdict(lambda: defaultdict(int))
    prices, uniq, ratio = defaultdict(list), defaultdict(list), defaultdict(list)
    fx = []
    for sh in edges(a, "showsConnection"):
        yr = int((sh.get("startAt") or "0")[:4] or 0)
        if yr < FIRST_YEAR:
            continue
        y[yr]["shows"] += 1
        kind = sh.get("kind") or ""
        y[yr]["solo_shows"] += kind == "solo"
        y[yr]["fair_shows"] += kind == "fair"
        y[yr]["inst_shows"] += ((sh.get("partner") or {}).get("type") == "Institution")
    for ar in edges(a, "articlesConnection"):
        yr = int((ar.get("publishedAt") or "0")[:4] or 0)
        if yr >= FIRST_YEAR:
            y[yr]["articles"] += 1
    for lot in edges(a, "auctionResultsConnection"):
        if lot.get("isUpcoming"):
            continue
        yr = int((lot.get("saleDate") or "0")[:4] or 0)
        if yr < FIRST_YEAR:
            continue
        pr = lot.get("priceRealized") or {}
        if not lot.get("boughtIn") and not pr.get("centsUSD"):
            continue  # result not published
        y[yr]["lots_offered"] += 1
        if lot.get("boughtIn"):
            continue
        usd = pr["centsUSD"] / 100
        y[yr]["lots_sold"] += 1
        prices[yr].append(usd)
        if (lot.get("categoryText") or "").strip().lower() not in NOT_UNIQUE:
            uniq[yr].append(usd)
        est = lot.get("estimate") or {}
        if est.get("low") and est.get("high") and pr.get("cents"):
            ratio[yr].append(pr["cents"] / ((est["low"] + est["high"]) / 2))
        cur = lot.get("currency")
        if cur and cur != "USD" and pr.get("cents") and len(fx) < 3:
            fx.append([cur, yr, round(pr["centsUSD"] / pr["cents"], 5)])
    rows = []
    for yr in sorted(y):
        d = y[yr]
        rows.append({"slug": a["slug"], "year": yr, **{k: d.get(k, 0) for k in YF[2:9]},
                     "median_price_usd": round(statistics.median(prices[yr])) if prices[yr] else "",
                     "median_unique_usd": round(statistics.median(uniq[yr])) if uniq[yr] else "",
                     "median_price_to_estimate": round(statistics.median(ratio[yr]), 3) if ratio[yr] else ""})
    listings = []
    for w in edges(a, "filterArtworksConnection"):
        lp = w.get("listPrice") or {}
        if "major" in lp:
            cur, price = lp.get("currencyCode"), lp["major"]
        elif lp.get("minPrice"):
            cur = lp["minPrice"].get("currencyCode")
            lo, hi = lp["minPrice"].get("major"), (lp.get("maxPrice") or {}).get("major")
            price = (lo + hi) / 2 if lo and hi else lo or hi
        else:
            continue
        if price:
            listings.append([a["slug"], cur, price, int(bool(w.get("isUnique"))), w.get("category") or ""])
    return rows, listings, fx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs")
    ap.add_argument("outdir")
    ap.add_argument("--batch", type=int, default=3)
    ap.add_argument("--delay", type=float, default=0.2)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    p = lambda n: os.path.join(a.outdir, n)
    slugs = [x.strip() for x in open(a.slugs, encoding="utf-8") if x.strip()]
    done = set(open(p("done.txt")).read().split()) if os.path.exists(p("done.txt")) else set()
    todo = [x for x in slugs if x not in done]
    print(f"{len(todo):,} artists to fetch", flush=True)
    files = {}
    for name, header in (("history_yearly.csv", YF), ("listings.csv", ["slug", "currency", "price", "is_unique", "category"]),
                         ("fx_samples.csv", ["currency", "year", "usd_per_unit"])):
        new = not os.path.exists(p(name))
        fh = open(p(name), "a", newline="", encoding="utf-8")
        w = csv.writer(fh)
        if new:
            w.writerow(header)
        files[name] = (fh, w)
    donef = open(p("done.txt"), "a")
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        got = {x["slug"]: x for x in gql({"s": chunk, "n": len(chunk)}) if x}
        for slug in chunk:
            if slug in got:
                rows, listings, fx = process(got[slug])
                for r in rows:
                    files["history_yearly.csv"][1].writerow([r[k] for k in YF])
                for l in listings:
                    files["listings.csv"][1].writerow(l)
                for f in fx:
                    files["fx_samples.csv"][1].writerow(f)
            donef.write(slug + "\n")
        for fh, _ in files.values():
            fh.flush()
        donef.flush()
        if (i // a.batch) % 100 == 0:
            print(f"  {i + len(chunk):,}/{len(todo):,}", flush=True)
        time.sleep(a.delay)
    print("done", flush=True)


if __name__ == "__main__":
    main()

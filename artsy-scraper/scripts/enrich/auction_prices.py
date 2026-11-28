"""Auction price statistics per artist from Artsy's public GraphQL endpoint.

Usage: python3 auction_prices.py signals.csv out.csv [--lots 50] [--years 5]
Fetches the most recent `--lots` auction results per artist (only artists with
auction_results > 0) and summarises the ones inside the last `--years` years.
Prices are Artsy's priceRealized converted to USD (hammer + premium as reported).
Resumable: artists already in out.csv are skipped.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import statistics
import time

import requests

GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session()
s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})

Q = """query($s:[String]!,$n:Int!,$lots:Int!){ artists(slugs:$s, size:$n){ slug
  auctionResultsConnection(first:$lots, sort: DATE_DESC){ edges{ node{
    saleDate boughtIn priceRealized{ centsUSD } } } } } }"""

FIELDS = ["slug", "lots_considered", "lots_sold", "sell_through_pct", "mean_price_usd",
          "median_price_usd", "max_price_usd", "last_sale_date"]


def gql(variables):
    for attempt in range(6):
        try:
            r = s.post(GQL, json={"query": Q, "variables": variables}, timeout=90)
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


def summarise(slug, edges, since, today):
    lots = []
    for e in edges:
        n = (e or {}).get("node") or {}
        d = (n.get("saleDate") or "")[:10]
        if not d or d < since or d > today:  # skip upcoming sales
            continue
        cents = (n.get("priceRealized") or {}).get("centsUSD")
        if n.get("boughtIn"):
            lots.append((d, None))
        elif cents:
            lots.append((d, cents / 100))
        # no price and not bought in: result not published yet, skip
    sold = [p for _, p in lots if p]
    return {
        "slug": slug, "lots_considered": len(lots), "lots_sold": len(sold),
        "sell_through_pct": round(100 * len(sold) / len(lots), 1) if lots else "",
        "mean_price_usd": round(statistics.fmean(sold)) if sold else "",
        "median_price_usd": round(statistics.median(sold)) if sold else "",
        "max_price_usd": round(max(sold)) if sold else "",
        "last_sale_date": max(d for d, _ in lots) if lots else "",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--lots", type=int, default=50)
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args()
    today = dt.date.today()
    since = today.replace(year=today.year - a.years).isoformat()
    rows = [r for r in csv.DictReader(open(a.src, encoding="utf-8")) if int(r.get("auction_results") or 0) > 0]
    done = {r["slug"] for r in csv.DictReader(open(a.out, encoding="utf-8"))} if os.path.exists(a.out) else set()
    todo = [r["slug"] for r in rows if r["slug"] not in done]
    print(f"{len(todo):,} artists to fetch (since {since})", flush=True)
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for i in range(0, len(todo), a.batch):
            chunk = todo[i:i + a.batch]
            got = {x["slug"]: x for x in gql({"s": chunk, "n": len(chunk), "lots": a.lots}) if x}
            for slug in chunk:
                edges = ((got.get(slug) or {}).get("auctionResultsConnection") or {}).get("edges") or []
                w.writerow(summarise(slug, edges, since, today.isoformat()))
            if (i // a.batch) % 50 == 0:
                fh.flush()
                print(f"  {i + len(chunk):,}/{len(todo):,}", flush=True)
            time.sleep(a.delay)
    print("done", flush=True)


if __name__ == "__main__":
    main()

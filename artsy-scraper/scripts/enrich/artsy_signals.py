"""Enrich the Artsy artist list with popularity and expert-recognition signals.

Uses Artsy's public GraphQL endpoint (no auth), batching artists by slug.

  pass 1 (follows):  python3 artsy_signals.py follows artists.csv follows.csv
  pass 2 (insights): python3 artsy_signals.py insights follows.csv signals.csv --min-follows 100

Both passes resume: rows already present in the output file are skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time

import requests

GQL = "https://metaphysics-production.artsy.net/v2"
UA = "artsy-research-script/1.0"

INSIGHT_KINDS = [
    "COLLECTED", "SOLO_SHOW", "GROUP_SHOW", "BIENNIAL", "REVIEWED",
    "PRIVATE_COLLECTIONS", "FOUNDATIONS", "AWARDS", "RESIDENCIES",
    "CRITICALLY_ACCLAIMED", "HIGH_AUCTION_RECORD", "ACTIVE_SECONDARY_MARKET",
    "ARTSY_VANGUARD_YEAR", "CURATORS_PICK_EMERGING", "TRENDING_NOW",
    "GAINING_FOLLOWERS", "RECENT_CAREER_EVENT",
]

session = requests.Session()
session.headers.update({"Content-Type": "application/json", "User-Agent": UA})


def gql(query: str, variables: dict) -> dict:
    for attempt in range(6):
        try:
            r = session.post(GQL, json={"query": query, "variables": variables}, timeout=60)
            if r.status_code in (429,) or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            d = r.json()
            if d.get("data") is None:
                raise requests.HTTPError(str(d.get("errors"))[:300])
            return d["data"]
        except (requests.RequestException, ValueError) as e:
            wait = 2 ** attempt
            print(f"  retry in {wait}s: {e!r}"[:300], flush=True)
            time.sleep(wait)
    raise RuntimeError("too many failures")


def done_slugs(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {row["slug"] for row in csv.DictReader(f)}


def batches(items, n):
    for i in range(0, len(items), n):
        yield items[i:i + n]


Q_FOLLOWS = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){
  slug counts{ follows artworks auctionResults partnerShows } } }"""

Q_INSIGHTS = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){
  slug insights{ kind label entities } } }"""


def run_pass(kind: str, src: str, dst: str, min_follows: int, batch: int, delay: float):
    with open(src, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if kind == "insights":
        rows = [r for r in rows if int(r.get("follows") or 0) >= min_follows]
    have = done_slugs(dst)
    todo = [r for r in rows if r["slug"] not in have]
    print(f"{kind}: {len(rows):,} candidates, {len(todo):,} to fetch", flush=True)

    base_fields = list(rows[0].keys()) if rows else []
    if kind == "follows":
        extra = ["follows", "artworks", "auction_results", "partner_shows"]
        fields = base_fields + [x for x in extra if x not in base_fields]
    else:
        fields = base_fields + [k.lower() for k in INSIGHT_KINDS] + ["expert_score", "insights_json"]

    new = not os.path.exists(dst)
    with open(dst, "a", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        for i, chunk in enumerate(batches(todo, batch)):
            by_slug = {r["slug"]: r for r in chunk}
            data = gql(Q_FOLLOWS if kind == "follows" else Q_INSIGHTS,
                       {"s": list(by_slug), "n": len(by_slug)})
            for a in data["artists"] or []:
                if not a or a["slug"] not in by_slug:
                    continue
                row = dict(by_slug.pop(a["slug"]))
                if kind == "follows":
                    c = a.get("counts") or {}
                    row.update(follows=c.get("follows") or 0, artworks=c.get("artworks") or 0,
                               auction_results=c.get("auctionResults") or 0,
                               partner_shows=c.get("partnerShows") or 0)
                else:
                    ins = [x for x in (a.get("insights") or [])
                           if x.get("entities") or not re.search(r"\b0 major", x.get("label") or "")]
                    for k in INSIGHT_KINDS:
                        row[k.lower()] = ""
                    for x in ins:
                        k = x["kind"].lower()
                        if k in row:
                            row[k] = "; ".join(x.get("entities") or []) or x.get("label") or "yes"
                    row["expert_score"] = expert_score(ins)
                    row["insights_json"] = json.dumps(ins, ensure_ascii=False)
                w.writerow(row)
            for row in by_slug.values():  # not returned by API: keep row with empty values
                w.writerow(row)
            if i % 50 == 0:
                out.flush()
                print(f"  {(i + 1) * batch:,}/{len(todo):,}", flush=True)
            time.sleep(delay)
    print("done", flush=True)


# Weights: institutional recognition counts more than market/attention signals.
WEIGHTS = {
    "COLLECTED": 3, "SOLO_SHOW": 3, "BIENNIAL": 3, "REVIEWED": 2, "GROUP_SHOW": 1,
    "PRIVATE_COLLECTIONS": 2, "FOUNDATIONS": 1, "AWARDS": 2, "RESIDENCIES": 1,
    "CRITICALLY_ACCLAIMED": 2, "CURATORS_PICK_EMERGING": 2, "ARTSY_VANGUARD_YEAR": 2,
}


def expert_score(insights: list[dict]) -> int:
    score = 0
    for x in insights:
        w = WEIGHTS.get(x["kind"], 0)
        n = max(1, len(x.get("entities") or []))
        score += w * min(n, 5)
    return score


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["follows", "insights"])
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--min-follows", type=int, default=100)
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args()
    run_pass(a.kind, a.src, a.dst, a.min_follows, a.batch if a.kind == "follows" else min(a.batch, 25), a.delay)

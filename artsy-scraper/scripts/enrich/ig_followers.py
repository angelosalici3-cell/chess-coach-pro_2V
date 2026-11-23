"""Fetch Instagram follower counts via Meta's official Business Discovery API.

The access token is NOT read from this script or the environment: in the cloud session
the network proxy injects it as `Authorization: Bearer ...` for graph.facebook.com.
To run elsewhere, set IG_TOKEN.

Usage: python3 ig_followers.py instagram.csv out.csv [--priority matrix.csv] [--per-hour 190]
Resumable: handles already in out.csv are skipped.
Only professional (business/creator) Instagram accounts can be read.
"""
from __future__ import annotations

import argparse
import csv
import os
import time

import requests

API = "https://graph.facebook.com/v21.0"
s = requests.Session()
if os.environ.get("IG_TOKEN"):
    s.headers["Authorization"] = f"Bearer {os.environ['IG_TOKEN']}"
RATE_LIMIT_CODES = {4, 17, 32, 613, 80002}


def call(path: str, params: dict) -> dict:
    while True:
        r = s.get(f"{API}/{path}", params=params, timeout=60)
        d = r.json() if r.headers.get("content-type", "").startswith(("application/json", "text/javascript")) else {}
        err = d.get("error") or {}
        if err.get("code") in RATE_LIMIT_CODES:
            print("  rate limit reached, sleeping 1h", flush=True)
            time.sleep(3600)
            continue
        return d if d else {"error": {"message": f"HTTP {r.status_code}"}}


def my_ig_user_id() -> str:
    d = call("me/accounts", {"fields": "name,instagram_business_account"})
    if "error" in d:
        raise SystemExit(f"Token problem: {d['error'].get('message')}")
    for page in d.get("data", []):
        ig = page.get("instagram_business_account")
        if ig:
            print(f"Using Instagram business account linked to page '{page['name']}'")
            return ig["id"]
    raise SystemExit("No Instagram professional account linked to your Facebook Pages.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instagram_csv")
    ap.add_argument("out")
    ap.add_argument("--priority", help="matrix csv: its artists are fetched first")
    ap.add_argument("--per-hour", type=int, default=190)
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.instagram_csv, encoding="utf-8")))
    if a.priority:
        first = {r["slug"] for r in csv.DictReader(open(a.priority, encoding="utf-8"))}
        rows.sort(key=lambda r: r["slug"] not in first)
    done = set()
    if os.path.exists(a.out):
        done = {r["slug"] for r in csv.DictReader(open(a.out, encoding="utf-8"))}
    todo = [r for r in rows if r["slug"] not in done]
    print(f"{len(todo):,} accounts to fetch (~{len(todo) / a.per_hour:.1f} h)", flush=True)

    me = my_ig_user_id()
    fields = ["slug", "instagram", "ig_followers", "ig_follows", "ig_media_count", "ig_status", "fetched_at"]
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        for i, r in enumerate(todo, 1):
            user = r["instagram"].split(";")[0].strip()
            d = call(me, {"fields": f"business_discovery.username({user}){{followers_count,follows_count,media_count}}"})
            bd = d.get("business_discovery") or {}
            status = "ok" if bd else ("not_professional_or_missing" if "error" in d else "empty")
            w.writerow({"slug": r["slug"], "instagram": user,
                        "ig_followers": bd.get("followers_count", ""), "ig_follows": bd.get("follows_count", ""),
                        "ig_media_count": bd.get("media_count", ""), "ig_status": status,
                        "fetched_at": time.strftime("%Y-%m-%d")})
            fh.flush()
            if i % 25 == 0:
                print(f"  {i:,}/{len(todo):,}", flush=True)
            time.sleep(3600 / a.per_hour)
    print("done", flush=True)


if __name__ == "__main__":
    main()

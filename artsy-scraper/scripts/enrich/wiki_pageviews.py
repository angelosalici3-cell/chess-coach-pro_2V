"""Monthly English Wikipedia page views (users only) per artist, from the Wikimedia REST API.

Usage: python3 wiki_pageviews.py wikipedia_titles.csv out.csv [--start 20150701] [--delay 0.8]
Resumable. On HTTP 429 it waits and retries. Months with no data are omitted by the API.
"""
import argparse
import csv
import datetime as dt
import os
import time
import urllib.parse

import requests

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{t}/monthly/{a}/{b}"
s = requests.Session()
s.headers["User-Agent"] = "ArtMarketResearchBot/1.0 (non-commercial research; python-requests)"

ap = argparse.ArgumentParser()
ap.add_argument("titles"); ap.add_argument("out")
ap.add_argument("--start", default="20150701"); ap.add_argument("--delay", type=float, default=0.8)
a = ap.parse_args()
end = dt.date.today().replace(day=1).strftime("%Y%m%d")
rows = list(csv.DictReader(open(a.titles, encoding="utf-8")))
done = {r["slug"] for r in csv.DictReader(open(a.out, encoding="utf-8"))} if os.path.exists(a.out) else set()
todo = [r for r in rows if r["slug"] not in done]
print(f"{len(todo):,} titles to fetch", flush=True)
new = not os.path.exists(a.out)
with open(a.out, "a", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    if new:
        w.writerow(["slug", "month", "views"])
    for i, r in enumerate(todo, 1):
        url = API.format(t=urllib.parse.quote(r["enwiki_title"].replace(" ", "_"), safe=""), a=a.start, b=end)
        for attempt in range(8):
            try:
                resp = s.get(url, timeout=60)
            except requests.RequestException as e:
                print(f"  error {e!r}"[:200], flush=True); time.sleep(10 * (attempt + 1)); continue
            if resp.status_code == 429:
                wait = int(resp.headers.get("retry-after", "60") or 60)
                print(f"  429, waiting {wait}s", flush=True); time.sleep(wait); continue
            break
        else:
            print(f"  giving up on {r['enwiki_title']}", flush=True)
            continue
        if resp.status_code not in (200, 404):
            print(f"  HTTP {resp.status_code} for {r['enwiki_title']}", flush=True)
            continue
        items = resp.json().get("items", []) if resp.status_code == 200 else []
        if not items:
            w.writerow([r["slug"], "", 0])  # marks as done with no data
        for it in items:
            w.writerow([r["slug"], it["timestamp"][:6], it["views"]])
        fh.flush()
        if i % 250 == 0:
            print(f"  {i:,}/{len(todo):,}", flush=True)
        time.sleep(a.delay)
print("done", flush=True)

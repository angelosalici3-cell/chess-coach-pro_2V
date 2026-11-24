"""Gallery representation, art-fair presence and career start per artist (Artsy public GraphQL).

Usage: python3 artist_extras.py matrix.csv outdir [--batch 8]
Writes (append/resume): outdir/extras.csv, outdir/fairs_yearly.csv, outdir/done.txt

- represented_*: galleries Artsy flags as representing the artist (partnerArtists.representedBy)
- top_galleries: represented galleries that are on TOP_GALLERIES (a fixed list chosen for this
  analysis: large international galleries; edit it to change the definition)
- institutions_linked: museums/institutions that list the artist on their Artsy profile
- fairs: shows of kind "fair" among the latest 100 shows; top fairs = TOP_FAIRS prefixes
- first_show_year / first_lot_year: earliest show and auction lot recorded on Artsy
  (Artsy's show records start around 2010, so older careers start earlier than this)
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import time
from collections import Counter

import requests

GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session()
s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})

TOP_GALLERIES = [
    "Gagosian", "David Zwirner", "Hauser & Wirth", "Pace", "White Cube", "Thaddaeus Ropac", "Lisson Gallery",
    "Perrotin", "Marian Goodman", "Sprüth Magers", "Gladstone", "Victoria Miro", "Lehmann Maupin",
    "Massimo De Carlo", "Galerie Max Hetzler", "Esther Schipper", "kurimanzutto", "Sadie Coles HQ",
    "Galerie Eva Presenhuber", "Blum", "Petzel", "Kamel Mennour", "Almine Rech", "Mendes Wood DM",
    "Jack Shainman Gallery", "Matthew Marks Gallery", "Paula Cooper Gallery", "Regen Projects",
    "GALLERIA CONTINUA", "Xavier Hufkens", "Galerie Chantal Crousel", "LGDR", "Skarstedt",
    "Stephen Friedman Gallery", "Timothy Taylor", "Kasmin", "Sean Kelly", "Tanya Bonakdar Gallery",
    "Luhring Augustine", "Galerie Lelong", "Goodman Gallery", "neugerriemschneider", "Galerie Buchholz",
]
TOP_FAIRS = ["Art Basel", "Frieze", "TEFAF", "Paris+ par Art Basel", "FIAC"]
_norm = lambda x: re.sub(r"\s+", " ", (x or "").lower()).strip()
_top = [(_norm(g), g) for g in TOP_GALLERIES]


def top_gallery(name):
    n = _norm(name)
    for key, label in _top:
        # whole-word prefix match: "pace" matches "Pace Gallery" but not "Space"
        if n == key or n.startswith(key + " "):
            return label
    return None


def fair_label(name):
    for f in TOP_FAIRS:
        if (name or "").startswith(f):
            return re.sub(r"\s+\d{4}$", "", name)
    return None


Q = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){ slug
  partnerArtists(size:50){ representedBy partner{ name type } }
  shows: showsConnection(first:100, sort: START_AT_DESC){ edges{ node{ startAt kind fair{ name } } } }
  firstShow: showsConnection(first:1, sort: START_AT_ASC){ edges{ node{ startAt } } }
  firstLot: auctionResultsConnection(first:1, sort: DATE_ASC){ edges{ node{ saleDate } } } } }"""
FIELDS = ["slug", "represented_count", "represented_galleries", "top_gallery_count", "top_galleries",
          "institutions_linked", "fairs_total", "top_fairs_total", "top_fairs_last3y", "first_top_fair_year",
          "top_fairs", "first_show_year", "first_lot_year"]


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


def year(x):
    return int(x[:4]) if x and x[:4].isdigit() else None


def process(a, this_year):
    pa = a.get("partnerArtists") or []
    rep = [p["partner"]["name"] for p in pa if p.get("representedBy") and (p.get("partner") or {}).get("type") == "Gallery"]
    tops = sorted({t for t in (top_gallery(n) for n in rep) if t})
    inst = sum(1 for p in pa if (p.get("partner") or {}).get("type") == "Institution")
    fairs, yearly = Counter(), Counter()
    total = 0
    for e in ((a.get("shows") or {}).get("edges") or []):
        n = (e or {}).get("node") or {}
        if n.get("kind") != "fair":
            continue
        total += 1
        lab = fair_label((n.get("fair") or {}).get("name"))
        y = year(n.get("startAt"))
        if lab and y and y <= this_year:
            fairs[lab] += 1
            yearly[y] += 1
    first = lambda k, f: year(((((a.get(k) or {}).get("edges") or [{}])[0] or {}).get("node") or {}).get(f))
    row = {
        "slug": a["slug"], "represented_count": len(rep), "represented_galleries": "; ".join(rep),
        "top_gallery_count": len(tops), "top_galleries": "; ".join(tops), "institutions_linked": inst,
        "fairs_total": total, "top_fairs_total": sum(fairs.values()),
        "top_fairs_last3y": sum(v for y, v in yearly.items() if y >= this_year - 2),
        "first_top_fair_year": min(yearly) if yearly else "",
        "top_fairs": "; ".join(f"{k} ({v})" for k, v in fairs.most_common(6)),
        "first_show_year": first("firstShow", "startAt") or "", "first_lot_year": first("firstLot", "saleDate") or "",
    }
    return row, sorted(yearly.items())


def main():
    import datetime as dt
    ap = argparse.ArgumentParser()
    ap.add_argument("matrix")
    ap.add_argument("outdir")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--delay", type=float, default=0.2)
    a = ap.parse_args()
    this_year = dt.date.today().year
    os.makedirs(a.outdir, exist_ok=True)
    p = lambda n: os.path.join(a.outdir, n)
    slugs = [r["slug"] for r in csv.DictReader(open(a.matrix, encoding="utf-8"))]
    done = set(open(p("done.txt")).read().split()) if os.path.exists(p("done.txt")) else set()
    todo = [x for x in slugs if x not in done]
    print(f"{len(todo):,} artists to fetch", flush=True)
    new = not os.path.exists(p("extras.csv"))
    fe = open(p("extras.csv"), "a", newline="", encoding="utf-8"); we = csv.DictWriter(fe, fieldnames=FIELDS)
    fy = open(p("fairs_yearly.csv"), "a", newline="", encoding="utf-8"); wy = csv.writer(fy)
    if new:
        we.writeheader(); wy.writerow(["slug", "year", "top_fairs"])
    fd = open(p("done.txt"), "a")
    for i in range(0, len(todo), a.batch):
        chunk = todo[i:i + a.batch]
        got = {x["slug"]: x for x in gql({"s": chunk, "n": len(chunk)}) if x}
        for slug in chunk:
            if slug in got:
                row, yearly = process(got[slug], this_year)
                we.writerow(row)
                for y, n in yearly:
                    wy.writerow([slug, y, n])
            fd.write(slug + "\n")
        fe.flush(); fy.flush(); fd.flush()
        if (i // a.batch) % 100 == 0:
            print(f"  {i + len(chunk):,}/{len(todo):,}", flush=True)
        time.sleep(a.delay)
    print("done", flush=True)


if __name__ == "__main__":
    main()

"""Attach Instagram usernames from Wikidata to Artsy artists.

Usage: python3 match_instagram.py artists.csv <dir with wd_*.csv> out.csv
Match order: Artsy artist ID on Wikidata (P2042) -> exact, unambiguous name match.
"""
import csv
import glob
import os
import sys
import unicodedata
from collections import defaultdict


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace(".", " ").replace("-", " ").split())


artists_csv, wd_dir, out = sys.argv[1:4]
by_artsy, by_name = {}, defaultdict(dict)
for f in glob.glob(os.path.join(wd_dir, "wd_*.csv")):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if not r.get("ig"):
            continue
        qid = r["p"].rsplit("/", 1)[-1]
        if r.get("artsy"):
            by_artsy.setdefault(r["artsy"], (qid, r["ig"]))
        by_name[norm(r["pLabel"])].setdefault(qid, r["ig"])

artists = list(csv.DictReader(open(artists_csv, encoding="utf-8")))
name_count = defaultdict(int)
for a in artists:
    name_count[norm(a["name"])] += 1

n_id = n_name = 0
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["slug", "instagram", "instagram_url", "wikidata_id", "match"])
    for a in artists:
        hit = by_artsy.get(a["slug"])
        how = "artsy_id"
        if not hit:
            cands = by_name.get(norm(a["name"]), {})
            # only if exactly one Wikidata person and one Artsy artist share the name
            if len(cands) == 1 and name_count[norm(a["name"])] == 1 and len(norm(a["name"]).split()) >= 2:
                hit = next(iter(cands.items()))
                how = "name"
        if hit:
            qid, ig = hit
            ig = ig.strip().lstrip("@")
            w.writerow([a["slug"], ig, f"https://www.instagram.com/{ig}/", qid, how])
            n_id += how == "artsy_id"
            n_name += how == "name"
print(f"matched by artsy id: {n_id:,}, by name: {n_name:,}")

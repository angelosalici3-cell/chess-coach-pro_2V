"""Append manual Instagram search results. stdin lines: slug|handle|confidence|followers|evidence"""
import csv, sys
T = {r["slug"]: r["name"] for r in csv.DictReader(open("data/ig_search_targets.csv"))}
path = "data/ig_search_results.csv"
done = {r["slug"] for r in csv.DictReader(open(path))}
w = csv.writer(open(path, "a"))
n = 0
for line in sys.stdin:
    if not line.strip(): continue
    slug, h, c, f, e = [p.strip() for p in line.split("|")]
    if slug in done or slug not in T: print("skip", slug); continue
    w.writerow([slug, T[slug], h.lstrip("@"), c, f, e]); done.add(slug); n += 1
print("added", n, "total", len(done))

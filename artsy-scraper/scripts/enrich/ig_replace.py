"""Replace rows of data/ig_search_results.csv by slug. stdin lines: slug|handle|confidence|followers|evidence"""
import csv, sys
p = "data/ig_search_results.csv"
rows = list(csv.DictReader(open(p, encoding="utf-8"))); f = list(rows[0].keys())
new = {}
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    slug, h, c, fo, e = [x.strip() for x in line.split("|", 4)]
    new[slug] = dict(instagram=h.lstrip("@"), confidence=c or ("" if h else ""), followers_snippet=fo, evidence=e)
n = 0
for r in rows:
    if r["slug"] in new:
        r.update(new[r["slug"]]); n += 1
w = csv.DictWriter(open(p, "w", newline="", encoding="utf-8"), fieldnames=f); w.writeheader(); w.writerows(rows)
print("replaced", n, "of", len(new))

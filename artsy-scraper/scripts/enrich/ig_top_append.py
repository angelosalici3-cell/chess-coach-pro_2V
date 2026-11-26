"""Append/replace Instagram results for the synthesis top list.
stdin lines: slug|handle|confidence|followers|evidence   (later lines replace earlier ones for the same slug)
Writes data/ig_top300_results.csv; `--next N` prints the next N targets without a result."""
import csv, sys
TP, RP = "data/ig_top300_targets.csv", "data/ig_top300_results.csv"
T = {r["slug"]: r for r in csv.DictReader(open(TP))}
F = ["slug", "name", "instagram", "confidence", "followers_snippet", "evidence"]
try:
    R = {r["slug"]: r for r in csv.DictReader(open(RP))}
except FileNotFoundError:
    R = {}
if len(sys.argv) > 2 and sys.argv[1] == "--next":
    n = int(sys.argv[2]); k = 0
    for r in T.values():
        if r["slug"] in R: continue
        print(r["rank"], r["slug"], "|", r["name"], "|", r["nationality"][:20], r["birthday"][:4], "|", r["task"], r["known_handle"]); k += 1
        if k >= n: break
    print("restanti:", sum(1 for s in T if s not in R)); sys.exit()
n = 0
for line in sys.stdin:
    if not line.strip(): continue
    slug, h, c, f, e = [p.strip() for p in line.split("|", 4)]
    if slug not in T: print("skip", slug); continue
    R[slug] = {"slug": slug, "name": T[slug]["name"], "instagram": h.lstrip("@"), "confidence": c, "followers_snippet": f, "evidence": e.replace("|", "/")}; n += 1
w = csv.DictWriter(open(RP, "w", newline=""), fieldnames=F); w.writeheader()
for s in T:
    if s in R: w.writerow(R[s])
print("scritti", n, "totale", len(R), "di", len(T))

"""Print the next N target artists not yet searched: slug | name"""
import csv, sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
done = {r["slug"] for r in csv.DictReader(open("data/ig_search_results.csv"))}
k = 0
for r in csv.DictReader(open("data/ig_search_targets.csv")):
    if r["slug"] in done: continue
    print(r["slug"], "|", r["name"], "|", r["nationality"][:25]); k += 1
    if k >= n: break
print("restanti:", sum(1 for r in csv.DictReader(open("data/ig_search_targets.csv")) if r["slug"] not in done))

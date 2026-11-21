"""Convert artists.jsonl to a de-duplicated CSV. Usage: python3 to_csv.py in.jsonl out.csv"""
import csv
import json
import sys

src, dst = sys.argv[1], sys.argv[2]
seen = set()
fields = ["name", "slug", "nationality", "birthday", "deathday", "profile_url"]
with open(src, encoding="utf-8") as f, open(dst, "w", newline="", encoding="utf-8") as out:
    w = csv.DictWriter(out, fieldnames=fields)
    w.writeheader()
    for line in f:
        a = json.loads(line)
        if a["slug"] in seen:
            continue
        seen.add(a["slug"])
        w.writerow({k: a.get(k, "") for k in fields})
print(f"{len(seen):,} unique artists -> {dst}")

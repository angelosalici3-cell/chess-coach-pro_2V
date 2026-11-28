"""Merge per-occupation Wikidata CSVs (files named <QID>:<role>.csv) into one experts list.

Usage: python3 merge_experts.py <dir with csvs> <out.csv>
Keeps living people (query already excludes a death date) born >= 1925 or with unknown birth year.
"""
import collections
import csv
import glob
import os
import sys

src, out = sys.argv[1], sys.argv[2]
people = {}
for f in sorted(glob.glob(os.path.join(src, "*.csv"))):
    role = os.path.basename(f).split(":")[1][:-4]
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if not r.get("p", "").startswith("http"):
            continue
        qid = r["p"].rsplit("/", 1)[-1]
        if r["pLabel"] == qid:
            continue
        p = people.setdefault(qid, {"name": r["pLabel"], "roles": set(), "countries": set(), "birth": "", "ig": set()})
        p["roles"].add(role)
        if r.get("countryLabel"):
            p["countries"].add(r["countryLabel"])
        b = r.get("birth") or ""
        if b[:4].isdigit():
            p["birth"] = b[:4]
        if r.get("ig"):
            p["ig"].add(r["ig"].strip().lstrip("@"))

rows = {q: p for q, p in people.items() if not p["birth"] or int(p["birth"]) >= 1925}
print(f"{len(rows):,} experts; roles:", dict(collections.Counter(r for p in rows.values() for r in p["roles"])))
print(f"with instagram: {sum(1 for p in rows.values() if p['ig']):,}")
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["wikidata_id", "name", "roles", "countries", "birth_year", "instagram", "wikidata_url"])
    for q, p in sorted(rows.items(), key=lambda kv: kv[1]["name"]):
        w.writerow([q, p["name"], "; ".join(sorted(p["roles"])), "; ".join(sorted(p["countries"])),
                    p["birth"], "; ".join(sorted(p["ig"])), f"https://www.wikidata.org/wiki/{q}"])

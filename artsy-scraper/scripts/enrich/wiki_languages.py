"""Number of Wikimedia pages (sitelinks: mostly Wikipedia language editions) about each artist.

Usage: python3 wiki_languages.py wd_artsy_wiki.csv matrix.csv out.csv
wd_artsy_wiki.csv: Wikidata items with an Artsy artist ID (P2042), columns p, artsy, title.
Artists without a Wikidata item linked by Artsy ID get no value (unknown, not zero).
"""
import csv
import sys
import time

import requests

src, matrix_csv, out = sys.argv[1:4]
slugs = {r["slug"] for r in csv.DictReader(open(matrix_csv, encoding="utf-8"))}
qid_of = {}
for r in csv.DictReader(open(src, encoding="utf-8")):
    if r["artsy"] in slugs:
        qid_of.setdefault(r["artsy"], r["p"].rsplit("/", 1)[-1])
qids = sorted(set(qid_of.values()))
langs = {}
for i in range(0, len(qids), 100):
    vals = " ".join("wd:" + q for q in qids[i:i + 100])
    q = f"""SELECT ?p ?n WHERE {{ VALUES ?p {{ {vals} }} ?p wikibase:sitelinks ?n }}"""
    for attempt in range(5):
        try:
            r = requests.post("https://query.wikidata.org/sparql", data={"query": q},
                          headers={"Accept": "application/sparql-results+json", "User-Agent": "artsy-research-script/1.0"}, timeout=180)
        except requests.RequestException as e:
            print("  error", repr(e)[:100], flush=True); time.sleep(10 * (attempt + 1)); continue
        if r.status_code == 200:
            break
        print("  HTTP", r.status_code, flush=True)
        time.sleep(10 * (attempt + 1))
    for b in r.json()["results"]["bindings"]:
        langs[b["p"]["value"].rsplit("/", 1)[-1]] = (int(b["n"]["value"]), "")
    time.sleep(1)
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["slug", "wikidata_id", "wikimedia_sitelinks"])
    for slug, q in sorted(qid_of.items()):
        n, l = langs.get(q, (0, ""))
        w.writerow([slug, q, n])
print(f"{len(qid_of):,} artists with Wikidata item; with >=1 Wikipedia: {sum(1 for q in qid_of.values() if langs.get(q, (0,))[0] > 0):,}")

"""Merge everything into one snapshot table per artist, keeping every existing column.

Usage: python3 merge_snapshot.py matrix.csv trends.csv extras.csv wiki_languages.csv out.csv
Adds: trends (growth, quadrant then/now, primary-market prices), galleries, fairs,
career (age, first documented year, years active), Wikimedia sitelinks.
"""
import csv
import datetime as dt
import sys

matrix_csv, trends_csv, extras_csv, langs_csv, out = sys.argv[1:6]
THIS = dt.date.today().year
load = lambda p: {r["slug"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}
rows = list(csv.DictReader(open(matrix_csv, encoding="utf-8")))
tr, ex, la = load(trends_csv), load(extras_csv), load(langs_csv)
TR = [k for k in next(iter(tr.values())).keys() if k not in ("slug", "name")]
EX = [k for k in next(iter(ex.values())).keys() if k != "slug"]
for r in rows:
    t, e, l = tr.get(r["slug"], {}), ex.get(r["slug"], {}), la.get(r["slug"], {})
    for k in TR:
        r[k] = t.get(k, "")
    for k in EX:
        r[k] = e.get(k, "")
    r["wikimedia_sitelinks"] = l.get("wikimedia_sitelinks", "")
    b = (r.get("birthday") or "")[:4]
    alive = not (r.get("deathday") or "").strip()
    r["age"] = THIS - int(b) if b.isdigit() and alive and 1900 < int(b) <= THIS else ""
    years = [int(x) for x in (e.get("first_show_year"), e.get("first_lot_year")) if x and str(x).isdigit()]
    r["first_documented_year"] = min(years) if years else ""
    r["years_documented"] = THIS - min(years) if years else ""
fields = list(rows[0].keys())
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows):,} artists, {len(fields)} columns -> {out}")

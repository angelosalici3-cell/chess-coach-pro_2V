"""Unify the dashboard quadrant: timeline 2026 quadrant where available, Artsy position otherwise; flag borderline (±2 pct pts). Usage: unify_quadrant.py <dir with artist_matrix_v5.csv and timeline_v3.csv>"""
import csv, collections, sys
d = sys.argv[1]
tl = {}
for r in csv.DictReader(open(f"{d}/timeline_v3.csv")):
    if r["quadrant"] and (r["slug"] not in tl or int(r["year"]) > int(tl[r["slug"]]["year"])):
        tl[r["slug"]] = r
Q = {(1,1):"established",(1,0):"insider",(0,1):"hype",(0,0):"emerging"}
INV = {v:k for k,v in Q.items()}
rows = list(csv.DictReader(open(f"{d}/artist_matrix_v5.csv")))
out = []
for r in rows:
    r["quadrant_artsy"] = r["quadrant"]
    t = tl.get(r["slug"])
    if r["quadrant_2026"] and t:
        q = r["quadrant_2026"]; rec, att = float(t["recognition_pct"] or 0), float(t["attention_pct"] or 0)
        r["quadrant_basis"] = "storico"
    else:
        q = r["quadrant"]; rec, att = float(r["expert_pct"] or 0), float(r["followers_pct"] or 0)
        r["quadrant_basis"] = "artsy"
    r["quadrant"] = q
    hi_r, hi_a = INV[q]
    near = []
    if abs(rec - 75) <= 2: near.append(Q[(1-hi_r, hi_a)])
    if abs(att - 75) <= 2: near.append(Q[(hi_r, 1-hi_a)])
    r["quadrant_borderline"] = near[0] if near else ""
    r["recognition_pct_now"] = round(rec, 1); r["attention_pct_now"] = round(att, 1)
    out.append(r)
f = list(rows[0].keys())
w = csv.DictWriter(open(f"{d}/artist_matrix_v6.csv","w",newline=""), fieldnames=f); w.writeheader(); w.writerows(out)
print(collections.Counter(r["quadrant"] for r in out))
print(collections.Counter(r["quadrant_basis"] for r in out))
print("borderline", sum(1 for r in out if r["quadrant_borderline"]))
print("diff vs artsy", sum(r["quadrant"]!=r["quadrant_artsy"] for r in out))
s=[r for r in out if r["slug"]=="sharon-louden"][0]; print({k:s[k] for k in ["quadrant","quadrant_artsy","quadrant_basis","quadrant_borderline","recognition_pct_now","attention_pct_now"]})

"""Build the popularity x expert-recognition matrix.

Usage: python3 build_matrix.py signals.csv instagram.csv out.csv

popularity  = Artsy followers (percentile among the artists in the file)
recognition = expert_score from Artsy insights (museum collections, institutional
              solo/group shows, biennials, reviews in major publications, private
              collections, awards, curator picks), as a percentile
quadrant    = established / hype (popular, little expert backing) /
              insider (expert backing ahead of popularity -> "about to break out") / emerging
"""
import bisect
import csv
import sys

sig_csv, ig_csv, out = sys.argv[1:4]
rows = list(csv.DictReader(open(sig_csv, encoding="utf-8")))
ig = {r["slug"]: r for r in csv.DictReader(open(ig_csv, encoding="utf-8"))}


def pct(values):
    s = sorted(values)
    return lambda v: round(100 * bisect.bisect_right(s, v) / len(s), 1)


fp = pct([int(r["follows"] or 0) for r in rows])
ep = pct([int(r["expert_score"] or 0) for r in rows])
MOMENTUM = ("gaining_followers", "trending_now", "curators_pick_emerging", "artsy_vanguard_year", "recent_career_event")


def count(v):
    return len([x for x in v.split("; ") if x]) if v else 0


out_rows = []
for r in rows:
    f, e = int(r["follows"] or 0), int(r["expert_score"] or 0)
    pf, pe = fp(f), ep(e)
    if pf >= 75 and pe >= 75:
        q = "established"
    elif pf >= 75:
        q = "hype"
    elif pe >= 75:
        q = "insider"
    else:
        q = "emerging"
    g = ig.get(r["slug"], {})
    out_rows.append({
        "name": r["name"], "slug": r["slug"], "nationality": r["nationality"],
        "birthday": r["birthday"], "deathday": r["deathday"],
        "artsy_followers": f, "followers_pct": pf,
        "expert_score": e, "expert_pct": pe, "quadrant": q,
        "momentum_signals": "; ".join(k for k in MOMENTUM if r.get(k)),
        "museum_collections": count(r.get("collected", "")),
        "institutional_solo_shows": count(r.get("solo_show", "")),
        "biennials": count(r.get("biennial", "")),
        "major_reviews": count(r.get("reviewed", "")),
        "private_collections": r.get("private_collections", ""),
        "collected_by": r.get("collected", ""),
        "high_auction_record": r.get("high_auction_record", ""),
        "auction_results": r.get("auction_results", ""),
        "instagram": g.get("instagram", ""), "instagram_url": g.get("instagram_url", ""),
        "instagram_match": g.get("match", ""),
        "profile_url": r["profile_url"],
    })
out_rows.sort(key=lambda x: (-x["expert_score"], -x["artsy_followers"]))
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
    w.writeheader()
    w.writerows(out_rows)
from collections import Counter
print(len(out_rows), Counter(x["quadrant"] for x in out_rows), "instagram:", sum(1 for x in out_rows if x["instagram"]))

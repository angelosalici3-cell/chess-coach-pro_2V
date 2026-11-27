"""Exhibition network: density, partner track record ("fiuto"), out-of-sample test, current signals.

Usage: python3 network_analysis.py network_dir dash_dir out_dir
A "bet" = a venue (partner) shows an artist who, in that year, was emerging or hype (low expert recognition).
A "hit" = that artist is insider or established in a later year. Quadrants: timeline_v4, carried forward,
with the market rule (one lot >= 100k USD: no longer emerging).
"""
import csv, json, os, sys, statistics
from collections import Counter, defaultdict

NET, D, OUT = sys.argv[1:4]
SAMPLE = sys.argv[4] if len(sys.argv) > 4 else f"{NET}/../network_sample.txt"
os.makedirs(OUT, exist_ok=True)
LOW, HIGH = {"emerging", "hype"}, {"insider", "established"}
K = 5  # shrinkage towards the base rate

M = {r["slug"]: r for r in csv.DictReader(open(f"{D}/artist_matrix_v7.csv", encoding="utf-8"))}
qrow = defaultdict(dict)
for r in csv.DictReader(open(f"{D}/timeline_v4.csv", encoding="utf-8")):
    if r["quadrant"]:
        qrow[r["slug"]][int(r["year"])] = r["quadrant"]


def q_at(slug, y):
    d = qrow.get(slug)
    if not d:
        return None
    ys = [k for k in d if k <= y]
    q = d[max(ys)] if ys else "emerging"
    py = (M.get(slug) or {}).get("market_proven_year")
    return "hype" if q == "emerging" and py and y >= int(py) else q


def reached_high(slug, after, until=2026):
    return any(q_at(slug, y) in HIGH for y in range(after + 1, until + 1))


shows = {r["show_slug"]: r for r in csv.DictReader(open(f"{NET}/shows.csv", encoding="utf-8"))}
members = defaultdict(set)
for r in csv.DictReader(open(f"{NET}/show_artists.csv", encoding="utf-8")):
    members[r["show_slug"]].add(r["artist_slug"])
for r in csv.DictReader(open(f"{NET}/artist_shows.csv", encoding="utf-8")):
    members[r["show_slug"]].add(r["artist_slug"])
sample = [x.strip() for x in open(SAMPLE) if x.strip()]
done = set(open(f"{NET}/done.txt").read().split())
sample = [x for x in sample if x in done]

# ---- 1. density for the sample ----
a_shows = defaultdict(list)
for r in csv.DictReader(open(f"{NET}/artist_shows.csv", encoding="utf-8")):
    a_shows[r["artist_slug"]].append(shows.get(r["show_slug"]))
dens = []
for s_ in sample:
    L = [x for x in a_shows.get(s_, []) if x]
    parts = {x["partner_slug"] or x["partner_name"] for x in L if (x["partner_slug"] or x["partner_name"])}
    dated = [x for x in L if x["start"][:4].isdigit()]
    co = set().union(*[members[x["show_slug"]] for x in L]) - {s_} if L else set()
    dens.append({"slug": s_, "quadrant": M[s_]["quadrant"], "shows": len(L), "partners": len(parts),
                 "institution_shows": sum(x["partner_type"] == "Institution" for x in L),
                 "fair_booths": sum(x["fair_booth"] == "1" for x in L), "solo": sum(x["kind"] == "solo" for x in L),
                 "first_year": min((int(x["start"][:4]) for x in dated), default=""), "co_exhibitors": len(co)})
with open(f"{OUT}/network_density.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(dens[0])); w.writeheader(); w.writerows(dens)

# ---- 2a. which venues choose artists (primary galleries, institutions) and which resell or print ----
import re
PRINT_RX = re.compile(r"\b(press|editions?|prints?|printmaking|graphics?|graphic studio|print studio|atelier|tamarind|gemini g\.?e\.?l|ulae|universal limited art editions|two palms|lithograph|serigraph)\b", re.I)
RESALE_RX = re.compile(r"\b(advisory|brokerage|auction|auctions|caviar20|art dealers?|fine art dealers?|collection sale|private sales?|vertu|editions? ltd)\b", re.I)
p_members = defaultdict(set); PNAME = {}
for sh in shows.values():
    PNAME.setdefault(sh["partner_slug"] or ("ext:" + sh["partner_name"]), sh["partner_name"])
    p_members[sh["partner_slug"] or ("ext:" + sh["partner_name"])] |= members[sh["show_slug"]]
ptype = {}
for p, arts in p_members.items():
    nm = PNAME.get(p, "")
    known = [a for a in arts if a in M]
    dead = sum(M[a]["living"] != "1" for a in known) / len(known) if known else 0
    if PRINT_RX.search(nm):
        ptype[p] = "stamperia"
    elif RESALE_RX.search(nm) or (len(known) >= 8 and dead > 0.3):
        ptype[p] = "mercato secondario"
    else:
        ptype[p] = "sceglie"

# ---- 2. bets per partner ----
def bets_for(year_from, year_to, outcome_until):
    """(partner, artist) first low-recognition showing in [year_from, year_to]; hit if high by outcome_until."""
    first = {}
    for sh in shows.values():
        if not sh["start"][:4].isdigit() or sh["fair_booth"] == "1" or sh["kind"] == "fair":
            continue  # fair booths are stock rotation, not curatorial bets
        y = int(sh["start"][:4]); p = sh["partner_slug"] or ("ext:" + sh["partner_name"])
        if not (year_from <= y <= year_to) or p in ("ext:",) or ptype.get(p) != "sceglie":
            continue
        for a in members[sh["show_slug"]]:
            if a not in qrow or q_at(a, y) not in LOW:
                continue
            k = (p, a)
            if k not in first or y < first[k]:
                first[k] = y
    stats = defaultdict(lambda: [0, 0])
    for (p, a), y in first.items():
        stats[p][0] += 1; stats[p][1] += reached_high(a, y, outcome_until)
    return first, stats

pinfo = {}
for sh in shows.values():
    p = sh["partner_slug"] or ("ext:" + sh["partner_name"])
    pinfo.setdefault(p, (sh["partner_name"], sh["partner_type"], sh["city"]))

first, st = bets_for(2015, 2022, 2026)
tot_b = sum(v[0] for v in st.values()); tot_h = sum(v[1] for v in st.values())
base = tot_h / tot_b if tot_b else 0
rows = []
for p, (b, h) in st.items():
    nm, ty, city = pinfo.get(p, ("", "", ""))
    rows.append({"partner": p, "name": nm, "type": ty, "role": ptype.get(p, ""), "city": city, "early_bets": b, "hits": h,
                 "hit_rate": round(h / b, 3), "shrunk_rate": round((h + K * base) / (b + K), 3),
                 "lift": round(((h + K * base) / (b + K)) / base, 2) if base else ""})
rows.sort(key=lambda r: (-r["shrunk_rate"], -r["early_bets"]))
with open(f"{OUT}/partner_track_record.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# ---- 3. out-of-sample test: track record 2015-2018 (outcomes to 2021) -> artists low in 2021, shown 2019-2021 ----
_, st_tr = bets_for(2015, 2018, 2021)
bt = sum(v[0] for v in st_tr.values()); bh = sum(v[1] for v in st_tr.values()); base_tr = bh / bt if bt else 0
good = {p for p, (b, h) in st_tr.items() if b >= 3 and (h + K * base_tr) / (b + K) >= 1.5 * base_tr}
test = defaultdict(lambda: [0, 0])
f2, _ = bets_for(2019, 2021, 2021)
art_good = defaultdict(bool); arts = set()
for (p, a), y in f2.items():
    if q_at(a, 2021) in LOW:
        arts.add(a); art_good[a] |= p in good
for a in arts:
    g = "con fiuto" if art_good[a] else "senza"
    test[g][0] += 1; test[g][1] += reached_high(a, 2021, 2026)
def wilson(h, n, z=1.96):
    if not n:
        return None, None
    p_ = h / n; den = 1 + z * z / n; c = (p_ + z * z / (2 * n)) / den; w = z * ((p_ * (1 - p_) / n + z * z / (4 * n * n)) ** .5) / den
    return round(c - w, 3), round(c + w, 3)
oos = {g: {"artists": n, "reached_high": h, "rate": round(h / n, 3) if n else None, "ci95": wilson(h, n)} for g, (n, h) in test.items()}

# ---- 4. current signals: low-recognition artists now, shown 2023-2026 by high-track-record venues ----
top = {r["partner"] for r in rows if r["early_bets"] >= 5 and r["lift"] != "" and r["lift"] >= 1.5}
sig = defaultdict(set)
for sh in shows.values():
    if not sh["start"][:4].isdigit() or sh["fair_booth"] == "1" or sh["kind"] == "fair":
        continue
    y = int(sh["start"][:4]); p = sh["partner_slug"] or ("ext:" + sh["partner_name"])
    if y >= 2023 and p in top:
        for a in members[sh["show_slug"]]:
            if a in M and M[a]["living"] == "1" and M[a]["quadrant"] in LOW | {"insider"}:
                sig[a].add(p)
srows = []
for a, ps in sig.items():
    r = M[a]
    srows.append({"slug": a, "name": r["name"], "quadrant": r["quadrant"], "age": r["age"], "nationality": r["nationality"],
                  "venues_with_track_record": len(ps), "venues": "; ".join(sorted(pinfo.get(p, (p,))[0] for p in ps))[:300],
                  "score_synthesis": r["score_synthesis"], "median_usd_10y": r["median_usd_10y"], "in_sample": int(a in set(sample))})
srows.sort(key=lambda r: (-r["venues_with_track_record"], -(float(r["score_synthesis"]) if r["score_synthesis"] else 0)))
if srows:
    with open(f"{OUT}/network_signals.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(srows[0])); w.writeheader(); w.writerows(srows)

# ---- summary ----
byq = defaultdict(list)
for d in dens:
    byq[d["quadrant"]].append(d)
summary = {
    "sample_fetched": len(sample), "shows": len(shows), "artists_in_network": len(set().union(*members.values())),
    "artists_in_network_with_timeline": len(set().union(*members.values()) & set(qrow)),
    "partners": len(pinfo),
    "density_by_quadrant": {q: {"artists": len(L), "median_shows": statistics.median([x["shows"] for x in L]),
                                "share_no_shows": round(sum(x["shows"] == 0 for x in L) / len(L), 2),
                                "median_partners": statistics.median([x["partners"] for x in L]),
                                "median_institution_shows": statistics.median([x["institution_shows"] for x in L])} for q, L in byq.items()},
    "bets_2015_2022": tot_b, "base_hit_rate": round(base, 3), "partners_with_5_bets": sum(1 for r in rows if r["early_bets"] >= 5),
    "partners_with_track_record": len(top), "venue_roles": dict(Counter(ptype.values())), "out_of_sample": oos, "good_partners_2015_2018": len(good),
    "current_signal_artists": len(srows),
}
json.dump(summary, open(f"{OUT}/network_summary.json", "w"), indent=1)
print(json.dumps(summary, indent=1))

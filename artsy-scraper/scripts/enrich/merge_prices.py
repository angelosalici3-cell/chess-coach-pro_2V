"""Add auction prices to the artist matrix and measure price vs interest correlation.

Usage: python3 merge_prices.py matrix.csv prices.csv out_matrix.csv out_correlations.csv

Adds to every row (existing columns are kept):
  lots_considered, lots_sold, sell_through_pct, mean_price_usd, median_price_usd,
  max_price_usd, last_sale_date, price_pct, interest_pct, value_gap
interest_pct = mean of followers_pct and expert_pct (digital + expert interest)
price_pct    = percentile of median_price_usd among artists with >= MIN_SOLD sold lots
value_gap    = interest_pct - price_pct  (>0: interest ahead of price, possibly undervalued)

Correlations are Spearman rank correlations, overall and per quadrant.
"""
import bisect
import csv
import math
import sys

MIN_SOLD = 5
matrix_csv, prices_csv, out_csv, corr_csv = sys.argv[1:5]
rows = list(csv.DictReader(open(matrix_csv, encoding="utf-8")))
prices = {r["slug"]: r for r in csv.DictReader(open(prices_csv, encoding="utf-8"))}
PRICE_COLS = ["lots_considered", "lots_sold", "sell_through_pct", "mean_price_usd",
              "median_price_usd", "max_price_usd", "last_sale_date"]

priced = []
for r in rows:
    p = prices.get(r["slug"], {})
    for c in PRICE_COLS:
        r[c] = p.get(c, "")
    if r["median_price_usd"] and int(r["lots_sold"] or 0) >= MIN_SOLD:
        priced.append(r)

sorted_prices = sorted(float(r["median_price_usd"]) for r in priced)
for r in rows:
    r["interest_pct"] = round((float(r["followers_pct"]) + float(r["expert_pct"])) / 2, 1)
    if r in priced:
        r["price_pct"] = round(100 * bisect.bisect_right(sorted_prices, float(r["median_price_usd"])) / len(sorted_prices), 1)
        r["value_gap"] = round(r["interest_pct"] - r["price_pct"], 1)
    else:
        r["price_pct"] = r["value_gap"] = ""

fields = list(rows[0].keys())
with open(out_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(cov / (sx * sy), 3) if sx and sy else ""


groups = [("all", priced)] + [(q, [r for r in priced if r["quadrant"] == q]) for q in ("insider", "established", "hype", "emerging")]
with open(corr_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["group", "artists", "rho_price_followers", "rho_price_expert", "rho_price_interest", "median_price_usd"])
    for name, g in groups:
        if len(g) < 30:
            continue
        price = [float(r["median_price_usd"]) for r in g]
        w.writerow([name, len(g),
                    spearman(price, [float(r["artsy_followers"]) for r in g]),
                    spearman(price, [float(r["expert_score"]) for r in g]),
                    spearman(price, [float(r["interest_pct"]) for r in g]),
                    round(sorted(price)[len(price) // 2])])
print(f"{len(priced):,} artists with >= {MIN_SOLD} sold lots")
print(open(corr_csv).read())

"""Exhibition network from Artsy's public GraphQL endpoint.

Usage: python3 shows_network.py slugs.txt out_dir [--batch 3] [--delay 0.3]
Writes (append/resume) in out_dir:
  shows.csv        one row per show: show_slug, name, start, end, kind, fair_booth, partner_slug, partner_name, partner_type, city, country, n_artists
  artist_shows.csv artist_slug, show_slug  (up to 100 most recent shows per artist)
  show_artists.csv show_slug, artist_slug  (up to 40 artists listed per show: co-exhibitors)
  done.txt         artists already fetched
"""
import argparse, csv, os, time
import requests

GQL = "https://metaphysics-production.artsy.net/v2"
s = requests.Session()
s.headers.update({"Content-Type": "application/json", "User-Agent": "artsy-research-script/1.0"})
Q = """query($s:[String]!,$n:Int!){ artists(slugs:$s, size:$n){ slug
 showsConnection(first:100, sort: START_AT_DESC){ edges{ node{ slug name startAt endAt kind isFairBooth
   partner{ __typename ... on Partner{ slug name type } ... on ExternalPartner{ name } }
   location{ city country } artistsConnection(first:40){ totalCount edges{ node{ slug } } } } } } } }"""


def gql(v):
    for attempt in range(7):
        try:
            r = s.post(GQL, json={"query": Q, "variables": v}, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}")
            d = r.json()
            if d.get("data") is None:
                raise requests.HTTPError(str(d.get("errors"))[:300])
            return d["data"]["artists"] or []
        except (requests.RequestException, ValueError) as e:
            print(f"  retry in {2 ** attempt}s: {e!r}"[:300], flush=True)
            time.sleep(2 ** attempt)
    raise RuntimeError("too many failures")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs"); ap.add_argument("outdir")
    ap.add_argument("--batch", type=int, default=3); ap.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    P = lambda f: os.path.join(a.outdir, f)
    done = set(open(P("done.txt")).read().split()) if os.path.exists(P("done.txt")) else set()
    seen = {r["show_slug"] for r in csv.DictReader(open(P("shows.csv")))} if os.path.exists(P("shows.csv")) else set()
    slugs = [x.strip() for x in open(a.slugs) if x.strip() and x.strip() not in done]
    def writer(name, header):
        new = not os.path.exists(P(name)); fh = open(P(name), "a", newline="", encoding="utf-8"); w = csv.writer(fh)
        if new: w.writerow(header)
        return fh, w
    fs, ws = writer("shows.csv", ["show_slug", "name", "start", "end", "kind", "fair_booth", "partner_slug", "partner_name", "partner_type", "city", "country", "n_artists"])
    fa, wa = writer("artist_shows.csv", ["artist_slug", "show_slug"])
    fc, wc = writer("show_artists.csv", ["show_slug", "artist_slug"])
    fd = open(P("done.txt"), "a")
    print(f"{len(slugs)} artists to fetch", flush=True)
    for i in range(0, len(slugs), a.batch):
        chunk = slugs[i:i + a.batch]
        for art in gql({"s": chunk, "n": len(chunk)}):
            if not art:
                continue
            for e in ((art.get("showsConnection") or {}).get("edges") or []):
                n = (e or {}).get("node") or {}
                if not n.get("slug"):
                    continue
                wa.writerow([art["slug"], n["slug"]])
                if n["slug"] in seen:
                    continue
                seen.add(n["slug"])
                p, loc, ac = n.get("partner") or {}, n.get("location") or {}, n.get("artistsConnection") or {}
                ws.writerow([n["slug"], (n.get("name") or "")[:150], (n.get("startAt") or "")[:10], (n.get("endAt") or "")[:10],
                             n.get("kind") or "", int(bool(n.get("isFairBooth"))), p.get("slug") or "", p.get("name") or "",
                             p.get("type") or p.get("__typename") or "", loc.get("city") or "", loc.get("country") or "", ac.get("totalCount") or ""])
                for c in ac.get("edges") or []:
                    if (c or {}).get("node"):
                        wc.writerow([n["slug"], c["node"]["slug"]])
        for x in chunk:
            fd.write(x + "\n")
        for f in (fs, fa, fc, fd):
            f.flush()
        if (i // a.batch) % 20 == 0:
            print(f"  {i + len(chunk)}/{len(slugs)}", flush=True)
        time.sleep(a.delay)
    print("done", flush=True)


if __name__ == "__main__":
    main()

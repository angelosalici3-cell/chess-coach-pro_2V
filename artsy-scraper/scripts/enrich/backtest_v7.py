import csv,collections,statistics as st,sys
D='/tmp/claude-0/-home-user-chess-coach-pro-2V/991ae462-e864-5948-9204-9d15918eec88/scratchpad/dash'
m={r['slug']:r for r in csv.DictReader(open(D+'/artist_matrix_v7.csv'))}
tl=collections.defaultdict(dict)
for r in csv.DictReader(open(D+'/timeline_v4.csv')): tl[r['slug']][int(r['year'])]=r
def q(s,Y):
    d=tl.get(s,{}); ys=[y for y in d if y<=Y and d[y]['quadrant']]; return d[max(ys)]['quadrant'] if ys else 'emerging'
# per lot from lots_radar (last 10y, max 40/artist) -> use adj for P/C with area
BETA=0.689
lots=collections.defaultdict(list)
for r in csv.DictReader(open(D+'/lots_radar.csv')):
    y=int(r['d'][:4]); usd=float(r['usd'])
    adj=usd*(10000/float(r['a']))**BETA if r['a'] and r['c'] in 'PC' else None
    lots[r['slug']].append((y,usd,adj,r['c']))
def run(kind):
    res=collections.defaultdict(list)
    for s,L in lots.items():
        if m.get(s,{}).get('living')!='1': continue
        if kind=='adj':
            a=[x[2] for x in L if 2017<=x[0]<=2019 and x[2]]; b=[x[2] for x in L if 2024<=x[0]<=2026 and x[2]]
        else:
            a=[x[1] for x in L if 2017<=x[0]<=2019 and x[3]!='M']; b=[x[1] for x in L if 2024<=x[0]<=2026 and x[3]!='M']
        if len(a)>=2 and len(b)>=2: res[q(s,2019)].append(st.median(b)/st.median(a))
    tot=sum(len(v) for v in res.values()); print(kind,tot)
    for k in ['emerging','insider','established','hype']:
        v=res[k]; print(' ',k,len(v),round(st.median(v),2),round(100*sum(x>=2 for x in v)/len(v)))
run('adj'); run('unique')
for s in ['alicja-kwade','ahmed-mater','jade-fadojutimi']:
    print(s,[(y,r['quadrant'][:2],r['median_unique_usd'],r['median_adj_usd'],r['lots_sold'],r['price_to_estimate']) for y,r in sorted(tl[s].items())])
print('--- timeline medians')
for key in ('median_adj_usd','median_unique_usd'):
  for only_living in (True,False):
    res=collections.defaultdict(list)
    for s,d in tl.items():
        if only_living and m.get(s,{}).get('living')!='1': continue
        a=[float(d[y][key]) for y in (2017,2018,2019) if y in d and d[y][key]]
        b=[float(d[y][key]) for y in (2024,2025,2026) if y in d and d[y][key]]
        if a and b: res[q(s,2019)].append(st.median(b)/st.median(a))
    print(key,'living' if only_living else 'all',sum(len(v) for v in res.values()))
    for k in ['emerging','insider','established','hype']:
        v=res[k]; print(' ',k,len(v),round(st.median(v),2),round(100*sum(x>=2 for x in v)/len(v)))

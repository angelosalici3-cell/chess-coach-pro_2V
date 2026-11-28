import csv,math,statistics as st,random
D='dash'
M=list(csv.DictReader(open(D+'/artist_matrix_v7.csv')))
COL={'insider':'#9A5F1C','established':'#14302B','hype':'#2F5F86','emerging':'#9AA19C'}
# ---- pricemap (size-adjusted)
P=[r for r in M if r['price_1m2_usd']]
med=st.median(float(r['price_1m2_usd']) for r in P)
Y=lambda p:600-116*(math.log10(max(100,min(1e7,p)))-2)
X=lambda i:60+9.6*i
o=['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="640" viewBox="0 0 1040 640"><rect x="60" y="20" width="960" height="580" fill="#FBFAF6"/>']
for y in (600,484,368,252,136,20): o.append(f'<line x1="60" y1="{y}" x2="1020" y2="{y}" stroke="#E4E0D3" stroke-width="1"/>')
for x in (300,540,780): o.append(f'<line x1="{x}" y1="20" x2="{x}" y2="600" stroke="#E4E0D3" stroke-width="1"/>')
zy=round(Y(med),1)
o.append(f'<rect x="732" y="{zy}" width="288" height="{round(600-zy,1)}" fill="#9A5F1C" fill-opacity="0.12" stroke="#9A5F1C" stroke-width="2" stroke-dasharray="6 5"/>')
for q in ('emerging','hype','established','insider'):
    o.append(f'<g fill="{COL[q]}" fill-opacity="0.55">'+''.join(f'<circle cx="{X(float(r["interest_pct"])):.0f}" cy="{Y(float(r["price_1m2_usd"])):.0f}" r="3.2"/>' for r in P if r['quadrant']==q)+'</g>')
o.append('<line x1="60" y1="600" x2="1020" y2="600" stroke="#4E5A55" stroke-width="2"/><line x1="60" y1="20" x2="60" y2="600" stroke="#4E5A55" stroke-width="2"/></svg>')
open('charts/pricemap_v7.svg','w').write(''.join(o))
print('pricemap',len(P),med,zy)
# ---- sankey
T={(r['from_quadrant'],r['to_quadrant']):int(r['artists']) for r in csv.DictReader(open(D+'/quadrant_transitions_v4.csv'))}
Q=['insider','established','hype','emerging']
tot=sum(T.values()); k=(620-72)/tot
L={a:sum(T.get((a,b),0) for b in Q) for a in Q}; R={b:sum(T.get((a,b),0) for a in Q) for b in Q}
def tops(n):
    y=0; t={}
    for q in Q: t[q]=y; y+=n[q]*k+24
    return t
lt,rt=tops(L),tops(R)
lc=dict(lt); rc=dict(rt); paths=[]
for a in Q:
    for b in Q:
        v=T.get((a,b),0)
        if not v: continue
        h=v*k; y0=lc[a]; y1=rc[b]; lc[a]+=h; rc[b]+=h
        op=0.22 if a==b else 0.55
        paths.append(f'<path d="M36 {y0:.1f} C500.0 {y0:.1f} 500.0 {y1:.1f} 964 {y1:.1f} L964 {y1+h:.1f} C500.0 {y1+h:.1f} 500.0 {y0+h:.1f} 36 {y0+h:.1f} Z" fill="{COL[b]}" fill-opacity="{op}"/>')
rects=[]
for q in Q:
    rects.append(f'<rect x="0" y="{lt[q]:.1f}" width="36" height="{L[q]*k:.1f}" fill="{COL[q]}"/><rect x="964" y="{rt[q]:.1f}" width="36" height="{R[q]*k:.1f}" fill="{COL[q]}"/>')
open('charts/sankey_v7.svg','w').write('<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="620" viewBox="0 0 1000 620">'+''.join(paths+rects)+'</svg>')
for q in Q: print(q,'L',L[q],round(17+0.8*(lt[q]+L[q]*k/2)),'R',R[q],round(17+0.8*(rt[q]+R[q]*k/2)))
print(tot)

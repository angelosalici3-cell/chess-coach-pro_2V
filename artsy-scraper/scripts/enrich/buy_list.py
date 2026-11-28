"""Shortlist: non-established living artists whose unique works sell at auction under 5,000 EUR.
Usage: python3 buy_list.py dash_dir out.csv"""
import csv, statistics, sys, collections
D, OUT = sys.argv[1:3]
rates = [float(r['usd']) / float(r['orig']) for r in csv.DictReader(open(D + '/lots_radar.csv'))
         if r['cur'] == 'EUR' and r['d'][:4] in ('2025', '2026') and r['orig']]
EUR = statistics.median(rates); CAP = 5000 * EUR
L = collections.defaultdict(list)
for r in csv.DictReader(open(D + '/lots_radar.csv')):
    L[r['slug']].append(r)
num = lambda x: float(x) if x not in ('', None) else None
rows = []
for r in csv.DictReader(open(D + '/artist_matrix_v7.csv')):
    if r['eligible_synthesis'] != '1' or r['quadrant'] == 'established':
        continue
    uniq = [x for x in L.get(r['slug'], []) if x['d'][:4] >= '2023' and x['c'] in 'PCS']  # unique: painting, paper, sculpture
    under = [x for x in uniq if float(x['usd']) <= CAP]
    st, pe, age = num(r['sell_through_10y']), num(r['price_to_estimate_last3y']), num(r['age'])
    ok = (len(under) >= 2 and len(under) / len(uniq) >= 0.3 and (st or 0) >= 70 and (pe or 0) >= 0.9
          and age is not None and age <= 60)
    if not ok:
        continue
    rows.append({'slug': r['slug'], 'name': r['name'], 'nationality': r['nationality'], 'age': int(age), 'quadrant': r['quadrant'],
                 'score_synthesis': r['score_synthesis'], 'score_parts': r['score_parts'],
                 'unique_sold_3y': len(uniq), 'unique_under_5k_eur': len(under),
                 'median_under_5k_eur': round(statistics.median(float(x['usd']) for x in under) / EUR),
                 'price_1m2_eur': round(float(r['price_1m2_usd']) / EUR) if r['price_1m2_usd'] else '',
                 'sell_through_10y': r['sell_through_10y'], 'price_to_estimate_last3y': r['price_to_estimate_last3y'],
                 'museum_collections': r['museum_collections'], 'biennials': r['biennials'], 'top_galleries': r['top_galleries'],
                 'momentum_signals': r['momentum_signals'], 'ig_followers': r['ig_followers'], 'instagram': r['ig_handle'] or r['instagram'],
                 'adj_growth_pct_per_year': r['adj_growth_pct_per_year']})
PICKS = {  # editorial choice on top of the filters: tier, reason (numbers from the matrix and the lots)
    'mark-manders': ('Riconoscimento forte', "8 collezioni museali e 7 biennali, Tanya Bonakdar e Xavier Hufkens; si vende il 90% dei lotti, a 1,5 volte la stima. Sotto 5.000 € passano soprattutto opere su carta."),
    'klara-liden': ('Riconoscimento forte', "6 collezioni museali e 7 biennali, Sadie Coles HQ; prezzo 1,65 volte la stima. Metà delle opere uniche vendute negli ultimi 3 anni è sotto 5.000 €."),
    'martin-boyce': ('Riconoscimento forte', "Esther Schipper, Eva Presenhuber e Tanya Bonakdar; si vende il 93% dei lotti. Tutte e tre le opere uniche degli ultimi 3 anni sotto 5.000 €."),
    'neil-beloufa': ('Riconoscimento forte', "41 anni, 6 biennali, Mendes Wood DM; si vende l'89% dei lotti, sopra la stima."),
    'michael-e-smith': ('Riconoscimento forte', "3 collezioni museali e 3 biennali; ogni lotto offerto è stato venduto, a 1,2 volte la stima."),
    'chris-johanson': ('Accessibile e liquido', "7 opere uniche su 9 vendute sotto 5.000 € negli ultimi 3 anni, a circa 1.050 €; si vende il 90% dei lotti, a 1,5 volte la stima."),
    'sam-falls': ('Accessibile e liquido', "42 anni, Galerie Eva Presenhuber, 3 collezioni museali; le opere sotto 5.000 € passano intorno a 1.500 €."),
    'jose-davila': ('Accessibile e liquido', "Sean Kelly; si vende il 91% dei lotti, sopra la stima. Sotto 5.000 € solo opere piccole, vicine alla soglia (circa 4.550 €)."),
    'sophie-von-hellermann': ('Slancio di prezzo', "Emergente; prezzi a parità di dimensioni in crescita dell'11% l'anno, si vende il 92% dei lotti a 1,3 volte la stima."),
    'serban-savu': ('Slancio di prezzo', "Emergente; prezzi a 1 m² in crescita del 44% l'anno, 1,4 volte la stima. Sotto 5.000 € solo opere piccole (circa 4.700 €): la finestra si sta chiudendo."),
}
for x in rows:
    x['pick_tier'], x['pick_reason'] = PICKS.get(x['slug'], ('', ''))
missing = set(PICKS) - {x['slug'] for x in rows}
assert not missing, missing
TIERS = ['Riconoscimento forte', 'Accessibile e liquido', 'Slancio di prezzo', '']
rows.sort(key=lambda x: (TIERS.index(x['pick_tier']), -float(x['score_synthesis'])))
for i, x in enumerate(rows, 1):
    x['rank'] = i
w = csv.DictWriter(open(OUT, 'w', newline=''), fieldnames=['rank'] + [k for k in rows[0] if k != 'rank']); w.writeheader(); w.writerows(rows)
print('EUR', round(EUR, 3), 'cap USD', round(CAP), 'artists', len(rows))

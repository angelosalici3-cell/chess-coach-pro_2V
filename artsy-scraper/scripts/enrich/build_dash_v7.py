"""Turn index.html (v6 radar) into the v7 radar: three parts, lot-level chart, social, synthesis, coherence."""
import json, re, sys
D = sys.argv[1]
src = open(f"{D}/index.html", encoding="utf-8").read()
summ = json.load(open(f"{D}/radar_summary.json"))
MATRIX = f"{D}/artist_matrix_v7.csv"
BETA = summ["beta_size_elasticity"]
h = src

def rep(old, new, count=1):
    global h
    assert h.count(old) >= 1, old[:80]
    h = h.replace(old, new, count)

# ---------- CSS ----------
rep("  .tr-linkbtn:focus-visible", """  .tr-part { border-top: 2px solid var(--color-border-line); padding-top: var(--cds-pad-lg); display: flex; flex-direction: column; gap: var(--cds-gap-sm); }
  .tr-part h2 { font-family: var(--font-anthropic-serif); font-weight: 400; font-size: calc(var(--cds-font-size-title) * 0.8); }
  .tr-nav { display: flex; flex-wrap: wrap; gap: var(--cds-gap-md); font-size: var(--cds-font-size-caption); }
  .tr-nav a { color: inherit; }
  .tr-lotchart { min-height: 280px; }
  .tr-lotchart svg text { fill: var(--cds-text-secondary); font-size: 10px; }
  .tr-svgchart { position: relative; width: 100%; }
  .tr-svgchart svg text { fill: var(--cds-text-secondary); font-size: var(--cds-font-size-caption); }
  .tr-score { display: inline-block; min-width: 2.6em; text-align: right; font-weight: var(--cds-font-weight-medium); }
  .tr-linkbtn:focus-visible""")

# ---------- intro: reading guide ----------
rep("""  </header>""", """    <p class="tr-lede" lang="it">Il radar si legge in tre parti. <b>1 · Valore artistico</b>: quanto gli esperti e le istituzioni riconoscono l'artista, come è cambiato nel tempo e se le regole che usiamo restano coerenti. <b>2 · Social e grande pubblico</b>: quanto l'artista è noto fuori dal giro degli addetti ai lavori (Instagram, follower su Artsy) e come questo si confronta con i prezzi, a parità di dimensioni dell'opera. <b>3 · Sintesi</b>: un punteggio che mette insieme tutto e indica gli artisti più interessanti.</p>
    <nav class="tr-nav" aria-label="Parti del radar"><a href="#part-1">1 · Valore artistico e punteggi</a><a href="#part-2">2 · Social e prezzo contro notorietà</a><a href="#part-3">3 · Sintesi</a><a href="#method">Metodo</a></nav>
  </header>""")

# ---------- extract and reorder sections ----------
def cut(sid):
    global h
    m = re.search(r'\n  <section class="tr-section" id="%s">.*?\n  </section>\n' % sid, h, re.S)
    assert m, sid
    h = h[:m.start()] + "\n" + h[m.end():]
    return m.group(0)
sec = {k: cut(k) for k in ["matrix", "ranking", "experts", "prices", "timeline-view"]}

# timeline: add lot-level chart, drop old median-price mini
sec["timeline-view"] = sec["timeline-view"].replace(
    """      <div class="tr-multiples" data-draw="t-charts" data-source="timeline"></div>""",
    """      <div class="tr-section">
        <span class="tr-label">Opere vendute all'asta, una per una (ultimi 10 anni)</span>
        <div class="tr-svgchart tr-lotchart" data-draw="t-lots" data-source="lots"></div>
        <span class="tr-muted" lang="it">Ogni punto è un'opera venduta, non più la somma dell'anno. Grandezza del punto: superficie dell'opera. Colore: tipo di opera. La linea segue il prezzo mediano dell'anno riportato a un dipinto o un'opera su carta di 1 m², così un anno con tele più grandi non sembra un aumento di prezzo. Prezzi in USD; nel dettaglio di ogni punto trovi la valuta e l'importo originali.</span>
      </div>
      <div class="tr-multiples" data-draw="t-charts" data-source="timeline"></div>""")
sec["timeline-view"] = sec["timeline-view"].replace(
    """<th class="tr-n" data-field="price_growth_pct_per_year">Crescita prezzi % annua</th>""",
    """<th class="tr-n" data-field="adj_growth_pct_per_year">Crescita prezzi % annua, a parità di dimensioni</th>""")
sec["timeline-view"] = sec["timeline-view"].replace("<option value=\"price\">Crescita annua dei prezzi d'asta</option>", "<option value=\"price\">Crescita annua dei prezzi d'asta, a parità di dimensioni</option>")

# prices: size-adjusted
sec["prices"] = sec["prices"].replace("<h2>Prezzo d'asta contro interesse</h2>", "<h2>Prezzo d'asta contro interesse degli esperti e di Artsy, a parità di dimensioni</h2>")
sec["prices"] = re.sub(r'<p lang="it" data-read>Tra i <b data-draw="p-n".*?</p>',
    """<p lang="it" data-read>Tra i <b data-draw="p-n" data-source="correlations" data-field="artists" data-where="group=all">—</b> artisti con almeno 3 dipinti o opere su carta di dimensioni note venduti negli ultimi 10 anni, il prezzo riportato a 1 m² segue poco l'interesse: la correlazione con il punteggio degli esperti è <b data-draw="p-rho-e2" data-source="correlations" data-field="rho_price_expert" data-where="group=all">—</b>, con i follower su Artsy <b data-draw="p-rho-f2" data-source="correlations" data-field="rho_price_followers" data-where="group=all">—</b>. Confrontare prezzi senza tener conto delle dimensioni premia chi vende tele grandi: per questo qui il prezzo di ogni opera è riportato a quello di un'opera di 1 m².</p>""", sec["prices"], flags=re.S)
sec["prices"] = sec["prices"].replace("""<span class="tr-label">Prezzo mediano tipico</span>""", """<span class="tr-label">Prezzo tipico di 1 m²</span>""")
sec["prices"] = re.sub(r'<thead><tr>\s*<th data-field="name">Artista</th>\s*<th class="tr-n" data-field="median_price_usd">Prezzo mediano \(USD\)</th>.*?</tr></thead>',
    """<thead><tr>
          <th data-field="name">Artista</th>
          <th class="tr-n" data-field="price_1m2_usd">Prezzo a 1 m² (USD)</th>
          <th class="tr-n" data-field="median_usd_10y">Prezzo mediano, 10 anni (USD)</th>
          <th class="tr-n" data-field="max_lot_usd">Opera più cara (USD)</th>
          <th class="tr-n" data-field="lots_sold_10y">Lotti venduti, 10 anni</th>
          <th class="tr-n" data-field="sell_through_pct">% venduti</th>
          <th class="tr-n" data-field="interest_pct">Interesse (pct)</th>
          <th class="tr-n" data-field="price_adj_pct">Prezzo a 1 m² (pct)</th>
          <th class="tr-n" data-field="interest_vs_price_gap_adj">Scarto</th>
          <th data-field="quadrant">Quadrante</th>
        </tr></thead>""", sec["prices"], flags=re.S)
sec["prices"] = re.sub(r'<p class="tr-note" lang="it">Il prezzo mediano include stampe.*?</p>',
    """<p class="tr-note" lang="it">Il prezzo a 1 m² usa solo dipinti e opere su carta con dimensioni note: stampe, fotografie in edizione e sculture restano fuori perché il prezzo non dipende dalla superficie allo stesso modo. Per gli scultori guarda l'opera più cara e i singoli lotti nel profilo.</p>""", sec["prices"], flags=re.S)
sec["prices"] = sec["prices"].replace("Asse verticale: prezzo d'asta mediano in USD, scala logaritmica.", "Asse verticale: prezzo d'asta mediano riportato a un'opera di 1 m², in USD, scala logaritmica.")

PART1 = """
  <div class="tr-part" id="part-1">
    <span class="tr-label">Parte 1</span>
    <h2>Valore artistico e punteggi</h2>
    <p lang="it">Quanto gli addetti ai lavori riconoscono l'artista (musei, mostre in istituzioni, biennali, critica) contro quanta attenzione riceve, oggi e anno per anno dal 2015. In fondo alla parte, la verifica che le regole del radar restino coerenti nel tempo.</p>
  </div>
"""
COHERENCE = """
  <section class="tr-section" id="coherence">
    <h2>Verifica di coerenza delle regole</h2>
    <p lang="it">Abbiamo riletto la serie anno per anno cercando i casi in cui le regole danno risultati che non tornano. Ecco cosa è emerso e cosa abbiamo cambiato.</p>
    <div class="tr-tablewrap">
      <table class="tr-table">
        <thead><tr><th>Controllo</th><th class="tr-n">Casi</th><th>Cosa significa e cosa abbiamo fatto</th></tr></thead>
        <tbody data-draw="audit-rows" data-source="audit"></tbody>
      </table>
    </div>
  </section>
"""
PART2 = """
  <div class="tr-part" id="part-2">
    <span class="tr-label">Parte 2</span>
    <h2>Social e grande pubblico: prezzo contro notorietà</h2>
    <p lang="it">Gli esperti arrivano prima, ma i prezzi li fanno i collezionisti e i collezionisti seguono anche la notorietà presso il pubblico. Qui guardiamo quanto ogni artista è conosciuto fuori dal giro (follower Instagram e follower su Artsy) e se il prezzo, a parità di dimensioni, è già allineato a questa notorietà.</p>
  </div>
"""
SOCIAL = """
  <section class="tr-section" id="social">
    <h2>Notorietà presso il pubblico</h2>
    <p lang="it" data-read>Abbiamo cercato l'account Instagram di 2.527 artisti insider ed emergenti in vita che non ne avevano uno collegato. Con quelli già noti da Wikidata, oggi <b data-draw="s-ig" data-source="pipeline" data-field="instagram_in_matrix" data-row="0">—</b> artisti della matrice hanno un account Instagram, e <b data-draw="s-ig-f" data-source="pipeline" data-field="instagram_with_followers" data-row="0">—</b> hanno un numero di follower letto dalla pagina pubblica. Tra chi ha sia follower Instagram sia prezzi a 1 m², la correlazione tra le due cose è <b data-draw="s-rho-ig" data-source="correlations" data-field="rho_price_instagram" data-where="group=all">—</b>.</p>
    <div class="tr-grid2">
      <div class="tr-panel">
        <h2>Follower Instagram contro prezzo a 1 m²</h2>
        <div class="tr-svgchart" data-draw="ig-scatter" data-source="matrix"></div>
        <p class="tr-muted" lang="it">Ogni punto è un artista con account Instagram, follower noti e prezzi d'asta a 1 m². Scale logaritmiche. In basso a destra: molto seguiti dal pubblico, prezzi ancora bassi. I filtri della parte 1 valgono anche qui.</p>
      </div>
      <div class="tr-panel">
        <h2>Follower Instagram tipici per quadrante</h2>
        <div class="tr-bars" data-draw="ig-quad-bars" data-source="ig_by_quad"></div>
        <p class="tr-muted" lang="it">Mediana dei follower tra gli artisti di ogni quadrante con un account trovato. Un insider con molti follower è già noto al pubblico: il riconoscimento degli esperti e quello del pubblico vanno nella stessa direzione.</p>
      </div>
    </div>
    <div class="tr-controls">
      <select class="dash-select" id="f-pub" aria-label="Ordina scarto pubblico">
        <option value="under">Pubblico molto avanti al prezzo (notorietà non ancora pagata)</option>
        <option value="over">Prezzo molto avanti al pubblico</option>
      </select>
      <span class="tr-muted" data-draw="pub-count">—</span>
    </div>
    <div class="tr-tablewrap">
      <table class="tr-table" data-source="matrix" data-row-key="slug">
        <thead><tr>
          <th data-field="name">Artista</th>
          <th data-field="instagram">Instagram</th>
          <th class="tr-n" data-field="ig_followers">Follower Instagram</th>
          <th class="tr-n" data-field="artsy_followers">Follower Artsy</th>
          <th class="tr-n" data-field="public_pct">Notorietà pubblica (pct)</th>
          <th class="tr-n" data-field="price_1m2_usd">Prezzo a 1 m² (USD)</th>
          <th class="tr-n" data-field="price_adj_pct">Prezzo (pct)</th>
          <th class="tr-n" data-field="public_vs_price_gap">Scarto</th>
          <th data-field="quadrant">Quadrante</th>
        </tr></thead>
        <tbody data-draw="pub-rows"></tbody>
      </table>
    </div>
    <p class="tr-note" lang="it">I follower Instagram vengono dal testo pubblico dei risultati di ricerca, quindi sono arrotondati (per esempio «24K») e a volte vecchi di qualche mese. Contano solo gli account trovati con affidabilità alta o media. Notorietà pubblica = media dei percentili di follower Instagram e follower su Artsy; per chi non ha Instagram vale solo Artsy.</p>
  </section>
"""
PART3 = """
  <div class="tr-part" id="part-3">
    <span class="tr-label">Parte 3</span>
    <h2>Sintesi: gli artisti più interessanti</h2>
    <p lang="it">Un punteggio da 0 a 100 per gli artisti in vita con almeno 3 opere vendute all'asta negli ultimi 10 anni. Pesa cinque cose: <b>riconoscimento degli esperti</b> 35%, <b>slancio</b> 20% (mostre importanti in aumento, crescita dei prezzi a parità di dimensioni, visualizzazioni Wikipedia, salita di quadrante), <b>notorietà pubblica</b> 15%, <b>valore</b> 20% (quanto l'interesse supera il prezzo a 1 m²) e <b>solidità del mercato</b> 10% (percentuale di lotti venduti e prezzo rispetto alla stima). Se manca un dato, il peso si ridistribuisce sugli altri; servono almeno il 60% dei pesi.</p>
  </div>
  <section class="tr-section" id="synthesis">
    <div class="tr-controls">
      <select class="dash-select" id="s-quad" aria-label="Quadrante">
        <option value="">Tutti i quadranti</option>
        <option value="insider">Insider</option>
        <option value="established">Affermati</option>
        <option value="hype">Hype</option>
        <option value="emerging">Emergenti</option>
      </select>
      <select class="dash-select" id="s-budget" aria-label="Prezzo massimo a 1 m²">
        <option value="">Qualsiasi prezzo</option>
        <option value="10000">Fino a 10.000 USD per 1 m²</option>
        <option value="50000">Fino a 50.000 USD per 1 m²</option>
        <option value="200000">Fino a 200.000 USD per 1 m²</option>
      </select>
      <label class="tr-check"><input type="checkbox" id="s-ig"> Solo con Instagram</label>
      <span class="tr-muted" data-draw="syn-count">—</span>
    </div>
    <div class="tr-tablewrap">
      <table class="tr-table" data-source="matrix" data-row-key="slug">
        <thead><tr>
          <th class="tr-n">#</th>
          <th data-field="name">Artista</th>
          <th data-field="quadrant">Quadrante</th>
          <th class="tr-n" data-field="score_synthesis">Punteggio</th>
          <th class="tr-n">Riconoscimento</th>
          <th class="tr-n">Slancio</th>
          <th class="tr-n">Pubblico</th>
          <th class="tr-n">Valore</th>
          <th class="tr-n">Solidità</th>
          <th class="tr-n" data-field="price_1m2_usd">Prezzo a 1 m² (USD)</th>
          <th class="tr-n" data-field="max_lot_usd">Opera più cara (USD)</th>
          <th data-field="instagram">Instagram</th>
        </tr></thead>
        <tbody data-draw="syn-rows"></tbody>
      </table>
    </div>
    <p class="tr-note" lang="it">Il punteggio ordina, non decide: un artista in cima con pochi lotti all'asta ha prezzi meno affidabili di uno con decine di vendite. Clicca il nome per aprire il profilo con le singole opere vendute.</p>
  </section>
"""
anchor = '\n  <p class="tr-note" lang="it">Mancano ancora i follower Instagram'
i = h.index(anchor)
j = h.index("</p>", i) + 4
body = (PART1 + sec["matrix"] + sec["ranking"] + sec["timeline-view"] + COHERENCE + PART2 + SOCIAL + sec["prices"] +
        sec["experts"] + PART3)
h = h[:i] + body + h[j:]

# ---------- method ----------
rep("""      <li>Prezzi: ultimi 50 risultati d'asta per artista su Artsy, tenendo quelli degli ultimi 5 anni. Prezzo realizzato convertito in USD da Artsy. Gli invenduti contano solo nella percentuale di venduti.</li>""",
    f"""      <li>Prezzi: ultimi 200 risultati d'asta per artista su Artsy, uno per uno, con titolo, tecnica, dimensioni, valuta e importo originali. Analisi sugli ultimi 10 anni. Gli invenduti contano solo nella percentuale di venduti.</li>
      <li>Valute: Artsy registra il prezzo nella valuta della vendita (euro, sterline, yen, yuan, dollari di Hong Kong, won e altre 25) e lo converte in USD. Abbiamo verificato ogni conversione contro il tasso mediano di quella valuta in quell'anno e ricalcolato quelle mancanti o incoerenti. Per yen, won e fiorini l'importo è registrato senza centesimi: il tasso che ne avevamo ricavato era sbagliato di 100 volte e gonfiava i listini galleria in quelle valute. Ora è corretto.</li>
      <li>Dimensioni: per dipinti e opere su carta abbiamo letto altezza e larghezza (centimetri, pollici o millimetri). Confrontando opere dello stesso artista vendute nello stesso anno, il prezzo cresce in media come la superficie elevata a {str(BETA).replace('.', ',')}: un'opera grande il doppio costa circa il {round((2**BETA-1)*100)}% in più. Prezzo a 1 m² = prezzo × (1 m² ÷ superficie)^{str(BETA).replace('.', ',')}, poi la mediana per artista.</li>
      <li>Regola del mercato provato: chi ha venduto all'asta almeno un'opera a 100.000 USD o più non può più essere emergente. Nel quadrante di oggi passa in Hype (attenzione alta, riconoscimento ancora basso); nella serie anno per anno la regola vale dall'anno di quella vendita in poi.</li>
      <li>Instagram: oltre ai profili Wikidata, abbiamo cercato per nome l'account di 2.527 insider ed emergenti in vita, controllando nella bio gallerie, mostre o sito. Affidabilità alta = bio che conferma l'artista; media = nome corrispondente; bassa = esclusa dalle analisi.</li>
      <li>Sintesi: riconoscimento 35%, slancio 20%, notorietà pubblica 15%, valore 20%, solidità 10%; tutte le componenti sono percentili da 0 a 100. Esclusi gli artisti morti, anche quelli che Artsy indica ancora in vita e che abbiamo scoperto durante la ricerca su Instagram.</li>""")
rep("""      <li>Instagram: dai profili Wikidata, collegati all'artista tramite l'ID Artsy oppure per nome quando il nome è univoco. Gli abbinamenti per nome vanno verificati.</li>""",
    """      <li>Instagram da Wikidata: collegati all'artista tramite l'ID Artsy oppure per nome quando il nome è univoco. Gli abbinamenti per nome vanno verificati.</li>""")
rep("""      <li>Scarto = interesse combinato (percentile) meno percentile di prezzo, calcolato solo per artisti con almeno 5 lotti venduti.</li>""",
    """      <li>Scarto = interesse combinato (percentile) meno percentile del prezzo a 1 m², per artisti con almeno 3 dipinti o opere su carta di dimensioni note.</li>""")

# ---------- JS: rows, prices, profile, lots chart, social, synthesis, audit ----------
rep("mp: +r.median_price_usd || 0, ip: +r.interest_pct || 0, vg: r.value_gap === '' || r.value_gap == null ? null : +r.value_gap,",
    "mp: +r.price_1m2_usd || 0, ip: +r.interest_pct || 0, vg: r.interest_vs_price_gap_adj === '' || r.interest_vs_price_gap_adj == null ? null : +r.interest_vs_price_gap_adj, igf: +r.ig_followers || 0, pg: r.public_vs_price_gap === '' || r.public_vs_price_gap == null ? null : +r.public_vs_price_gap, sc: r.score_synthesis === '' ? null : +r.score_synthesis,")
rep("""      const gap = cell(String(r.value_gap), 'tr-n');""", """      const gap = cell(String(r.interest_vs_price_gap_adj), 'tr-n');""")
rep("""      tr.append(cell(a), cell(TR_FMT(r.mp), 'tr-n'), cell(r.mean_price_usd ? TR_FMT(+r.mean_price_usd) : '', 'tr-n'),
        cell(r.max_price_usd ? TR_FMT(+r.max_price_usd) : '', 'tr-n'), cell(r.lots_sold || '', 'tr-n'), cell(r.sell_through_pct || '', 'tr-n'),
        cell(r.interest_pct, 'tr-n'), cell(r.price_pct, 'tr-n'), gap, cell(pill));""",
    """      tr.append(cell(a), cell(TR_FMT(r.mp), 'tr-n'), cell(r.median_usd_10y ? TR_FMT(+r.median_usd_10y) : '', 'tr-n'),
        cell(r.max_lot_usd ? TR_FMT(+r.max_lot_usd) : '', 'tr-n'), cell(r.lots_sold_10y || '', 'tr-n'), cell(r.sell_through_pct || '', 'tr-n'),
        cell(r.interest_pct, 'tr-n'), cell(r.price_adj_pct, 'tr-n'), gap, cell(pill));""")
rep("""        [`Prezzo mediano US$ ${TR_FMT(a.mp)}`, a.max_price_usd ? `Massimo US$ ${TR_FMT(+a.max_price_usd)}` : '', `${a.lots_sold} lotti venduti`,
         `Interesse ${a.interest_pct} · prezzo ${a.price_pct} (percentili)`, `Scarto ${a.value_gap} · ${TR_LABEL[a.quadrant]}`]""",
    """        [`Prezzo a 1 m² US$ ${TR_FMT(a.mp)}`, a.max_lot_usd ? `Opera più cara US$ ${TR_FMT(+a.max_lot_usd)} (${a.max_lot_year})` : '', `${a.lots_sold_10y} lotti venduti in 10 anni`,
         `Interesse ${a.interest_pct} · prezzo ${a.price_adj_pct} (percentili)`, `Scarto ${a.interest_vs_price_gap_adj} · ${TR_LABEL[a.quadrant]}`]""")
rep("g.append('text').attr('x', m.l + 4).attr('y', m.t + 4).attr('dy', '0.7em').text('↑ Prezzo mediano (USD)');",
    "g.append('text').attr('x', m.l + 4).attr('y', m.t + 4).attr('dy', '0.7em').text('↑ Prezzo a 1 m² (USD)');")
# correlation tiles/numbers
rep("""      <div class="tr-tile"><span class="tr-label">Prezzo tipico di 1 m²</span>""", """      <div class="tr-tile"><span class="tr-label">Prezzo tipico di 1 m²</span>""")

rep("fact('Età', 'age', r.age || '—'),", "fact(r.deceased_flag === '1' ? 'Morto' : 'Età', r.deceased_flag === '1' ? 'death_year' : 'age', r.deceased_flag === '1' ? (r.death_year ? `nel ${r.death_year} (Artsy lo indica ancora in vita)` : 'sì (Artsy lo indica ancora in vita)') : (r.age || '—')),")
# movers: size-adjusted growth
rep("""      const g = cell(pct(r.price_growth_pct_per_year), 'tr-n');
      if (r.price_growth_pct_per_year !== '') g.style.color = +r.price_growth_pct_per_year >= 0 ? 'var(--color-ok)' : 'var(--color-bad)';""",
    """      const g = cell(pct(r.adj_growth_pct_per_year), 'tr-n');
      if (r.adj_growth_pct_per_year !== '') g.style.color = +r.adj_growth_pct_per_year >= 0 ? 'var(--color-ok)' : 'var(--color-bad)';""")
h = h.replace("price_growth_pct_per_year", "adj_growth_pct_per_year")  # movers sort + profile now use size-adjusted growth

# profile facts
rep("""      fact('Crescita annua prezzi', 'adj_growth_pct_per_year', r.adj_growth_pct_per_year === '' ? '—' : `${pct(r.adj_growth_pct_per_year)} (${r.price_trend_basis === 'unique works' ? 'opere uniche' : 'tutti i lotti'})`),""",
    """      fact('Crescita annua prezzi, a parità di dimensioni', 'adj_growth_pct_per_year', r.adj_growth_pct_per_year === '' ? '—' : pct(r.adj_growth_pct_per_year)),
      fact('Prezzo a parità di dimensioni (1 m², USD)', 'price_1m2_usd', r.price_1m2_usd ? TR_FMT(+r.price_1m2_usd) : '—'),
      fact('Opera più cara venduta (USD)', 'max_lot_usd', r.max_lot_usd ? `${TR_FMT(+r.max_lot_usd)} (${r.max_lot_year}${r.max_lot_currency && r.max_lot_currency !== 'USD' ? ', venduta in ' + r.max_lot_currency : ''}${r.max_lot_dim ? ', ' + r.max_lot_dim : ''})` : '—'),
      ...(r.quadrant_rule ? [fact('Regola del mercato provato', 'quadrant_rule', `Era ${TR_LABEL[r.quadrant_before_rule]}: ${r.quadrant_rule}`)] : []),
      fact('Instagram', 'ig_followers', r.instagram ? `@${r.instagram}${r.ig_followers ? ' · ' + TR_FMT(+r.ig_followers) + ' follower' : ''}` : '—'),
      fact('Punteggio di sintesi', 'score_synthesis', r.eligible_synthesis === '1' ? dec(r.score_synthesis) : (r.deceased_flag === '1' ? 'non calcolato (artista morto)' : 'non calcolato (meno di 3 opere vendute o dati insufficienti)')),""")
rep("""    mini({ title: 'Prezzo d\\'asta mediano (USD, scala log)', type: 'lines', log: true, series: [
      { key: 'median_unique_usd', label: 'Opere uniche', color: c[0] }, { key: 'median_price_usd', label: 'Tutti i lotti', color: muted }] });
""", "")
rep("TR_redraw('t-artist', 't-profile', 't-strip', 't-charts');", "TR_redraw('t-artist', 't-profile', 't-strip', 't-charts', 't-lots');")

NEWJS = r"""
<script>
  const BETA = __BETA__;
  const dec = (v) => (v === '' || v == null) ? '—' : String(v).replace('.', ',');  // each dashboard script has its own scope
  const CAT = { P: 'Dipinto', C: 'Opera su carta', S: 'Scultura', M: 'Stampa o multiplo', F: 'Fotografia', A: 'Altro' };
  window.LOT_index = () => {
    const d = dash.data('lots');
    if (d.status !== 'ok') return null;
    if (!window.LOT_cache || window.LOT_cache.src !== d.data) {
      const idx = new Map();
      for (const r of d.data) { if (!idx.has(r.slug)) idx.set(r.slug, []); idx.get(r.slug).push(r); }
      window.LOT_cache = { src: d.data, idx };
    }
    return window.LOT_cache.idx;
  };
  dash.draw('t-lots', (box) => {
    const idx = LOT_index();
    box.replaceChildren();
    if (!idx) { box.textContent = dash.data('lots').status === 'loading' ? 'Caricamento…' : 'Dati non caricati.'; return; }
    const L = (idx.get(TR.artist) || []).map((r) => ({ ...r, t: new Date(r.d + '-15'), usd: +r.usd, a: +r.a || 0 }));
    if (!L.length) { const e = document.createElement('div'); e.className = 'tr-muted'; e.textContent = 'Nessuna opera venduta all\'asta negli ultimi 10 anni su Artsy.'; box.append(e); return; }
    const c = dash.colors, muted = 'var(--cds-chart-muted)';
    const COL = { P: c[0], C: c[1], S: c[2], M: muted, F: muted, A: muted };
    const lg = document.createElement('div'); lg.className = 'tr-mini-legend';
    [...new Set(L.map((r) => r.c))].forEach((k) => { const sp = document.createElement('span'); const sw = document.createElement('i'); sw.className = 'tr-sw'; sw.style.background = COL[k]; sp.append(sw, CAT[k] || k); lg.append(sp); });
    const ln = document.createElement('span'); ln.textContent = '— prezzo mediano a 1 m²'; lg.append(ln);
    box.append(lg);
    const yrs = d3.groups(L.filter((r) => (r.c === 'P' || r.c === 'C') && r.a), (r) => r.t.getFullYear())
      .map(([y, v]) => [new Date(y, 6, 1), d3.median(v, (r) => r.usd * Math.pow(10000 / r.a, BETA))]).sort((a, b) => a[0] - b[0]);
    const W = Math.max(260, box.clientWidth), H = 250, m = { t: 10, r: 10, b: 22, l: 52 };
    const now = new Date();
    const x = d3.scaleTime().domain([new Date(now.getFullYear() - 10, 0, 1), now]).range([m.l, W - m.r]);
    const vals = [...L.map((r) => r.usd), ...yrs.map((p) => p[1])].filter((v) => v > 0);
    const y = d3.scaleLog().domain(d3.extent(vals)).range([H - m.b, m.t]).nice();
    const R = d3.scaleSqrt().domain([0, d3.max(L, (r) => r.a) || 1]).range([2.5, 10]);
    const svg = d3.select(box).append('svg').attr('width', W).attr('height', H).attr('role', 'img').attr('aria-label', `Opere vendute all'asta, una per una: ${L.length} lotti`);
    svg.append('g').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(6).tickSizeOuter(0)).call((g) => g.selectAll('line,path').style('stroke', 'var(--cds-chart-axis)'));
    svg.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4, '~s').tickSizeOuter(0)).call((g) => g.selectAll('line,path').style('stroke', 'var(--cds-chart-axis)'));
    if (yrs.length > 1) svg.append('path').datum(yrs).attr('fill', 'none').style('stroke', 'var(--color-fg)').attr('stroke-width', 1.5).attr('stroke-dasharray', '4 3').attr('d', d3.line().x((p) => x(p[0])).y((p) => y(p[1])));
    const tip = document.createElement('div'); tip.className = 'tr-tip'; tip.hidden = true; box.append(tip);
    svg.selectAll(null).data(L.sort((a, b) => b.a - a.a)).join('circle')
      .attr('cx', (r) => x(r.t)).attr('cy', (r) => y(r.usd)).attr('r', (r) => r.a ? R(r.a) : 3)
      .style('fill', (r) => r.a ? COL[r.c] : 'none').style('stroke', (r) => COL[r.c]).attr('fill-opacity', 0.7).attr('stroke-width', 1)
      .on('mouseenter', (ev, r) => {
        tip.replaceChildren();
        const b = document.createElement('b'); b.textContent = `US$ ${TR_FMT(r.usd)}`; tip.append(b);
        [r.cur ? `Venduto in ${r.cur}: ${TR_FMT(+r.orig)}` : '', `${CAT[r.c] || ''} · ${r.d.replace('-', '/')}`,
         r.a ? `Superficie ${TR_FMT(r.a)} cm²${(r.c === 'P' || r.c === 'C') ? ` · a 1 m²: US$ ${TR_FMT(Math.round(r.usd * Math.pow(10000 / r.a, BETA)))}` : ''}` : 'Dimensioni non indicate']
          .filter(Boolean).forEach((t) => { const d = document.createElement('div'); d.textContent = t; tip.append(d); });
        tip.hidden = false;
        tip.style.left = `${Math.min(Math.max(0, x(r.t) + 10), box.clientWidth - tip.offsetWidth)}px`; tip.style.top = `${Math.max(0, y(r.usd) - 60)}px`;
      })
      .on('mouseleave', () => { tip.hidden = true; });
  });

  // ---------- coherence audit ----------
  const AUDIT = {
    emerging_to_hype_market_rule: ['Emergenti di oggi con almeno un\'opera già venduta a 100.000 USD o più', 'Spostati in Hype: il mercato li ha già prezzati, non sono più una scoperta. Nel profilo resta scritto il quadrante di prima.'],
    timeline_emerging_to_hype_market_rule: ['Anni-artista «emergenti» dopo una vendita da 100.000 USD', 'Stessa regola nella serie storica: dall\'anno di quella vendita l\'artista non torna emergente.'],
    growth_sign_flips_after_size_adjustment: ['Artisti la cui crescita dei prezzi cambia segno tenendo conto delle dimensioni', 'La crescita «grezza» dipendeva dal formato delle opere vendute in ogni anno. Ora tutte le crescite sono calcolate a parità di dimensioni.'],
    listing_price_was_inflated: ['Listini galleria gonfiati da un errore di cambio', 'Opere in vendita in yen, won o fiorini: Artsy registra l\'importo intero, non i centesimi. Corretto il tasso.'],
    lots_fx_recomputed: ['Lotti con conversione in USD mancante o fuori scala', 'Ricalcolati con il tasso mediano di quella valuta in quell\'anno.'],
    deceased_corrected_in_matrix: ['Artisti indicati in vita da Artsy ma morti, corretti nella matrice', 'Trovati durante la ricerca degli account Instagram (data di morte o account gestito dall\'estate). Nella matrice non hanno più l\'età, il profilo mostra l\'anno di morte, e sono esclusi dalla sintesi e dai passaggi tra quadranti degli artisti in vita.'],
    timeline_quadrant_flapping_4plus_changes: ['Artisti che cambiano quadrante 4 o più volte dal 2016', 'Casi rari: la soglia di uscita al 65° percentile funziona. Restano segnati come «al limite».'],
    timeline_recognition_high_to_low: ['Riconoscimento degli esperti che scende da alto a basso', 'Nessun caso: il riconoscimento si accumula e non torna indietro, come previsto.'],
    artists_market_proven: ['Artisti con almeno un\'opera venduta a 100.000 USD o più', 'Riferimento per la regola del mercato provato.'],
    lots_sold_parsed: ['Opere vendute analizzate una per una', 'Dal 2010, con valuta e importo originali.'],
    lots_with_size: ['…di cui con dimensioni leggibili', 'Base per il prezzo a parità di dimensioni.'],
    artists_with_lots: ['Artisti con almeno un\'opera venduta', ''],
  };
  dash.draw('audit-rows', (tb) => {
    const d = dash.data('audit');
    if (d.status !== 'ok') { tb.replaceChildren(); return; }
    const by = new Map(d.data.map((r) => [r.check, r.value]));
    const cell = (t, c) => { const x = document.createElement('td'); if (c) x.className = c; x.textContent = t; return x; };
    tb.replaceChildren(...Object.keys(AUDIT).filter((k) => by.has(k)).map((k) => {
      const tr = document.createElement('tr'); tr.dataset.key = k;
      const v = cell(TR_FMT(+by.get(k)), 'tr-n'); v.dataset.source = 'audit'; v.dataset.field = 'value'; v.dataset.where = `check=${k}`;
      tr.append(cell(AUDIT[k][0]), v, cell(AUDIT[k][1])); return tr;
    }));
  });

  // ---------- social ----------
  dash.calc('ig_by_quad', {
    title: 'Follower Instagram per quadrante', description: 'Mediana dei follower Instagram per quadrante, tra gli artisti con follower noti.',
    inputs: ['matrix'],
    fn: (matrix) => ['insider', 'established', 'hype', 'emerging'].map((q) => {
      const v = matrix.filter((r) => r.quadrant === q && r.ig_followers).map((r) => +r.ig_followers).sort((a, b) => a - b);
      return { quadrant: q, artists: v.length, median_followers: v.length ? v[Math.floor(v.length / 2)] : 0 };
    }),
  });
  dash.draw('ig-quad-bars', (el) => {
    const d = dash.data('ig_by_quad');
    if (d.status !== 'ok') { el.textContent = ''; return; }
    const max = d3.max(d.data, (r) => r.median_followers) || 1;
    el.replaceChildren(...d.data.map((r) => {
      const row = document.createElement('div'); row.className = 'tr-bar-row';
      const l = document.createElement('span'); l.textContent = `${TR_LABEL[r.quadrant]} (${TR_FMT(r.artists)})`;
      const t = document.createElement('div'); t.className = 'tr-bar-track'; const f = document.createElement('div'); f.className = 'tr-bar-fill'; f.style.width = `${100 * r.median_followers / max}%`; f.style.background = TR_COLOR(r.quadrant); t.append(f);
      const v = document.createElement('span'); v.className = 'tr-bar-val'; v.textContent = TR_FMT(r.median_followers); v.dataset.source = 'ig_by_quad'; v.dataset.field = 'median_followers'; v.dataset.where = `quadrant=${r.quadrant}`;
      row.append(l, t, v); return row;
    }));
  });
  dash.draw('ig-scatter', (box) => {
    const rows = TR_rows();
    box.replaceChildren();
    if (!rows) { box.textContent = 'Caricamento…'; return; }
    const pts = rows.filter((r) => r.igf > 0 && r.mp > 0);
    if (!pts.length) { box.textContent = 'Nessun artista con follower Instagram e prezzi corrisponde ai filtri.'; return; }
    const W = Math.max(280, box.clientWidth), H = Math.max(320, Math.min(460, Math.round(W * 0.55))), m = { t: 12, r: 14, b: 40, l: 58 };
    const all = TR_cache.rows.filter((r) => r.igf > 0 && r.mp > 0);
    const x = d3.scaleLog().domain(d3.extent(all, (r) => r.igf)).range([m.l, W - m.r]).nice();
    const y = d3.scaleLog().domain(d3.extent(all, (r) => r.mp)).range([H - m.b, m.t]).nice();
    const svg = d3.select(box).append('svg').attr('width', W).attr('height', H).attr('role', 'img').attr('aria-label', 'Follower Instagram contro prezzo a 1 m² per artista');
    svg.append('g').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(5, '~s').tickSizeOuter(0)).call((s) => s.selectAll('line,path').style('stroke', 'var(--cds-chart-axis)'));
    svg.append('g').attr('transform', `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(5, '~s').tickSizeOuter(0)).call((s) => s.selectAll('line,path').style('stroke', 'var(--cds-chart-axis)'));
    svg.append('text').attr('x', W - m.r).attr('y', H - 6).attr('text-anchor', 'end').text('Follower Instagram →');
    svg.append('text').attr('x', m.l + 4).attr('y', m.t + 4).attr('dy', '0.7em').text('↑ Prezzo a 1 m² (USD)');
    const tip = document.createElement('div'); tip.className = 'tr-tip'; tip.hidden = true; box.append(tip);
    svg.selectAll(null).data(pts).join('circle').attr('cx', (r) => x(r.igf)).attr('cy', (r) => y(r.mp)).attr('r', pts.length > 400 ? 3 : 4)
      .style('fill', (r) => TR_COLOR(r.quadrant)).attr('fill-opacity', 0.8).style('cursor', 'pointer')
      .on('mouseenter', (ev, r) => {
        tip.replaceChildren(); const b = document.createElement('b'); b.textContent = r.name; tip.append(b);
        [`@${r.instagram} · ${TR_FMT(r.igf)} follower`, `Prezzo a 1 m² US$ ${TR_FMT(r.mp)}`, `Notorietà ${r.public_pct} · prezzo ${r.price_adj_pct} (percentili)`, TR_LABEL[r.quadrant]]
          .forEach((t) => { const d = document.createElement('div'); d.textContent = t; tip.append(d); });
        tip.hidden = false;
        tip.style.left = `${Math.min(Math.max(0, x(r.igf) + 12), box.clientWidth - tip.offsetWidth)}px`; tip.style.top = `${Math.max(0, y(r.mp) - 70)}px`;
      })
      .on('mouseleave', () => { tip.hidden = true; })
      .on('click', (ev, r) => TR_select(r.slug));
  });
  window.TR_pubrows = () => { const rows = TR_rows(); return rows ? rows.filter((r) => r.pg !== null && !isNaN(r.pg) && r.igf > 0) : null; };
  dash.draw('pub-count', (el) => { const rows = TR_pubrows(); el.textContent = rows ? `${TR_FMT(rows.length)} artisti con follower Instagram e prezzi, mostrati i primi ${Math.min(100, rows.length)}` : '—'; });
  dash.draw('pub-rows', (tb) => {
    const rows = TR_pubrows();
    if (!rows) { tb.replaceChildren(); return; }
    const sgn = (TR.pubSort || 'under') === 'over' ? 1 : -1;
    const cell = (t, c) => { const x = document.createElement('td'); if (c) x.className = c; if (t instanceof Node) x.append(t); else x.textContent = t; return x; };
    const top = rows.slice().sort((a, b) => sgn * (a.pg - b.pg)).slice(0, 100);
    if (!top.length) { const tr = document.createElement('tr'); const c = cell('Nessun artista corrisponde ai filtri.', 'tr-empty'); c.colSpan = 9; tr.append(c); tb.replaceChildren(tr); return; }
    tb.replaceChildren(...top.map((r) => {
      const tr = document.createElement('tr'); tr.dataset.key = encodeURIComponent(r.slug);
      const b = document.createElement('button'); b.type = 'button'; b.className = 'tr-linkbtn'; b.textContent = r.name; b.onclick = () => TR_select(r.slug);
      const a = document.createElement('a'); a.href = `https://www.instagram.com/${encodeURIComponent(r.instagram)}/`; a.target = '_blank'; a.rel = 'noopener'; a.textContent = '@' + r.instagram;
      const g = cell(dec(r.public_vs_price_gap), 'tr-n'); g.style.color = r.pg > 0 ? 'var(--color-ok)' : 'var(--color-bad)';
      tr.append(cell(b), cell(a), cell(TR_FMT(r.igf), 'tr-n'), cell(TR_FMT(r.f), 'tr-n'), cell(dec(r.public_pct), 'tr-n'), cell(TR_FMT(r.mp), 'tr-n'), cell(dec(r.price_adj_pct), 'tr-n'), g, cell(TR_pill(r)));
      return tr;
    }));
  });

  // ---------- synthesis ----------
  window.TR_syn = () => {
    TR_rows();
    if (!window.TR_cache) return null;
    const q = TR.sq || '', bud = +(TR.sb || 0), ig = !!TR.sig;
    return TR_cache.rows.filter((r) => r.eligible_synthesis === '1' && r.sc !== null && (!q || r.quadrant === q) && (!bud || (r.mp > 0 && r.mp <= bud)) && (!ig || r.instagram))
      .sort((a, b) => b.sc - a.sc);
  };
  dash.draw('syn-count', (el) => { const rows = TR_syn(); el.textContent = rows ? `${TR_FMT(rows.length)} artisti valutati, mostrati i primi ${Math.min(100, rows.length)}` : '—'; });
  dash.draw('syn-rows', (tb) => {
    const rows = TR_syn();
    if (!rows) { tb.replaceChildren(); return; }
    const cell = (t, c) => { const x = document.createElement('td'); if (c) x.className = c; if (t instanceof Node) x.append(t); else x.textContent = t; return x; };
    if (!rows.length) { const tr = document.createElement('tr'); const c = cell('Nessun artista corrisponde ai filtri.', 'tr-empty'); c.colSpan = 12; tr.append(c); tb.replaceChildren(tr); return; }
    tb.replaceChildren(...rows.slice(0, 100).map((r, i) => {
      const parts = Object.fromEntries((r.score_parts || '').split(';').filter(Boolean).map((s) => s.split('=')));
      const tr = document.createElement('tr'); tr.dataset.key = encodeURIComponent(r.slug);
      const b = document.createElement('button'); b.type = 'button'; b.className = 'tr-linkbtn'; b.textContent = r.name; b.onclick = () => TR_select(r.slug);
      const sc = cell(dec(r.score_synthesis), 'tr-n'); sc.style.fontWeight = '600'; sc.dataset.source = 'matrix'; sc.dataset.field = 'score_synthesis'; sc.dataset.where = `slug=${encodeURIComponent(r.slug)}`;
      const ig = r.instagram ? (() => { const a = document.createElement('a'); a.href = `https://www.instagram.com/${encodeURIComponent(r.instagram)}/`; a.target = '_blank'; a.rel = 'noopener'; a.textContent = '@' + r.instagram + (r.igf ? ` · ${TR_FMT(r.igf)}` : ''); return a; })() : '';
      tr.append(cell(String(i + 1), 'tr-n'), cell(b), cell(TR_pill(r)), sc, cell(parts.rec ?? '—', 'tr-n'), cell(parts.mom ?? '—', 'tr-n'), cell(parts.pub ?? '—', 'tr-n'),
        cell(parts.value ?? '—', 'tr-n'), cell(parts.solid ?? '—', 'tr-n'), cell(r.mp ? TR_FMT(r.mp) : '—', 'tr-n'), cell(r.max_lot_usd ? TR_FMT(+r.max_lot_usd) : '—', 'tr-n'), cell(ig));
      return tr;
    }));
  });
  const on2 = (sel, ev, fn) => document.querySelectorAll(sel).forEach((el) => el.addEventListener(ev, fn));
  on2('#f-pub', 'change', (e) => { TR.pubSort = e.target.value; dash.draw('pub-rows'); });
  on2('#s-quad', 'change', (e) => { TR.sq = e.target.value; ['syn-rows', 'syn-count'].forEach((n) => dash.draw(n)); });
  on2('#s-budget', 'change', (e) => { TR.sb = e.target.value; ['syn-rows', 'syn-count'].forEach((n) => dash.draw(n)); });
  on2('#s-ig', 'change', (e) => { TR.sig = e.target.checked; ['syn-rows', 'syn-count'].forEach((n) => dash.draw(n)); });
</script>
""".replace("__BETA__", str(BETA))
h = h.rstrip() + "\n" + NEWJS
# filters in part 1 also redraw social views
rep("const redraw = window.TR_redraw = (...names) => (names.includes('scatter') ? [...names, 'price-scatter', 'gap-rows', 'gap-count', 'mv-rows', 'mv-count'] : names).forEach((n) => dash.draw(n));",
    "const redraw = window.TR_redraw = (...names) => (names.includes('scatter') ? [...names, 'price-scatter', 'gap-rows', 'gap-count', 'mv-rows', 'mv-count', 'ig-scatter', 'pub-rows', 'pub-count'] : names).forEach((n) => dash.draw(n));")
# correlation numbers for new sentence
rep("  one('p-med', 'median_price_usd', (v) => TR_FMT(+v));", """  one('p-med', 'median_price_usd', (v) => TR_FMT(+v));
  one('p-rho-e2', 'rho_price_expert', rho);
  one('p-rho-f2', 'rho_price_followers', rho);
  one('s-rho-ig', 'rho_price_instagram', rho);""")
rep("  num('n-analyzed', 'pipeline', 'artists_analyzed');", """  num('n-analyzed', 'pipeline', 'artists_analyzed');
  num('s-ig', 'pipeline', 'instagram_in_matrix');
  num('s-ig-f', 'pipeline', 'instagram_with_followers');""")
# v7.1 audit fixes
rep("""          <th class="tr-n" data-field="median_price_usd">Prezzo mediano (USD)</th>""", """          <th class="tr-n" data-field="median_usd_10y">Prezzo mediano, 10 anni (USD)</th>""")
rep("td(r.mp ? TR_FMT(r.mp) : '', 'tr-n'), td(mom, 'tr-tags')", "td(r.median_usd_10y ? TR_FMT(+r.median_usd_10y) : '', 'tr-n'), td(mom, 'tr-tags')")
h = h.replace('data-field="sell_through_pct">% venduti</th>', 'data-field="sell_through_10y">% venduti, 10 anni</th>')
h = h.replace("cell(r.sell_through_pct || '', 'tr-n')", "cell(r.sell_through_10y || '', 'tr-n')")
rep("    return rows.filter(f[0]).sort((a, b) => f[1](b) - f[1](a));\n  };", "    return rows.filter((r) => String(r.living) === '1').filter(f[0]).sort((a, b) => f[1](b) - f[1](a));\n  };")
import csv as _csv
_m = list(_csv.DictReader(open(MATRIX, encoding="utf-8")))
QDIFF = sum(1 for r in _m if r["quadrant_artsy"] and r["quadrant_artsy"] != r["quadrant"])
h = h.replace("Differisce dal quadrante oggi per circa 2.250 artisti", f"Differisce dal quadrante oggi per {QDIFF:,} artisti".replace(",", "."))
print("qdiff", QDIFF)
open(f"{D}/index_v7.html", "w", encoding="utf-8").write(h)
print("ok", len(h))

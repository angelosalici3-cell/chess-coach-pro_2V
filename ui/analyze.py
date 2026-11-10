import io

import chess
import chess.pgn
import streamlit as st

from services.analysis import analyze_pgn, create_review_items_from_errors
from services.usage import remaining_analyses, record_analysis
from services.rating import extract_and_save
from services.supabase_client import get_client
from services.analytics import track_context, capture_event, Events
from ui.components import board_svg, alert
from config.constants import STOCKFISH_DEPTH


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader(f"🔍 {texts['analyze']}")

    left = remaining_analyses(user_email, tier)
    if left <= 0:
        alert(texts["quota_exhausted"], "danger")
        if st.button(texts["upgrade"], type="primary"):
            st.session_state["nav"] = "pricing"
            st.rerun()
        return

    pgn = st.text_area("PGN della partita", height=160, key="pgn_input")
    col_up, col_btn = st.columns([2, 1])
    with col_up:
        uploaded = st.file_uploader("… oppure carica un file PGN", type=["pgn", "txt"])
        if uploaded:
            pgn = uploaded.read().decode("utf-8", errors="ignore")
    with col_btn:
        st.write("")
        run = st.button(texts["analyze_btn"], type="primary",
                        use_container_width=True, disabled=not pgn.strip())

    if not run:
        _render_last_analysis(texts)
        return

    progress = st.progress(0.0, text="Analisi Stockfish in corso…")
    try:
        depth = STOCKFISH_DEPTH.get(tier, 10)
        result = analyze_pgn(
            pgn.strip(),
            target_usernames=[],
            depth=depth,
            progress_cb=lambda p: progress.progress(p, text=f"Analisi {int(p*100)}%"),
        )
        progress.empty()

        st.session_state["last_analysis"] = result
        st.session_state["last_pgn"] = pgn
        st.session_state["ply"] = 0

        with track_context(user_email):
            if result.get("cached"):
                capture_event(Events.ANALYSIS_CACHED_HIT,
                              {"partita_id": result["partita_id"]})
                alert("✅ Risultato recuperato dalla cache (istantaneo).", "success")
            else:
                capture_event(Events.GAME_ANALYZED, {
                    "partita_id": result["partita_id"],
                    "errors_count": len(result["errors"]),
                    "depth": depth,
                    "tier": tier,
                })
                record_analysis(user_email, result.get("partita_id", "unknown"))
                alert(f"✅ Analisi completata — {len(result['errors'])} criticità trovate.", "success")

        _save_errors_to_db(user_email, result, pgn.strip(), tier)
    except Exception as e:
        progress.empty()
        alert(f"Errore: {e}", "danger")
        return

    _render_last_analysis(texts)


def _save_errors_to_db(user_email: str, result: dict, pgn_text: str, tier: str):
    client = get_client()
    partita_id = result["partita_id"]

    try:
        profs = client.table("profili_scacchi").select("username").eq("user_email", user_email).execute().data or []
        usernames = [p["username"] for p in profs]
    except Exception:
        usernames = []

    extract_and_save(user_email, pgn_text, partita_id, usernames, result["errors"])

    if result.get("cached") or not result["errors"]:
        return

    rows_to_insert = [{
        "user_email": user_email,
        "partita_id": partita_id,
        "categoria_errore": e["categoria"],
        "mossa_critica": e["label_mossa"],
        "spiegazione": f"Perdita {e['perdita_cp']} CP ({e['tipo_problema']})",
        "fen_prima": e["fen_prima"],
        "perdita_cp": e["perdita_cp"],
    } for e in result["errors"]]

    try:
        res = client.table("errori_utenti").insert(rows_to_insert).execute()
        inserted = res.data or []
    except Exception:
        return

    create_review_items_from_errors(user_email, inserted)


def _render_last_analysis(texts: dict):
    result = st.session_state.get("last_analysis")
    pgn = st.session_state.get("last_pgn")
    if not result or not pgn:
        return

    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return
    moves = list(game.mainline_moves())
    if "ply" not in st.session_state:
        st.session_state["ply"] = 0
    ply = max(0, min(st.session_state["ply"], len(moves)))

    c1, c2, c3, c4 = st.columns(4)
    if c1.button("⏮", use_container_width=True):
        st.session_state["ply"] = 0; st.rerun()
    if c2.button("◀", use_container_width=True) and ply > 0:
        st.session_state["ply"] = ply - 1; st.rerun()
    if c3.button("▶", use_container_width=True) and ply < len(moves):
        st.session_state["ply"] = ply + 1; st.rerun()
    if c4.button("⏭", use_container_width=True):
        st.session_state["ply"] = len(moves); st.rerun()

    board = game.board()
    for i in range(ply):
        board.push(moves[i])
    st.markdown(board_svg(board, 420), unsafe_allow_html=True)

    if result["eval_history"]:
        try:
            import plotly.graph_objects as go
            xs = [e["ply"] for e in result["eval_history"]]
            ys = [e["eval_clamped"] for e in result["eval_history"]]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="tozeroy",
                                     line=dict(color="#d4af37", width=2),
                                     fillcolor="rgba(212,175,55,.15)"))
            fig.update_layout(
                height=280, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8eaf0",
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    st.markdown("### Criticità")
    for i, e in enumerate(result["errors"]):
        with st.expander(f"{e['tipo_problema']} · {e['label_mossa']} · {e['categoria']}"):
            st.markdown(f"**Cluster:** {e['categoria']} · **Perdita:** {e['perdita_cp']} CP")
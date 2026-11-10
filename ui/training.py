import pandas as pd
import chess
import chess.svg
import streamlit as st

from services.supabase_client import get_client
from services.analytics import track_context, capture_event, Events
from ui.components import alert, metric_card


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader(f"🎯 {texts['training']}")

    client = get_client()
    try:
        res = client.table("errori_utenti").select("*").eq("user_email", user_email).execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        alert("Nessun errore da allenare. Analizza qualche partita prima.", "info")
        return

    counts = df["categoria_errore"].value_counts()
    top = counts.index[0] if len(counts) else "—"

    c1, c2 = st.columns([1, 2])
    with c1:
        metric_card("Punto debole", top, "purple")
    with c2:
        alert(f"Il cluster in cui sbagli di più è <b>{top}</b> ({counts.iloc[0]} errori).", "warn")

    st.divider()
    sel = st.selectbox("Filtra per cluster", ["Tutti"] + counts.index.tolist())
    filtered = df if sel == "Tutti" else df[df["categoria_errore"] == sel]
    if filtered.empty:
        alert("Nessun errore in questo cluster.", "info")
        return

    row = filtered.sample(1).iloc[0]

    with track_context(user_email):
        capture_event(Events.TRAINING_SESSION_STARTED, {"cluster": sel})

    st.markdown(
        f"**Cluster:** `{row['categoria_errore']}` · "
        f"**Mossa errata:** `{row['mossa_critica']}`"
    )
    if row.get("fen_prima"):
        try:
            board = chess.Board(row["fen_prima"])
            svg = chess.svg.board(board=board, size=360)
            st.markdown(f"<div class='cc-board'>{svg}</div>", unsafe_allow_html=True)
        except Exception:
            pass
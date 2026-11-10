import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from services.supabase_client import get_client
from services.analytics import track_context, capture_event, Events
from services.usage import remaining_analyses
from services.rating import load_trend
from ui.components import alert, metric_card


@st.cache_data(ttl=60)
def _load_errors(user_email: str) -> pd.DataFrame:
    client = get_client()
    try:
        res = (
            client.table("errori_utenti")
            .select("*")
            .eq("user_email", user_email)
            .order("data", desc=True)
            .execute()
        )
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _compute_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"total_errors": 0, "games_analyzed": 0, "blunder_rate": 0.0,
                "avg_loss_cp": 0.0, "accuracy": 0.0}

    total = len(df)
    games = df["partita_id"].nunique() if "partita_id" in df else 0
    blunders = len(df[df["spiegazione"].str.contains("Blunder", na=False)]) if "spiegazione" in df else 0
    blunder_rate = (blunders / total * 100) if total > 0 else 0

    if "perdita_cp" in df:
        avg_loss = df["perdita_cp"].fillna(0).mean()
    else:
        avg_loss = 0.0

    accuracy = max(0, min(100, 100 - avg_loss * 2)) if avg_loss else 100

    return {
        "total_errors": total, "games_analyzed": games,
        "blunder_rate": round(blunder_rate, 1),
        "avg_loss_cp": round(float(avg_loss), 1),
        "accuracy": round(accuracy, 1),
    }


def _render_kpi_row(kpis: dict, quota_left: int):
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Accuracy", f"{kpis['accuracy']}%", "green")
    with c2: metric_card("Blunder rate", f"{kpis['blunder_rate']}%",
                        "gold" if kpis["blunder_rate"] < 15 else "purple")
    with c3: metric_card("Partite analizzate", kpis["games_analyzed"], "blue")
    with c4: metric_card("Analisi residue", quota_left, "gold")


def _render_trend(df: pd.DataFrame):
    if df.empty or "data" not in df:
        return
    df2 = df.copy()
    df2["data"] = pd.to_datetime(df2["data"])
    weekly = df2.groupby(pd.Grouper(key="data", freq="W")).size().reset_index(name="errori")
    weekly = weekly[weekly["errori"] > 0]
    if weekly.empty:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weekly["data"], y=weekly["errori"], mode="lines+markers",
        line=dict(color="#d4af37", width=3),
        marker=dict(size=8, color="#d4af37"),
        fill="tozeroy", fillcolor="rgba(212,175,55,0.12)",
        name="Errori / settimana",
    ))
    fig.update_layout(
        title="Trend errori nel tempo", height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8eaf0",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_cluster_distribution(df: pd.DataFrame):
    if df.empty or "categoria_errore" not in df:
        return
    counts = df["categoria_errore"].value_counts().head(8)
    fig = go.Figure(go.Pie(
        labels=counts.index, values=counts.values, hole=0.6,
        marker=dict(colors=px.colors.sequential.Gold[::-1]),
        textinfo="percent", textfont=dict(color="#e8eaf0"),
    ))
    fig.update_layout(
        title="Distribuzione errori per cluster", height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)", font_color="#e8eaf0",
        showlegend=True, legend=dict(font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_white_black_split(df: pd.DataFrame):
    if df.empty or "mossa_critica" not in df:
        return

    def _is_white(label: str) -> bool:
        return "." in str(label) and "..." not in str(label)

    df_w = df[df["mossa_critica"].apply(_is_white)]
    df_b = df[~df["mossa_critica"].apply(_is_white)]

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Errori con Bianco", len(df_w))
        if not df_w.empty and "categoria_errore" in df_w:
            for cat, cnt in df_w["categoria_errore"].value_counts().head(3).items():
                st.caption(f"• {cat}: {cnt}")
    with c2:
        st.metric("Errori con Nero", len(df_b))
        if not df_b.empty and "categoria_errore" in df_b:
            for cat, cnt in df_b["categoria_errore"].value_counts().head(3).items():
                st.caption(f"• {cat}: {cnt}")


def _render_phase_breakdown(df: pd.DataFrame):
    if df.empty or "categoria_errore" not in df:
        return
    phase_map = {"Opening Mistake": "Apertura", "Endgame": "Finale"}
    df2 = df.copy()
    df2["fase"] = df2["categoria_errore"].map(phase_map).fillna("Mediogioco")
    phase_counts = df2["fase"].value_counts().reindex(["Apertura", "Mediogioco", "Finale"]).fillna(0)
    fig = go.Figure(go.Bar(
        x=phase_counts.index, y=phase_counts.values,
        marker_color=["#d4af37", "#a855f7", "#3b82f6"],
        text=phase_counts.values, textposition="auto",
    ))
    fig.update_layout(
        title="Errori per fase di gioco", height=300,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8eaf0",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_recent_games(df: pd.DataFrame):
    if df.empty or "partita_id" not in df:
        return
    recent = (
        df.groupby("partita_id")
        .agg(
            data=("data", "min"),
            errori=("categoria_errore", "count"),
            top_cluster=("categoria_errore",
                        lambda x: x.value_counts().index[0] if len(x) else "—"),
        )
        .sort_values("data", ascending=False)
        .head(10)
        .reset_index()
    )
    st.dataframe(recent, use_container_width=True, hide_index=True)


def _render_rating_section(user_email: str):
    df = load_trend(user_email)
    if df.empty:
        alert(
            "Nessuna partita con rating disponibile. Le partite devono avere WhiteElo/BlackElo nel PGN.",
            "info",
        )
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data_partita"], y=df["user_elo"],
        mode="lines+markers", name="Il tuo Elo",
        line=dict(color="#d4af37", width=3),
        marker=dict(size=8),
    ))
    fig.add_trace(go.Scatter(
        x=df["data_partita"], y=df["opponent_elo"],
        mode="lines", name="Elo avversario",
        line=dict(color="#94a3b8", width=1, dash="dot"),
    ))
    fig.update_layout(
        title="Trend Elo nel tempo", height=320,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8eaf0",
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)

    wins = len(df[df["outcome"] == "W"])
    losses = len(df[df["outcome"] == "L"])
    draws = len(df[df["outcome"] == "D"])
    total = wins + losses + draws
    win_rate = round(wins / total * 100, 1) if total else 0
    avg_elo = int(df["user_elo"].mean())
    peak_elo = int(df["user_elo"].max())
    last_elo = int(df["user_elo"].iloc[-1])

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Elo attuale", last_elo, "gold")
    with c2: metric_card("Elo medio", avg_elo, "blue")
    with c3: metric_card("Peak Elo", peak_elo, "purple")
    with c4: metric_card("Win rate", f"{win_rate}%", "green")

    fig2 = go.Figure(go.Bar(
        x=["Vittorie", "Pareggi", "Sconfitte"], y=[wins, draws, losses],
        marker_color=["#10b981", "#94a3b8", "#ef4444"],
        text=[wins, draws, losses], textposition="auto",
    ))
    fig2.update_layout(
        title="Risultati", height=260,
        margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8eaf0",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
    )
    st.plotly_chart(fig2, use_container_width=True)


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader("📈 Analytics & Insights")

    with track_context(user_email):
        capture_event(Events.PAGE_VIEWED, {"page": "analytics", "tier": tier})

    with st.spinner("Caricamento statistiche…"):
        df = _load_errors(user_email)
        quota_left = remaining_analyses(user_email, tier)

    tab_overview, tab_rating, tab_errors = st.tabs(
        ["📊 Overview", "📈 Rating Trend", "🎯 Errori"]
    )

    with tab_overview:
        kpis = _compute_kpis(df)
        _render_kpi_row(kpis, quota_left)
        st.divider()
        if not df.empty:
            _render_trend(df)
            col_a, col_b = st.columns(2)
            with col_a: _render_cluster_distribution(df)
            with col_b: _render_phase_breakdown(df)
            st.divider()
            st.markdown("### 📋 Ultime partite")
            _render_recent_games(df)
        else:
            alert("Nessun dato. Analizza la prima partita per sbloccare le statistiche.", "info")

    with tab_rating:
        _render_rating_section(user_email)

    with tab_errors:
        if df.empty:
            alert("Nessun errore censito.", "info")
        else:
            _render_white_black_split(df)
            st.divider()
            st.markdown("### 🔝 Cluster più frequenti")
            counts = df["categoria_errore"].value_counts().head(15)
            st.dataframe(
                counts.reset_index().rename(columns={"index": "Cluster", "categoria_errore": "Count"}),
                use_container_width=True, hide_index=True,
            )
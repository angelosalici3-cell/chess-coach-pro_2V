import pandas as pd
import streamlit as st

from services.supabase_client import get_client
from services.usage import remaining_analyses
from services.srs import due_count
from ui.components import metric_card, alert


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader(f"📊 {texts['dash']}")

    client = get_client()
    errors_df = pd.DataFrame()
    try:
        res = client.table("errori_utenti").select("*").eq("user_email", user_email).execute()
        if res.data:
            errors_df = pd.DataFrame(res.data)
    except Exception:
        alert("Impossibile caricare gli errori.", "warn")

    left = remaining_analyses(user_email, tier)
    due = due_count(user_email)
    n_err = len(errors_df)
    n_games = errors_df["partita_id"].nunique() if not errors_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card(texts["quota_left"], left, "gold")
    with c2: metric_card("Errori censiti", n_err, "purple")
    with c3: metric_card("Partite analizzate", n_games, "green")
    with c4: metric_card("Da ripassare", due, "blue")

    if n_err > 0:
        st.markdown("### 🎯 Cluster di errore più frequenti")
        counts = errors_df["categoria_errore"].value_counts().head(10)
        try:
            import plotly.graph_objects as go
            fig = go.Figure(go.Bar(
                x=counts.values, y=counts.index, orientation="h",
                marker_color="#d4af37",
            ))
            fig.update_layout(
                height=340, margin=dict(l=0, r=0, t=10, b=0),
                yaxis=dict(autorange="reversed"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8eaf0",
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.bar_chart(counts)
    else:
        alert("Nessun errore censito. Analizza una partita per iniziare.", "info")
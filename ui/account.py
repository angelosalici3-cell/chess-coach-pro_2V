import streamlit as st

from services.supabase_client import get_client
from services.auth import logout
from ui.components import alert, tier_badge
from config.constants import TIER_PROFILE_LIMIT


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader(f"👤 {texts['account']}")
    st.markdown(
        f"**Email:** `{user_email}` · **Piano:** {tier_badge(tier)}",
        unsafe_allow_html=True,
    )

    st.markdown("### Profili scacchistici")
    client = get_client()
    try:
        profiles = (
            client.table("profili_scacchi").select("*")
            .eq("user_email", user_email).execute().data or []
        )
    except Exception:
        profiles = []

    limit = TIER_PROFILE_LIMIT.get(tier, 1)
    st.caption(f"{len(profiles)}/{limit} profili usati")

    if len(profiles) >= limit:
        alert("Limite profili raggiunto. Passa a Pro o Diamond per aggiungerne altri.", "warn")
    else:
        with st.form("add_profile"):
            plat = st.selectbox("Piattaforma", ["Lichess", "Chess.com"])
            user = st.text_input("Username")
            if st.form_submit_button("Aggiungi"):
                if user.strip():
                    try:
                        client.table("profili_scacchi").insert({
                            "user_email": user_email,
                            "piattaforma": plat,
                            "username": user.strip(),
                        }).execute()
                        st.rerun()
                    except Exception as e:
                        alert(f"Errore: {e}", "danger")

    for p in profiles:
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{p['piattaforma']}** · `{p['username']}`")
        if c2.button("🗑", key=f"del_{p['id']}"):
            client.table("profili_scacchi").delete().eq("id", p["id"]).execute()
            st.rerun()

    st.divider()
    st.markdown("### Zona pericolosa")
    with st.expander("⚠️ Cancella account e tutti i dati"):
        st.warning(texts["confirm_delete"])
        if st.button("Elimina definitivamente il mio account", type="primary"):
            _delete_account(user_email)


def _delete_account(email: str):
    client = get_client()
    try:
        for table in ["errori_utenti", "profili_scacchi", "usage_events",
                      "storico_abbonamenti", "partite_analizzate", "review_items"]:
            client.table(table).delete().eq("user_email", email).execute()
        client.table("config_utenti").delete().eq("user_email", email).execute()
        logout()
        st.success("Account eliminato. Verrai reindirizzato.")
        st.rerun()
    except Exception as e:
        alert(f"Errore cancellazione: {e}", "danger")
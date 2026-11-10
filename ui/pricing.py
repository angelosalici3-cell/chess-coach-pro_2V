import streamlit as st
import stripe

from services.supabase_client import get_client
from services.analytics import track_context, capture_event, Events
from ui.components import alert


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader(f"💎 {texts['pricing']}")

    plans = [
        {"key": "free", "name": "Free", "price": "€0",
         "features": ["5 analisi/mese", "1 profilo", "Analisi base", "PDF 1/mese"]},
        {"key": "pro", "name": "Pro", "price": "€4,99",
         "features": ["200 analisi/mese", "3 profili", "Spiegazione GM AI",
                     "Sync automatico", "PDF illimitati", "Supporto 48h"]},
        {"key": "diamond", "name": "Diamond", "price": "€9,99",
         "features": ["Analisi illimitate", "5 profili", "Priorità su AI",
                     "Supporto 24h", "Tutto di Pro"]},
    ]

    cols = st.columns(3)
    for col, p in zip(cols, plans):
        with col:
            featured = "featured" if p["key"] == tier.lower() else ""
            st.markdown(f"""
            <div class="cc-price-card {featured}">
              <h3>{p['name']}</h3>
              <div class="cc-price-val">{p['price']}</div>
              <ul class="cc-price-features">
                {''.join(f"<li>✓ {f}</li>" for f in p['features'])}
              </ul>
            </div>""", unsafe_allow_html=True)

            if p["key"] == tier.lower():
                st.button("Piano attuale", disabled=True, key=f"b_{p['key']}",
                          use_container_width=True)
            elif p["key"] == "free":
                if st.button("Downgrade", key="b_free", use_container_width=True):
                    _open_billing_portal(user_email)
            else:
                if st.button(f"Scegli {p['name']}", type="primary",
                             key=f"b_{p['key']}", use_container_width=True):
                    _start_checkout(user_email, p["key"])


def _start_checkout(user_email: str, plan: str):
    price_id = (
        st.secrets.get("STRIPE_PRO_PRICE_ID") if plan == "pro"
        else st.secrets.get("STRIPE_DIAMOND_PRICE_ID")
    )
    if not price_id:
        alert("Configurazione Stripe mancante.", "danger")
        return

    with track_context(user_email):
        capture_event(Events.UPGRADE_CLICKED, {"plan": plan})
        capture_event(Events.CHECKOUT_STARTED, {"plan": plan})

    stripe.api_key = st.secrets.get("STRIPE_SECRET_KEY", "")
    base = st.secrets.get("APP_BASE_URL", "http://localhost:8501")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=user_email,
            success_url=f"{base}/?checkout=success",
            cancel_url=f"{base}/?checkout=cancel",
            allow_promotion_codes=True,
            metadata={"plan": plan, "user_email": user_email},
        )
        st.link_button("Apri checkout Stripe →", session.url,
                       use_container_width=True, type="primary")
    except Exception as e:
        alert(f"Errore Stripe: {e}", "danger")


def _open_billing_portal(user_email: str):
    stripe.api_key = st.secrets.get("STRIPE_SECRET_KEY", "")
    base = st.secrets.get("APP_BASE_URL", "http://localhost:8501")
    try:
        client = get_client()
        row = client.table("config_utenti").select("stripe_customer_id").eq("user_email", user_email).execute()
        if not row.data or not row.data[0].get("stripe_customer_id"):
            alert("Nessun abbonamento attivo da gestire.", "info")
            return
        portal = stripe.billing_portal.Session.create(
            customer=row.data[0]["stripe_customer_id"],
            return_url=base,
        )
        st.link_button("Apri portale gestione →", portal.url, type="primary")
    except Exception as e:
        alert(f"Errore portale: {e}", "danger")
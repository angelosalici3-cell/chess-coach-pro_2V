import streamlit as st

st.set_page_config(
    page_title="Chess Coach Pro", page_icon="♟️",
    layout="wide", initial_sidebar_state="expanded",
)

for k, v in {
    "nav": "dashboard", "theme": "dark", "lang": "it",
    "ply": 0, "last_analysis": None, "last_pgn": None,
    "imported_pgns": None, "pgn_input": "",
}.items():
    st.session_state.setdefault(k, v)

from config.i18n import t
from ui.components import apply_styles, alert, tier_badge
from services.auth import current_user, login, signup, logout, reset_password
from services.supabase_client import get_client

apply_styles()

TEXT_KEYS = [
    "app_title", "tagline", "login", "register", "logout", "email", "password",
    "login_btn", "register_btn", "forgot_password", "analyze_btn", "upgrade",
    "settings", "language", "theme", "dark", "light", "dash", "analyze",
    "import", "training", "pricing", "account", "analytics", "srs",
    "quota_left", "quota_exhausted", "confirm_delete", "due_today",
]
texts = {k: t(k, st.session_state["lang"]) for k in TEXT_KEYS}

# ============ LOGIN ============
user = current_user()
if not user:
    st.markdown(f"# ♟️ {texts['app_title']}")
    st.caption(texts["tagline"])
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        tab_login, tab_reg = st.tabs([texts["login"], texts["register"]])
        with tab_login:
            with st.form("login"):
                em = st.text_input(texts["email"])
                pw = st.text_input(texts["password"], type="password")
                if st.form_submit_button(texts["login_btn"], type="primary",
                                         use_container_width=True):
                    ok, msg = login(em, pw)
                    if ok:
                        st.rerun()
                    else:
                        alert(msg, "danger")
            with st.expander(texts["forgot_password"]):
                with st.form("reset"):
                    em2 = st.text_input("Email", key="reset_email")
                    if st.form_submit_button("Invia link"):
                        ok, msg = reset_password(em2)
                        alert(msg, "success" if ok else "danger")
        with tab_reg:
            with st.form("signup"):
                em = st.text_input(texts["email"], key="reg_email")
                pw = st.text_input(texts["password"], type="password", key="reg_pass")
                if st.form_submit_button(texts["register_btn"], type="primary",
                                         use_container_width=True):
                    ok, msg = signup(em, pw)
                    alert(msg, "success" if ok else "danger")
    st.stop()

# ============ APP ============
client = get_client()
try:
    row = client.table("config_utenti").select("*").eq("user_email", user).execute()
    cfg = row.data[0] if row.data else {"tier": "Free"}
except Exception:
    cfg = {"tier": "Free"}
tier = cfg.get("tier", "Free")

with st.sidebar:
    st.markdown(f"**{user}**")
    st.markdown(tier_badge(tier), unsafe_allow_html=True)

    from services.srs import due_count
    n_due = due_count(user)
    if n_due > 0:
        st.markdown(
            f"<div style='background:rgba(212,175,55,.15); padding:6px 10px; "
            f"border-radius:8px; margin-top:8px; font-size:.85rem;'>"
            f"🧠 <b>{n_due}</b> {texts['due_today']}</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    nav_labels = {
        "dashboard": f"📊 {texts['dash']}",
        "analytics": f"📈 {texts['analytics']}",
        "srs": f"🧠 {texts['srs']}",
        "analyze": f"🔍 {texts['analyze']}",
        "import": f"🌐 {texts['import']}",
        "training": f"🎯 {texts['training']}",
        "pricing": f"💎 {texts['pricing']}",
        "account": f"👤 {texts['account']}",
    }
    keys = list(nav_labels.keys())
    labels = [nav_labels[k] for k in keys]
    current_idx = keys.index(st.session_state["nav"]) if st.session_state["nav"] in keys else 0
    choice = st.radio("Navigazione", labels, index=current_idx,
                      label_visibility="collapsed")
    st.session_state["nav"] = keys[labels.index(choice)]

    st.divider()
    st.session_state["lang"] = st.selectbox(
        texts["language"], ["it", "en", "es"],
        index=["it", "en", "es"].index(st.session_state["lang"]),
    )
    st.session_state["theme"] = st.selectbox(
        texts["theme"], ["dark", "light"],
        index=["dark", "light"].index(st.session_state["theme"]),
    )
    if st.button(texts["logout"]):
        logout()
        st.rerun()

nav = st.session_state["nav"]
if nav == "dashboard":
    from ui.dashboard import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "analytics":
    from ui.analytics_dashboard import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "srs":
    from ui.srs_training import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "analyze":
    from ui.analyze import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "import":
    from ui.import_sync import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "training":
    from ui.training import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "pricing":
    from ui.pricing import render; render(user, tier, st.session_state["lang"], texts)
elif nav == "account":
    from ui.account import render; render(user, tier, st.session_state["lang"], texts)
import streamlit as st
from supabase import create_client, Client


def get_client() -> Client:
    """Client per-sessione. NON cachare con st.cache_resource: condividerebbe auth tra utenti."""
    if "supabase_client" not in st.session_state:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            st.error("⚠️ Configurazione Supabase mancante in secrets.toml")
            st.stop()
        st.session_state["supabase_client"] = create_client(url, key)
    return st.session_state["supabase_client"]


def get_service_client() -> Client:
    """Solo per operazioni admin (worker/webhook). Bypassa RLS."""
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return create_client(url, key)
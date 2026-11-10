import streamlit as st
from services.supabase_client import get_client


def current_user() -> str | None:
    client = get_client()
    try:
        session = client.auth.get_session()
        if session and session.user:
            return session.user.email
    except Exception:
        pass
    return None


def login(email: str, password: str) -> tuple[bool, str]:
    client = get_client()
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            return True, res.user.email
        return False, "Credenziali non valide."
    except Exception as e:
        return False, _friendly_error(str(e))


def signup(email: str, password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "La password deve avere almeno 8 caratteri."
    client = get_client()
    try:
        client.auth.sign_up({"email": email, "password": password})
        return True, "Controlla la tua email per confermare l'account."
    except Exception as e:
        return False, _friendly_error(str(e))


def logout():
    client = get_client()
    try:
        client.auth.sign_out()
    except Exception:
        pass
    st.session_state.pop("supabase_client", None)


def reset_password(email: str) -> tuple[bool, str]:
    client = get_client()
    try:
        client.auth.reset_password_for_email(email)
        return True, "Email inviata. Controlla la casella."
    except Exception as e:
        return False, _friendly_error(str(e))


def _friendly_error(msg: str) -> str:
    low = msg.lower()
    if "invalid login" in low or "invalid credentials" in low:
        return "Email o password errati."
    if "already registered" in low or "user already" in low:
        return "Email già registrata."
    if "email" in low and "invalid" in low:
        return "Formato email non valido."
    return "Errore di autenticazione. Riprova."
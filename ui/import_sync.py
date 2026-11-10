import io
import chess
import chess.pgn
import httpx
import streamlit as st

from config.constants import USER_AGENT
from services.supabase_client import get_client
from services.analytics import track_context, capture_event, Events
from ui.components import alert


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader(f"🌐 {texts['import']}")

    client = get_client()
    profiles = []
    try:
        res = client.table("profili_scacchi").select("*").eq("user_email", user_email).execute()
        profiles = res.data or []
    except Exception:
        alert("Impossibile caricare i profili.", "warn")

    if not profiles:
        alert("Aggiungi prima un profilo dalla sezione Account.", "info")
        return

    labels = [f"{p['piattaforma']}: {p['username']}" for p in profiles]
    sel = st.selectbox("Account", labels)
    n = st.number_input("Partite da scaricare", 5, 30, 10)
    idx = labels.index(sel)
    platform, username = profiles[idx]["piattaforma"], profiles[idx]["username"]

    if st.button("Scarica partite", type="primary"):
        with st.spinner("Scaricamento…"):
            pgns = _download(platform, username, int(n))
        if not pgns:
            alert("Nessuna partita trovata o errore di download.", "warn")
            return
        st.session_state["imported_pgns"] = pgns
        alert(f"✅ {len(pgns)} partite scaricate.", "success")
        with track_context(user_email):
            capture_event(Events.IMPORT_COMPLETED, {
                "platform": platform, "games_count": len(pgns),
            })

    if st.session_state.get("imported_pgns"):
        options = []
        for i, p in enumerate(st.session_state["imported_pgns"]):
            g = chess.pgn.read_game(io.StringIO(p))
            if g:
                h = g.headers
                options.append(f"{i}: {h.get('White','?')} vs {h.get('Black','?')} ({h.get('Date','?')})")
        if options:
            pick = st.selectbox("Partita", options)
            sel_idx = int(pick.split(":")[0])
            if st.button("Analizza questa partita", type="primary"):
                st.session_state["pgn_input"] = st.session_state["imported_pgns"][sel_idx]
                st.session_state["nav"] = "analyze"
                st.rerun()


def _download(platform: str, username: str, n: int) -> list[str]:
    headers = {"User-Agent": USER_AGENT}
    try:
        with httpx.Client(timeout=25.0) as c:
            if platform == "Lichess":
                r = c.get(
                    f"https://lichess.org/api/games/user/{username.lower()}",
                    params={"max": n},
                    headers={**headers, "Accept": "application/x-chess-pgn"},
                )
                if r.status_code != 200:
                    return []
                raw = r.text
                return ["[Event " + p if not p.startswith("[Event") else p
                        for p in raw.split("\n[Event ") if p.strip()]
            if platform == "Chess.com":
                r = c.get(
                    f"https://api.chess.com/pub/player/{username.lower()}/games/archives",
                    headers=headers,
                )
                if r.status_code != 200:
                    return []
                archives = r.json().get("archives", [])
                if not archives:
                    return []
                g = c.get(archives[-1], headers=headers)
                games = g.json().get("games", [])[-n:][::-1]
                return [x["pgn"] for x in games if x.get("pgn")]
    except Exception:
        return []
    return []
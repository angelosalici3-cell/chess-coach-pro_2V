import datetime

import chess
import chess.svg
import streamlit as st

from services.srs import due_items, due_count, submit_review, stats, ReviewItem
from services.analytics import track_context, capture_event, Events
from services.supabase_client import get_client
from ui.components import alert, metric_card


def render(user_email: str, tier: str, lang: str, texts: dict):
    st.subheader("🧠 Ripasso Spaziato")

    with track_context(user_email):
        capture_event(Events.PAGE_VIEWED, {"page": "srs_training", "tier": tier})

    s = stats(user_email)
    due = due_count(user_email)

    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Da ripassare", due, "gold")
    with c2: metric_card("Items totali", s["total_items"], "blue")
    with c3: metric_card("Accuracy", f"{s['accuracy']}%", "green")
    with c4: metric_card("Intervallo medio", f"{s['avg_interval']}g", "purple")

    st.divider()

    if due == 0:
        alert("✅ Nessun ripasso dovuto oggi. Torna domani o analizza nuove partite.", "success")
        _render_upcoming(user_email)
        return

    items = due_items(user_email, limit=20)
    if not items:
        alert("Errore caricamento items.", "warn")
        return

    if "srs_index" not in st.session_state:
        st.session_state["srs_index"] = 0
    if "srs_feedback" not in st.session_state:
        st.session_state["srs_feedback"] = None
    if "srs_completed_shown" not in st.session_state:
        st.session_state["srs_completed_shown"] = False

    idx = st.session_state["srs_index"]
    if idx >= len(items):
        if not st.session_state["srs_completed_shown"]:
            st.balloons()
            st.session_state["srs_completed_shown"] = True
            with track_context(user_email):
                capture_event(Events.SRS_SESSION_STARTED, {
                    "items": len(items), "session": "completed",
                })
        alert("🎉 Sessione completata! Ottimo lavoro.", "success")
        if st.button("Ricomincia", use_container_width=True):
            st.session_state["srs_index"] = 0
            st.session_state["srs_feedback"] = None
            st.session_state["srs_completed_shown"] = False
            st.rerun()
        return

    item = items[idx]
    st.progress((idx + 1) / len(items), text=f"Puzzle {idx + 1} di {len(items)}")
    _render_puzzle(item, idx)

    if st.session_state["srs_feedback"]:
        fb = st.session_state["srs_feedback"]
        if fb["correct"]:
            alert(f"✅ Corretto! La soluzione era <b>{item.solution_san}</b>.", "success")
        else:
            alert(
                f"❌ La soluzione corretta era <b>{item.solution_san}</b> "
                f"(tu hai giocato: {fb['played']}).",
                "danger",
            )

        st.markdown("**Quanto è stato difficile?**")
        qc1, qc2, qc3 = st.columns(3)
        with qc1:
            if st.button("😊 Facile", use_container_width=True):
                _finalize(user_email, item, quality=5, correct=fb["correct"])
        with qc2:
            if st.button("😐 Medio", use_container_width=True):
                _finalize(user_email, item, quality=3, correct=fb["correct"])
        with qc3:
            if st.button("😰 Difficile", use_container_width=True):
                _finalize(user_email, item, quality=1, correct=fb["correct"])


def _render_puzzle(item: ReviewItem, idx: int):
    board = chess.Board(item.fen)
    svg = chess.svg.board(
        board=board, size=400,
        colors={"square light": "#ebecd0", "square dark": "#739552"},
    )
    st.markdown(f"<div class='cc-board'>{svg}</div>", unsafe_allow_html=True)

    st.markdown(
        f"**Cluster:** `{item.category or '—'}` &nbsp;·&nbsp; "
        f"**Tu avevi giocato:** `{item.user_move_san or '—'}`"
    )
    st.caption("Trova la mossa migliore in questa posizione.")

    legal_sans = sorted(board.san(m) for m in board.legal_moves)

    if not st.session_state.get("srs_feedback"):
        choice = st.selectbox(
            "La tua mossa:", legal_sans,
            key=f"srs_choice_{idx}_{item.id}",
        )
        if st.button("Verifica", type="primary", use_container_width=True):
            correct = (choice == item.solution_san)
            st.session_state["srs_feedback"] = {"correct": correct, "played": choice}
            st.rerun()


def _finalize(user_email: str, item: ReviewItem, quality: int, correct: bool):
    update = submit_review(item, quality=quality, correct=correct)
    with track_context(user_email):
        capture_event(Events.SRS_REVIEW_SUBMITTED, {
            "item_id": item.id, "quality": quality, "correct": correct,
            "new_interval": update["interval_days"],
            "new_ease": update["ease_factor"],
        })
    st.session_state["srs_index"] += 1
    st.session_state["srs_feedback"] = None
    st.toast(f"Prossimo ripasso tra {update['interval_days']}g (EF {update['ease_factor']})")
    st.rerun()


def _render_upcoming(user_email: str):
    client = get_client()
    try:
        res = (
            client.table("review_items")
            .select("next_review_at, category")
            .eq("user_email", user_email)
            .order("next_review_at", desc=False)
            .limit(5)
            .execute()
        )
        upcoming = res.data or []
    except Exception:
        return

    if not upcoming:
        return

    st.markdown("### 📅 Prossimi ripassi")
    for u in upcoming:
        try:
            dt = datetime.datetime.fromisoformat(u["next_review_at"].replace("Z", "+00:00"))
            delta = (dt - datetime.datetime.now(datetime.timezone.utc)).days
            st.caption(f"• **{u.get('category', '—')}** — tra {max(0, delta)} giorni")
        except Exception:
            pass
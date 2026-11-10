from contextlib import contextmanager

import posthog
import streamlit as st


def init_posthog():
    if "posthog_initialized" not in st.session_state:
        api_key = st.secrets.get("POSTHOG_API_KEY", "")
        host = st.secrets.get("POSTHOG_HOST", "https://eu.i.posthog.com")
        if api_key:
            posthog.api_key = api_key
            posthog.host = host
        st.session_state["posthog_initialized"] = True


@contextmanager
def track_context(user_email: str, session_id: str | None = None):
    init_posthog()
    try:
        from posthog import new_context, identify_context, set_context_session
        with new_context():
            if user_email:
                identify_context(user_email)
            if session_id:
                set_context_session(session_id)
            yield
    except Exception:
        yield


def capture_event(event_name: str, properties: dict | None = None):
    try:
        posthog.capture(event_name, properties=properties or {})
    except Exception:
        pass


class Events:
    GAME_ANALYZED = "game_analyzed"
    ANALYSIS_CACHED_HIT = "analysis_cache_hit"
    ANALYSIS_QUOTA_EXCEEDED = "analysis_quota_exceeded"
    ERROR_CLUSTER_VIEWED = "error_cluster_viewed"
    GM_LESSON_REQUESTED = "gm_lesson_requested"
    PROFILE_ADDED = "profile_added"
    IMPORT_COMPLETED = "import_completed"
    UPGRADE_CLICKED = "upgrade_clicked"
    CHECKOUT_STARTED = "checkout_started"
    TRAINING_SESSION_STARTED = "training_session_started"
    SRS_SESSION_STARTED = "srs_session_started"
    SRS_REVIEW_SUBMITTED = "srs_review_submitted"
    PDF_EXPORTED = "pdf_exported"
    PAGE_VIEWED = "page_viewed"
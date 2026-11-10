import streamlit as st
from typing import Literal


def apply_styles():
    with open("assets/style.css", "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def metric_card(label: str, value, accent: Literal["gold", "blue", "purple", "green"] = "gold"):
    colors = {"gold": "#d4af37", "blue": "#3b82f6", "purple": "#a855f7", "green": "#10b981"}
    st.markdown(
        f"""<div class="cc-metric" style="border-left-color:{colors[accent]};">
        <div class="cc-metric-val">{value}</div>
        <div class="cc-metric-lbl">{label}</div></div>""",
        unsafe_allow_html=True,
    )


def tier_badge(tier: str) -> str:
    cls = {"Free": "free", "Pro": "pro", "Diamond": "diamond"}.get(tier, "free")
    return f"<span class='cc-badge {cls}'>{tier}</span>"


def alert(text: str, kind: Literal["info", "success", "warn", "danger"] = "info"):
    st.markdown(f"<div class='cc-alert {kind}'>{text}</div>", unsafe_allow_html=True)


def board_svg(board, size: int = 400) -> str:
    import chess.svg
    svg = chess.svg.board(
        board=board, size=size,
        colors={"square light": "#ebecd0", "square dark": "#739552"},
    )
    return f"<div class='cc-board'>{svg}</div>"
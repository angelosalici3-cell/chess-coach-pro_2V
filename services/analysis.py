import hashlib
import io
import json

import chess
import chess.pgn
import httpx
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
import streamlit as st

from config.constants import (
    ERROR_CATEGORIES, GEMINI_MODEL, STOCKFISH_API_URL, USER_AGENT,
    BLUNDER_THRESHOLD, MISTAKE_THRESHOLD, INACCURACY_THRESHOLD,
)
from services.supabase_client import get_client


def pgn_hash(pgn: str) -> str:
    return hashlib.sha256(pgn.strip().encode("utf-8")).hexdigest()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=4))
def _stockfish_eval(fen: str, depth: int) -> float | None:
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.post(STOCKFISH_API_URL, json={"fen": fen, "depth": depth},
                       headers={"User-Agent": USER_AGENT})
            if r.status_code != 200:
                return None
            data = r.json()
            for k, div in (("eval", 1), ("centipawns", 100), ("cp", 100), ("value", 100)):
                if data.get(k) is not None:
                    return float(data[k]) / div
            if data.get("mate") is not None:
                m = int(data["mate"])
                return 100.0 if m > 0 else -100.0
            return None
    except Exception:
        return None


def best_move_from_fen(fen: str, depth: int = 14) -> tuple[str | None, str | None]:
    """Ritorna (uci, san) della mossa migliore."""
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.post(STOCKFISH_API_URL, json={"fen": fen, "depth": depth},
                       headers={"User-Agent": USER_AGENT})
            if r.status_code != 200:
                return None, None
            data = r.json()
            uci = data.get("bestmove") or data.get("move") or data.get("best_move")
            if not uci or not isinstance(uci, str):
                return None, None
            try:
                board = chess.Board(fen)
                san = board.san(chess.Move.from_uci(uci))
            except Exception:
                san = uci
            return uci, san
    except Exception:
        return None, None


def _classify_error(fen: str, san: str, api_key: str) -> str:
    if not api_key:
        return "Positional Weakness"

    prompt = f"""Sei un GM. Classifica l'errore in UNA categoria:
{', '.join(ERROR_CATEGORIES)}.
FEN: {fen}
Mossa errata: {san}
Rispondi SOLO JSON: {{"categoria": "..."}}"""

    try:
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )
        data = json.loads(resp.text)
        cat = data.get("categoria", "").strip()
        for valid in ERROR_CATEGORIES:
            if valid.lower() == cat.lower() or valid.lower() in cat.lower():
                return valid
        return "Positional Weakness"
    except Exception:
        return "Positional Weakness"


def analyze_pgn(
    pgn_text: str,
    target_usernames: list[str],
    depth: int = 12,
    progress_cb=None,
) -> dict:
    ph = pgn_hash(pgn_text)
    try:
        cache = get_client().table("analyses_cache").select("*").eq("pgn_sha256", ph).execute()
        if cache.data:
            row = cache.data[0]
            return {
                "errors": row["errors_json"],
                "eval_history": row["eval_history"],
                "partita_id": row.get("partita_id"),
                "cached": True,
            }
    except Exception:
        pass

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        raise ValueError("PGN non valido.")

    headers = game.headers
    white = headers.get("White", "?").strip().lower()
    black = headers.get("Black", "?").strip().lower()
    partita_id = f"{headers.get('White','?')}_vs_{headers.get('Black','?')}_{headers.get('Date','Live')}"

    if target_usernames:
        ul = [u.strip().lower() for u in target_usernames]
        user_is_white = any(u in white for u in ul)
        user_is_black = any(u in black for u in ul)
        if not user_is_white and not user_is_black:
            user_is_white = user_is_black = True
    else:
        user_is_white = user_is_black = True

    board = game.board()
    moves = list(game.mainline_moves())
    total = len(moves)
    eval_history, errors = [], []
    prev_eval = 0.0
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    evals_cache: dict[str, float] = {}

    def get_eval(fen: str) -> float:
        if fen in evals_cache:
            return evals_cache[fen]
        e = _stockfish_eval(fen, depth)
        if e is None:
            e = prev_eval
        evals_cache[fen] = e
        return e

    for idx, move in enumerate(moves):
        fen_before = board.fen()
        try:
            san = board.san(move)
        except Exception:
            san = move.uci()

        eval_before = get_eval(fen_before)
        board.push(move)
        fen_after = board.fen()
        eval_after = get_eval(fen_after)

        num = (idx // 2) + 1
        is_white = (idx % 2 == 0)

        eval_history.append({
            "ply": idx + 1, "num_move": num, "san": san,
            "eval_cp": eval_after, "eval_clamped": max(min(eval_after, 10), -10),
            "is_white": is_white,
        })

        is_user = (is_white and user_is_white) or (not is_white and user_is_black)
        if is_user:
            delta = (eval_before - eval_after) if is_white else (eval_after - eval_before)
            tipo = None
            if delta >= BLUNDER_THRESHOLD:
                tipo = "🔴 Blunder"
            elif delta >= MISTAKE_THRESHOLD:
                tipo = "🟠 Mistake"
            elif delta >= INACCURACY_THRESHOLD:
                tipo = "🟡 Inaccuracy"
            if tipo:
                label = f"{num}. {san}" if is_white else f"{num}... {san}"
                cat = _classify_error(fen_before, san, api_key)
                errors.append({
                    "mossa_num": idx + 1, "label_mossa": label,
                    "fen_prima": fen_before, "fen_dopo": fen_after,
                    "mossa_giocata": move.uci(), "perdita_cp": round(delta, 2),
                    "eval_dopo": eval_after, "tipo_problema": tipo, "categoria": cat,
                })

        prev_eval = eval_after
        if progress_cb and total:
            progress_cb((idx + 1) / total)

    try:
        get_client().table("analyses_cache").insert({
            "pgn_sha256": ph, "pgn_text": pgn_text,
            "eval_history": eval_history, "errors_json": errors,
            "partita_id": partita_id,
        }).execute()
    except Exception:
        pass

    return {"errors": errors, "eval_history": eval_history,
            "partita_id": partita_id, "cached": False}


def create_review_items_from_errors(user_email: str, error_rows: list[dict]) -> int:
    client = get_client()
    created = 0
    for row in error_rows:
        fen = row.get("fen_prima")
        if not fen:
            continue
        uci, san = best_move_from_fen(fen)
        if not san:
            continue
        label = row.get("mossa_critica", "")
        user_san = label.split()[-1] if " " in label else label
        try:
            client.table("review_items").upsert({
                "user_email": user_email,
                "source_error_id": row["id"],
                "fen": fen,
                "solution_uci": uci,
                "solution_san": san,
                "user_move_san": user_san,
                "category": row.get("categoria_errore"),
            }, on_conflict="user_email,source_error_id").execute()
            created += 1
        except Exception:
            pass
    return created
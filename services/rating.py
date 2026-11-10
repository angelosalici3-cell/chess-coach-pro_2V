import io
import pandas as pd
import chess.pgn
from services.supabase_client import get_client


def extract_and_save(
    user_email: str,
    pgn_text: str,
    partita_id: str,
    user_usernames: list[str],
    errors: list[dict],
) -> bool:
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        return False

    h = game.headers
    white = h.get("White", "?").strip()
    black = h.get("Black", "?").strip()
    w_elo = _to_int(h.get("WhiteElo"))
    b_elo = _to_int(h.get("BlackElo"))
    result = h.get("Result", "*")
    date_str = h.get("Date", "").replace(".", "-") if h.get("Date") else None
    if date_str and date_str.count("-") != 2:
        date_str = None
    if date_str and "?" in date_str:
        date_str = None

    ul = [u.strip().lower() for u in user_usernames]
    is_white = any(u in white.lower() for u in ul)
    is_black = any(u in black.lower() for u in ul)

    if is_white and not is_black:
        user_color, user_elo, opp_elo = "white", w_elo, b_elo
    elif is_black and not is_white:
        user_color, user_elo, opp_elo = "black", b_elo, w_elo
    else:
        return False

    if user_elo is None or opp_elo is None:
        return False

    blunders = sum(1 for e in errors if "Blunder" in e.get("tipo_problema", ""))
    mistakes = sum(1 for e in errors if "Mistake" in e.get("tipo_problema", ""))
    inaccuracies = sum(1 for e in errors if "Inaccuracy" in e.get("tipo_problema", ""))
    accuracy = _compute_accuracy(errors)

    client = get_client()
    try:
        client.table("partite_analizzate").upsert({
            "user_email": user_email,
            "partita_id": partita_id,
            "data_partita": date_str,
            "white_player": white,
            "black_player": black,
            "user_color": user_color,
            "user_elo": user_elo,
            "opponent_elo": opp_elo,
            "user_rating_diff": user_elo - opp_elo,
            "result": result,
            "time_control": h.get("TimeControl"),
            "termination": h.get("Termination"),
            "accuracy": accuracy,
            "blunders": blunders,
            "mistakes": mistakes,
            "inaccuracies": inaccuracies,
        }, on_conflict="user_email,partita_id").execute()
        return True
    except Exception:
        return False


def load_trend(user_email: str) -> pd.DataFrame:
    client = get_client()
    try:
        res = (
            client.table("partite_analizzate")
            .select("data_partita, user_elo, opponent_elo, result, user_color, accuracy, blunders")
            .eq("user_email", user_email)
            .not_.is_("user_elo", "null")
            .order("data_partita", desc=False)
            .execute()
        )
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        df["data_partita"] = pd.to_datetime(df["data_partita"])
        df["outcome"] = df.apply(_outcome, axis=1)
        return df
    except Exception:
        return pd.DataFrame()


def _outcome(row) -> str:
    r = row.get("result")
    c = row.get("user_color")
    if r == "1/2-1/2":
        return "D"
    if (c == "white" and r == "1-0") or (c == "black" and r == "0-1"):
        return "W"
    if r in ("1-0", "0-1"):
        return "L"
    return "?"


def _compute_accuracy(errors: list[dict]) -> float:
    if not errors:
        return 100.0
    losses = [e.get("perdita_cp", 0) for e in errors]
    avg = sum(losses) / len(losses)
    return round(max(0, min(100, 100 - avg * 2)), 1)


def _to_int(v) -> int | None:
    try:
        return int(v) if v not in (None, "", "?") else None
    except Exception:
        return None
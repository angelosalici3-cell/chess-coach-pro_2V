"""
Worker di sincronizzazione notturna.
Deploy: Railway/Render cron job giornaliero.
Richiede SERVICE_ROLE key (bypassa RLS).
"""
import datetime
import io
import os
import time

import chess
import chess.pgn
import httpx
from supabase import create_client

URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
UA = "ChessCoachProWorker/3.0"

sb = create_client(URL, KEY)


def _eval(fen: str, depth: int = 10) -> float | None:
    for _ in range(3):
        try:
            r = httpx.post(
                "https://chess-api.com/v1",
                json={"fen": fen, "depth": depth},
                headers={"User-Agent": UA}, timeout=10,
            )
            if r.status_code == 200:
                d = r.json()
                for k, div in (("eval", 1), ("centipawns", 100), ("cp", 100)):
                    if d.get(k) is not None:
                        return float(d[k]) / div
                if d.get("mate") is not None:
                    return 100.0 if int(d["mate"]) > 0 else -100.0
        except Exception:
            time.sleep(1)
    return None


def _best_move(fen: str, depth: int = 14) -> tuple:
    try:
        r = httpx.post(
            "https://chess-api.com/v1",
            json={"fen": fen, "depth": depth},
            headers={"User-Agent": UA}, timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            uci = d.get("bestmove") or d.get("move") or d.get("best_move")
            if uci:
                try:
                    b = chess.Board(fen)
                    return uci, b.san(chess.Move.from_uci(uci))
                except Exception:
                    return uci, uci
    except Exception:
        pass
    return None, None


def _classify(fen: str, san: str) -> str:
    if not GEMINI_KEY:
        return "Positional Weakness"
    try:
        from google import genai
        from google.genai import types
        import json
        client = genai.Client(api_key=GEMINI_KEY)
        resp = client.models.generate_content(
            model=MODEL,
            contents=(
                f'FEN:{fen} SAN:{san}. Rispondi JSON: {{"categoria":"..."}} '
                "scegliendo tra Fork,Pin,Skewer,Hanging Piece,Mate in 1,"
                "Mate in 2,Endgame,Opening Mistake,Positional Weakness."
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0,
            ),
        )
        return json.loads(resp.text).get("categoria", "Positional Weakness")
    except Exception:
        return "Positional Weakness"


def process_game(user_email: str, pgn: str, username: str):
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return
    h = game.headers
    partita_id = f"{h.get('White','?')}_vs_{h.get('Black','?')}_{h.get('Date','Live')}"

    existing = (
        sb.table("errori_utenti").select("id")
        .eq("user_email", user_email).eq("partita_id", partita_id).execute()
    )
    if existing.data:
        return

    user_is_white = username.lower() in h.get("White", "").lower()
    user_is_black = username.lower() in h.get("Black", "").lower()
    if not (user_is_white or user_is_black):
        return

    board = game.board()
    prev = 0.0
    for idx, move in enumerate(game.mainline_moves()):
        fen_before = board.fen()
        san = board.san(move)
        eb = _eval(fen_before) or prev
        board.push(move)
        ea = _eval(board.fen()) or eb
        is_white = idx % 2 == 0
        is_user = (is_white and user_is_white) or (not is_white and user_is_black)
        if is_user:
            delta = (eb - ea) if is_white else (ea - eb)
            if delta >= 1.0:
                tipo = "Blunder" if delta >= 2.0 else "Mistake"
                label = f"{(idx//2)+1}. {san}" if is_white else f"{(idx//2)+1}... {san}"
                categoria = _classify(fen_before, san)
                try:
                    res = sb.table("errori_utenti").insert({
                        "user_email": user_email,
                        "partita_id": partita_id,
                        "data": datetime.date.today().isoformat(),
                        "categoria_errore": categoria,
                        "mossa_critica": label,
                        "spiegazione": f"Perdita {round(delta, 2)} CP ({tipo})",
                        "fen_prima": fen_before,
                        "perdita_cp": round(delta, 2),
                    }).execute()
                    if res.data:
                        err_id = res.data[0]["id"]
                        uci, sol_san = _best_move(fen_before)
                        if sol_san:
                            sb.table("review_items").upsert({
                                "user_email": user_email,
                                "source_error_id": err_id,
                                "fen": fen_before,
                                "solution_uci": uci,
                                "solution_san": sol_san,
                                "user_move_san": san,
                                "category": categoria,
                            }, on_conflict="user_email,source_error_id").execute()
                except Exception:
                    pass
        prev = ea
        time.sleep(0.05)


def fetch_games(platform: str, user: str, n: int = 5) -> list[str]:
    try:
        with httpx.Client(timeout=25, headers={"User-Agent": UA}) as c:
            if platform == "Lichess":
                r = c.get(
                    f"https://lichess.org/api/games/user/{user.lower()}",
                    params={"max": n},
                    headers={"Accept": "application/x-chess-pgn"},
                )
                if r.status_code != 200:
                    return []
                return ["[Event " + p if not p.startswith("[Event") else p
                        for p in r.text.split("\n[Event ") if p.strip()]
            if platform == "Chess.com":
                r = c.get(
                    f"https://api.chess.com/pub/player/{user.lower()}/games/archives"
                )
                if r.status_code != 200:
                    return []
                arch = r.json().get("archives", [])
                if not arch:
                    return []
                g = c.get(arch[-1])
                return [x["pgn"] for x in g.json().get("games", [])[-n:] if x.get("pgn")]
    except Exception:
        return []
    return []


def main():
    print("[worker] start", datetime.datetime.utcnow().isoformat())
    subs = (
        sb.table("config_utenti").select("user_email, data_scadenza")
        .in_("tier", ["Pro", "Diamond"]).execute()
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    for row in (subs.data or []):
        if row.get("data_scadenza"):
            exp = datetime.datetime.fromisoformat(
                row["data_scadenza"].replace("Z", "+00:00")
            )
            if exp < now:
                continue
        email = row["user_email"]
        profs = (
            sb.table("profili_scacchi").select("*")
            .eq("user_email", email).execute().data or []
        )
        for p in profs:
            for pgn in fetch_games(p["piattaforma"], p["username"], 5):
                process_game(email, pgn, p["username"])
    print("[worker] done")


if __name__ == "__main__":
    main()
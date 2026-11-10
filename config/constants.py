import os

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

STOCKFISH_API_URL = "https://chess-api.com/v1"
STOCKFISH_DEPTH = {"Free": 8, "Pro": 14, "Diamond": 18}

TIER_PROFILE_LIMIT = {"Free": 1, "Pro": 3, "Diamond": 5}
TIER_MONTHLY_ANALYSES = {
    "Free": int(os.getenv("FREE_MONTHLY_ANALYSES", "5")),
    "Pro": int(os.getenv("PRO_MONTHLY_ANALYSES", "200")),
    "Diamond": 99999,
}

ERROR_CATEGORIES = [
    "Fork", "Pin", "Skewer", "Hanging Piece", "Discovered Attack",
    "Double Check", "Interference", "Clearance", "Zugzwang",
    "Mate in 1", "Mate in 2", "Mate in 3+", "Back Rank Mate",
    "Smothered Mate", "Endgame", "Quiet Move", "Defensive Move",
    "Opening Mistake", "Positional Weakness",
]

BLUNDER_THRESHOLD = 2.0
MISTAKE_THRESHOLD = 1.0
INACCURACY_THRESHOLD = 0.5

USER_AGENT = "ChessCoachPro/3.0 (support@chesscoachpro.com)"
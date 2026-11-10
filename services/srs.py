import datetime
from dataclasses import dataclass

from services.supabase_client import get_client


MIN_EASE = 1.30
DEFAULT_EASE = 2.50


@dataclass
class ReviewItem:
    id: int
    fen: str
    solution_san: str | None
    solution_uci: str | None
    user_move_san: str | None
    category: str | None
    ease_factor: float
    interval_days: int
    repetitions: int
    next_review_at: str


def calculate_next(quality: int, ease: float, interval: int, reps: int) -> dict:
    assert 0 <= quality <= 5

    new_ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if new_ease < MIN_EASE:
        new_ease = MIN_EASE

    if quality < 3:
        new_reps = 0
        new_interval = 1
    else:
        new_reps = reps + 1
        if reps == 0:
            new_interval = 1
        elif reps == 1:
            new_interval = 6
        else:
            new_interval = max(1, round(interval * new_ease))

    next_review = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=new_interval)

    return {
        "ease_factor": round(new_ease, 2),
        "interval_days": new_interval,
        "repetitions": new_reps,
        "next_review_at": next_review.isoformat(),
    }


def due_items(user_email: str, limit: int = 20) -> list[ReviewItem]:
    client = get_client()
    try:
        res = (
            client.table("review_items")
            .select("*")
            .eq("user_email", user_email)
            .lte("next_review_at", datetime.datetime.now(datetime.timezone.utc).isoformat())
            .order("next_review_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [
            ReviewItem(
                id=r["id"],
                fen=r["fen"],
                solution_san=r.get("solution_san"),
                solution_uci=r.get("solution_uci"),
                user_move_san=r.get("user_move_san"),
                category=r.get("category"),
                ease_factor=float(r["ease_factor"]),
                interval_days=int(r["interval_days"]),
                repetitions=int(r["repetitions"]),
                next_review_at=r["next_review_at"],
            )
            for r in (res.data or [])
        ]
    except Exception:
        return []


def due_count(user_email: str) -> int:
    client = get_client()
    try:
        res = (
            client.table("review_items")
            .select("id", count="exact")
            .eq("user_email", user_email)
            .lte("next_review_at", datetime.datetime.now(datetime.timezone.utc).isoformat())
            .execute()
        )
        return res.count or 0
    except Exception:
        return 0


def submit_review(item: ReviewItem, quality: int, correct: bool) -> dict:
    client = get_client()
    update = calculate_next(
        quality=quality,
        ease=item.ease_factor,
        interval=item.interval_days,
        reps=item.repetitions,
    )
    try:
        client.rpc("increment_review_stats", {
            "p_item_id": item.id,
            "p_correct": correct,
        }).execute()
        client.table("review_items").update({
            "ease_factor": update["ease_factor"],
            "interval_days": update["interval_days"],
            "repetitions": update["repetitions"],
            "next_review_at": update["next_review_at"],
            "last_reviewed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "last_quality": quality,
        }).eq("id", item.id).execute()
    except Exception:
        pass
    return update


def stats(user_email: str) -> dict:
    client = get_client()
    try:
        res = (
            client.table("review_items")
            .select("total_reviews, correct_reviews, interval_days, ease_factor")
            .eq("user_email", user_email)
            .execute()
        )
        rows = res.data or []
        total = sum(r["total_reviews"] for r in rows)
        correct = sum(r["correct_reviews"] for r in rows)
        return {
            "total_items": len(rows),
            "total_reviews": total,
            "correct_reviews": correct,
            "accuracy": round(correct / total * 100, 1) if total else 0.0,
            "avg_interval": round(sum(r["interval_days"] for r in rows) / len(rows), 1) if rows else 0,
            "avg_ease": round(sum(r["ease_factor"] for r in rows) / len(rows), 2) if rows else DEFAULT_EASE,
        }
    except Exception:
        return {"total_items": 0, "total_reviews": 0, "correct_reviews": 0,
                "accuracy": 0.0, "avg_interval": 0, "avg_ease": DEFAULT_EASE}
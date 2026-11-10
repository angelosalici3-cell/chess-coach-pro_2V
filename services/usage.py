import datetime
from services.supabase_client import get_client
from config.constants import TIER_MONTHLY_ANALYSES


def remaining_analyses(user_email: str, tier: str) -> int:
    limit = TIER_MONTHLY_ANALYSES.get(tier, 5)
    if limit >= 99999:
        return 99999
    client = get_client()
    month_start = datetime.datetime.now(datetime.timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    try:
        res = (
            client.table("usage_events")
            .select("id", count="exact")
            .eq("user_email", user_email)
            .eq("action", "analysis")
            .gte("created_at", month_start)
            .execute()
        )
        used = res.count or 0
        return max(0, limit - used)
    except Exception:
        return limit


def record_analysis(user_email: str, partita_id: str):
    client = get_client()
    try:
        client.table("usage_events").insert({
            "user_email": user_email,
            "action": "analysis",
            "metadata": {"partita_id": partita_id},
        }).execute()
    except Exception:
        pass
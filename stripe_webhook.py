"""
Stripe webhook — deploy su Railway/Fly/Render.
Configura in Stripe Dashboard → Developers → Webhooks:
URL: https://tuo-webhook.com/webhook
Eventi: checkout.session.completed, customer.subscription.updated,
        customer.subscription.deleted
"""
import datetime
import os

import stripe
from fastapi import FastAPI, Request, HTTPException
from supabase import create_client

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

PLAN_BY_PRICE = {
    os.environ.get("STRIPE_PRO_PRICE_ID", ""): "Pro",
    os.environ.get("STRIPE_DIAMOND_PRICE_ID", ""): "Diamond",
}

app = FastAPI()


@app.post("/webhook")
async def webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(400, f"Signature error: {e}")

    obj = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        email = obj.get("customer_email") or obj.get("customer_details", {}).get("email")
        customer = obj.get("customer")
        sub_id = obj.get("subscription")
        if email and sub_id:
            sub = stripe.Subscription.retrieve(sub_id)
            price_id = sub["items"]["data"][0]["price"]["id"]
            tier = PLAN_BY_PRICE.get(price_id, "Pro")
            _set_tier(email, tier, customer, sub_id, sub["current_period_end"])

    elif event["type"] == "customer.subscription.updated":
        customer = obj.get("customer")
        sub_id = obj.get("id")
        status = obj.get("status")
        price_id = obj["items"]["data"][0]["price"]["id"]
        tier = PLAN_BY_PRICE.get(price_id, "Pro")
        email = _email_from_customer(customer)
        if not email:
            return {"ok": True}
        if status in ("active", "trialing"):
            _set_tier(email, tier, customer, sub_id, obj.get("current_period_end"))
        elif status in ("canceled", "unpaid", "past_due", "incomplete_expired"):
            _set_tier(email, "Free", customer, None, None)

    elif event["type"] == "customer.subscription.deleted":
        customer = obj.get("customer")
        email = _email_from_customer(customer)
        if email:
            _set_tier(email, "Free", customer, None, None)

    return {"ok": True}


def _email_from_customer(customer_id: str) -> str | None:
    try:
        cust = stripe.Customer.retrieve(customer_id)
        return cust.get("email")
    except Exception:
        return None


def _set_tier(email: str, tier: str, customer: str | None,
              sub_id: str | None, period_end: int | None):
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = datetime.datetime.fromtimestamp(
        period_end, tz=datetime.timezone.utc
    ) if period_end else None

    sb.table("config_utenti").upsert({
        "user_email": email,
        "tier": tier,
        "data_scadenza": exp.isoformat() if exp else None,
        "stripe_customer_id": customer,
        "stripe_subscription_id": sub_id,
        "updated_at": now.isoformat(),
    }).execute()

    if tier != "Free":
        sb.table("storico_abbonamenti").insert({
            "user_email": email,
            "tier": tier,
            "data_inizio": now.isoformat(),
            "data_scadenza": exp.isoformat() if exp else None,
            "stato": "attivo",
            "stripe_subscription_id": sub_id,
        }).execute()
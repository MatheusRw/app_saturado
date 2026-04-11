import stripe
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from .database import SessionLocal, User
import os

router = APIRouter(tags=["webhooks"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura inválida")
    
    # Processa o evento
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await handle_checkout_completed(session)
    
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        await handle_subscription_updated(subscription)
    
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await handle_subscription_deleted(subscription)
    
    return {"status": "ok"}

async def handle_checkout_completed(session):
    """Atualiza o usuário para PRO quando o checkout é concluído"""
    db = SessionLocal()
    try:
        user_id = session.get("metadata", {}).get("user_id")
        if not user_id:
            return
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            # Obtém detalhes da subscription
            subscription_id = session.get("subscription")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                user.stripe_subscription_id = subscription_id
                user.subscription_status = "PRO"
                user.subscription_end_date = datetime.fromtimestamp(
                    subscription.current_period_end
                )
            
            db.commit()
    finally:
        db.close()

async def handle_subscription_updated(subscription):
    """Atualiza a data de expiração quando a subscription é renovada"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.stripe_subscription_id == subscription.id
        ).first()
        
        if user:
            user.subscription_end_date = datetime.fromtimestamp(
                subscription.current_period_end
            )
            user.subscription_status = "PRO"
            db.commit()
    finally:
        db.close()

async def handle_subscription_deleted(subscription):
    """Marca a assinatura como expirada quando cancelada"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(
            User.stripe_subscription_id == subscription.id
        ).first()
        
        if user:
            user.subscription_status = "EXPIRED"
            db.commit()
    finally:
        db.close()
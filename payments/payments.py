import stripe
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from Databases.databases import  User,SessionLocal
from Auth.auth import get_current_user
import os

router = APIRouter(prefix="/payments", tags=["payments"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

# Preços dos planos (crie no Dashboard do Stripe)
# Exemplo: Plano PRO mensal
PLANOS = {
    "pro_monthly": {
        "price_id": os.environ.get("STRIPE_PRO_MONTHLY_PRICE_ID"),
        "name": "Plano PRO Mensal",
        "amount": 29.90,
        "interval": "month"
    },
    "pro_yearly": {
        "price_id": os.environ.get("STRIPE_PRO_YEARLY_PRICE_ID"),
        "name": "Plano PRO Anual",
        "amount": 299.00,
        "interval": "year"
    }
}

class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str

@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CheckoutRequest,
    user: User = Depends(get_current_user)
):
    """Cria uma sessão de checkout do Stripe"""
    try:
        # Busca ou cria o customer no Stripe
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"user_id": user.id}
            )
            user.stripe_customer_id = customer.id
            db = SessionLocal()
            db.commit()
        
        # Cria a sessão de checkout
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": request.price_id,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={"user_id": user.id}
        )
        
        return {"session_id": checkout_session.id, "url": checkout_session.url}
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subscription-status")
async def get_subscription_status(user: User = Depends(get_current_user)):
    """Retorna o status da assinatura do usuário"""
    return {
        "status": user.subscription_status,
        "plan": "PRO" if user.subscription_status == "PRO" else "FREE",
        "end_date": user.subscription_end_date.isoformat() if user.subscription_end_date else None
    }

@router.post("/cancel-subscription")
async def cancel_subscription(user: User = Depends(get_current_user)):
    """Cancela a assinatura do usuário"""
    if not user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="Nenhuma assinatura ativa")
    
    try:
        # Cancela no Stripe
        stripe.Subscription.modify(
            user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        return {"message": "Assinatura cancelada com sucesso. Válida até o fim do período."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
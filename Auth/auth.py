from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from Databases.databases import User, SessionLocal
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "sua-chave-secreta-aqui-mude-em-producao")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")

def get_current_user(email: str = Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

def check_premium_access(user: User = Depends(get_current_user)):
    """Verifica se o usuário tem acesso premium (assinatura ativa)"""
    if user.subscription_status != "PRO":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso premium necessário. Assine o plano para continuar."
        )
    
    # Verifica se o período de assinatura não expirou
    if user.subscription_end_date and user.subscription_end_date < datetime.utcnow():
        user.subscription_status = "EXPIRED"
        db = SessionLocal()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assinatura expirada. Renove para continuar."
        )
    
    return user
# criar_pro_direto.py
from Databases.databases import SessionLocal, User
from Auth.auth import create_access_token

db = SessionLocal()

# Deletar usuário existente se houver
db.query(User).filter(User.email == "pro@teste.com").delete()

# Criar novo usuário PRO
user = User(
    email="pro@teste.com",
    hashed_password="123456",  # senha simples
    subscription_status="PRO",
    is_active=True
)
db.add(user)
db.commit()
db.refresh(user)

print(f"✅ Usuário criado: {user.email}")
print(f"📋 Status: {user.subscription_status}")

# Criar token para teste
token = create_access_token(data={"sub": user.email})
print(f"\n🔑 TOKEN (copie para testar):")
print(token)

db.close()
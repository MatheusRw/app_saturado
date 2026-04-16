"""
Script de Diagnóstico Completo - Saturado
Verifica backend, banco de dados, usuários, tokens e conectividade
"""

import sys
import os
import requests
import sqlite3
import json

# Configurações
BACKEND_URL = "http://localhost:8000"
DB_PATH = "saturado.db"

print("=" * 60)
print("🔍 DIAGNÓSTICO DO SISTEMA SATURADO")
print("=" * 60)

# ============================================================
# 1. VERIFICAR BACKEND
# ============================================================
print("\n📡 1. VERIFICANDO BACKEND...")
try:
    response = requests.get(f"{BACKEND_URL}/", timeout=5)
    if response.status_code == 200:
        print(f"   ✅ Backend rodando em {BACKEND_URL}")
        print(f"   📦 Versão: {response.json().get('versao', 'N/A')}")
    else:
        print(f"   ❌ Backend respondeu com status {response.status_code}")
except requests.exceptions.ConnectionError:
    print(f"   ❌ Backend NÃO está rodando em {BACKEND_URL}")
    print(f"   🔧 Solução: Execute 'uvicorn main:app --reload --port 8000'")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# ============================================================
# 2. VERIFICAR BANCO DE DADOS
# ============================================================
print("\n🗄️ 2. VERIFICANDO BANCO DE DADOS...")
if os.path.exists(DB_PATH):
    print(f"   ✅ Banco encontrado: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verificar tabela users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone():
            print(f"   ✅ Tabela 'users' existe")
            
            # Contar usuários
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            print(f"   👥 Total de usuários: {count}")
            
            # Listar usuários
            cursor.execute("SELECT email, subscription_status, is_active FROM users")
            users = cursor.fetchall()
            for email, status, active in users:
                status_icon = "✅" if active else "❌"
                print(f"      {status_icon} {email} - Status: {status}")
        else:
            print(f"   ❌ Tabela 'users' não encontrada")
        
        conn.close()
    except Exception as e:
        print(f"   ❌ Erro ao ler banco: {e}")
else:
    print(f"   ❌ Banco não encontrado em {DB_PATH}")

# ============================================================
# 3. TESTAR AUTENTICAÇÃO
# ============================================================
print("\n🔐 3. TESTANDO AUTENTICAÇÃO...")

test_users = [
    ("pro@teste.com", "123456"),
    ("teste@teste.com", "123456")
]

for email, password in test_users:
    try:
        response = requests.post(
            f"{BACKEND_URL}/login",
            data={"email": email, "password": password},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token", "")[:50]
            user_status = data.get("user", {}).get("status", "N/A")
            print(f"   ✅ Login OK: {email} (Status: {user_status})")
            print(f"      Token: {token}...")
            
            # Testar rota protegida com o token
            headers = {"Authorization": f"Bearer {data['access_token']}"}
            resp2 = requests.get(
                f"{BACKEND_URL}/relatorio",
                params={"cnae": "barbearia", "municipio": "Rio de Janeiro", "raio_km": 3},
                headers=headers,
                timeout=10
            )
            if resp2.status_code == 200:
                print(f"      ✅ Rota /relatorio acessível (PRO)")
            elif resp2.status_code == 403:
                print(f"      ⚠️ Rota /relatorio: Acesso negado (usuário não PRO)")
            else:
                print(f"      ❌ Rota /relatorio: Status {resp2.status_code}")
        else:
            print(f"   ❌ Login falhou para {email}: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Não foi possível testar login (backend offline)")
        break
    except Exception as e:
        print(f"   ❌ Erro: {e}")

# ============================================================
# 4. TESTAR ROTAS PÚBLICAS
# ============================================================
print("\n🌐 4. TESTANDO ROTAS PÚBLICAS...")

routes = [
    ("GET", "/", "Status"),
    ("GET", "/analise?cnae=barbearia&municipio=Rio%20de%20Janeiro&raio_km=3", "Análise"),
]

for method, route, name in routes:
    try:
        if method == "GET":
            response = requests.get(f"{BACKEND_URL}{route}", timeout=10)
        if response.status_code == 200:
            print(f"   ✅ {name}: OK")
        else:
            print(f"   ⚠️ {name}: Status {response.status_code}")
    except Exception as e:
        print(f"   ❌ {name}: Erro - {e}")

# ============================================================
# 5. TESTAR ROTAS PREMIUM
# ============================================================
print("\n⭐ 5. TESTANDO ROTAS PREMIUM...")

# Primeiro, fazer login para obter token
try:
    response = requests.post(
        f"{BACKEND_URL}/login",
        data={"email": "pro@teste.com", "password": "123456"},
        timeout=5
    )
    if response.status_code == 200:
        token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        premium_routes = [
            ("GET", "/relatorio?cnae=barbearia&municipio=Rio%20de%20Janeiro&raio_km=3", "Relatório"),
            ("GET", "/recomendar?cnae=barbearia&municipio=Rio%20de%20Janeiro&raio_km=3", "Recomendação"),
        ]
        
        for method, route, name in premium_routes:
            try:
                resp = requests.get(f"{BACKEND_URL}{route}", headers=headers, timeout=15)
                if resp.status_code == 200:
                    print(f"   ✅ {name}: OK")
                    # Mostrar resumo da recomendação se for o caso
                    if name == "Recomendação" and resp.status_code == 200:
                        data = resp.json()
                        if data.get("melhor_rua"):
                            melhor = data["melhor_rua"]
                            print(f"      🏆 Melhor rua: {melhor.get('rua', 'N/A')} (Score: {melhor.get('score', 'N/A')})")
                elif resp.status_code == 401:
                    print(f"   ❌ {name}: Não autorizado - Token inválido")
                elif resp.status_code == 403:
                    print(f"   ❌ {name}: Acesso negado - Usuário não é PRO")
                else:
                    print(f"   ⚠️ {name}: Status {resp.status_code}")
            except Exception as e:
                print(f"   ❌ {name}: Erro - {e}")
    else:
        print(f"   ❌ Não foi possível obter token para rotas premium")
except Exception as e:
    print(f"   ❌ Erro no login para rotas premium: {e}")

# ============================================================
# 6. VERIFICAR ARQUIVOS DO FRONTEND
# ============================================================
print("\n📁 6. VERIFICANDO ARQUIVOS DO FRONTEND...")

frontend_paths = [
    "../app_saturado_frontend/src/services/api.js",
    "../app_saturado_frontend/src/contexts/AuthContext.jsx",
    "../app_saturado_frontend/src/components/Relatorio.jsx",
    "../app_saturado_frontend/.env",
]

for path in frontend_paths:
    full_path = os.path.join(os.path.dirname(__file__), path)
    if os.path.exists(full_path):
        print(f"   ✅ {path}")
    else:
        print(f"   ❌ {path} - NÃO ENCONTRADO")

# ============================================================
# 7. VERIFICAR VARIÁVEIS DE AMBIENTE
# ============================================================
print("\n🔑 7. VERIFICANDO VARIÁVEIS DE AMBIENTE...")

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        env_content = f.read()
    env_vars = ['GOOGLE_PLACES_API_KEY', 'STRIPE_SECRET_KEY', 'GEMINI_API_KEY']
    for var in env_vars:
        if var in env_content:
            # Mostra apenas os primeiros e últimos caracteres por segurança
            import re
            match = re.search(f'{var}=(.+)', env_content)
            if match:
                value = match.group(1).strip()
                if value and len(value) > 10:
                    print(f"   ✅ {var}=...{value[-6:]}")
                elif value:
                    print(f"   ✅ {var} configurada")
                else:
                    print(f"   ⚠️ {var} está vazia")
        else:
            print(f"   ❌ {var} não encontrada no .env")
else:
    print(f"   ❌ Arquivo .env não encontrado")

# ============================================================
# RESUMO FINAL
# ============================================================
print("\n" + "=" * 60)
print("📋 RESUMO DO DIAGNÓSTICO")
print("=" * 60)

if os.path.exists(DB_PATH):
    print("✅ Banco de dados: OK")
else:
    print("❌ Banco de dados: PROBLEMA")

try:
    requests.get(f"{BACKEND_URL}/", timeout=2)
    print("✅ Backend: RODANDO")
except:
    print("❌ Backend: PARADO - Execute 'uvicorn main:app --reload --port 8000'")

print("\n🔧 PARA CORRIGIR:")
print("1. Se o backend não estiver rodando: uvicorn main:app --reload --port 8000")
print("2. Se o usuário não for PRO: python -c \"from Databases.databases import SessionLocal, User; db=SessionLocal(); user=db.query(User).filter(User.email=='pro@teste.com').first(); user.subscription_status='PRO'; db.commit()\"")
print("3. Se o frontend não conectar: Verifique se o .env tem VITE_API_URL=http://localhost:8000")
print("4. Depois, faça logout e login novamente no frontend")

print("\n" + "=" * 60)
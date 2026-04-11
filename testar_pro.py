# testar_pro.py
import requests
import sqlite3

BASE_URL = "http://localhost:8000"

print("=== CRIANDO USUÁRIO ===")
response = requests.post(f"{BASE_URL}/register", params={
    "email": "pro@teste.com",
    "password": "123456"
})
print(response.json())

print("\n=== FAZENDO LOGIN ===")
response = requests.post(f"{BASE_URL}/login", params={
    "email": "pro@teste.com",
    "password": "123456"
})
print(response.json())

if response.status_code == 200:
    token = response.json().get("access_token")
    print(f"\n✅ Token obtido: {token[:50]}...")
    
    print("\n=== ATUALIZANDO PARA PRO (direto no banco) ===")
    conn = sqlite3.connect('saturado.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET subscription_status = 'PRO' WHERE email = 'pro@teste.com'")
    conn.commit()
    print(f"✅ Linhas afetadas: {cursor.rowcount}")
    conn.close()
    
    print("\n=== TESTANDO RELATÓRIO ===")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/relatorio",
        params={"cnae": "pet", "municipio": "Rio de Janeiro", "raio_km": 3},
        headers=headers
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Relatório gerado! Encontrados: {data.get('total_empresas')} estabelecimentos")
    else:
        print(f"❌ Erro: {response.text}")
else:
    print("❌ Falha no login")
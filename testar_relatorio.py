import requests

BASE_URL = "http://localhost:8000"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwcm9AdGVzdGUuY29tIiwiZXhwIjoxNzc1ODcyNzk4fQ.TKKoewqrXRate85SazfO3Uq1pCyqu15p5A1RDt52BGA"

print("=== TESTANDO RELATÓRIO ===")
headers = {"Authorization": f"Bearer {TOKEN}"}
response = requests.get(
    f"{BASE_URL}/relatorio",
    params={"cnae": "pet", "municipio": "Rio de Janeiro", "raio_km": 3},
    headers=headers
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"\n✅ SUCESSO!")
    print(f"📊 Total de estabelecimentos: {data.get('total_empresas')}")
    print(f"🏪 Estabelecimentos abertos: {data.get('empresas_ativas')}")
    print(f"⭐ Score: {data.get('score')}/100")
    print(f"📌 Status: {data.get('status_label')}")
    print(f"⭐ Nota média: {data.get('rating_medio')}")
    
    if data.get('lugares'):
        print(f"\n📋 Primeiros estabelecimentos:")
        for i, lugar in enumerate(data['lugares'][:5], 1):
            print(f"  {i}. {lugar['nome']} - ★ {lugar.get('rating', 'N/A')}")
else:
    print(f"❌ Erro: {response.text}")
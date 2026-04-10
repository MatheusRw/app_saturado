import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 1. BRASILAPI (IBGE + CNAE fictício)
# ============================================================
async def testar_brasilapi():
    print("\n🌍 TESTANDO BRASILAPI...")
    async with httpx.AsyncClient(timeout=10) as client:
        # IBGE - municípios do RJ
        resp = await client.get("https://brasilapi.com.br/api/ibge/municipios/v1/RJ")
        if resp.status_code == 200:
            cidades = [m["nome"] for m in resp.json() if "niter" in m["nome"].lower()]
            print(f"✅ IBGE funcionando. Niterói encontrado? {bool(cidades)}")
        else:
            print("❌ BrasilAPI falhou no IBGE")

        # Busca CNPJs simulada (endpoint de teste)
        resp2 = await client.get("https://brasilapi.com.br/api/cnpj/v1/00000000000191")
        if resp2.status_code == 200:
            print("✅ BrasilAPI CNPJ funcionando (exemplo)")
        else:
            print("⚠️ BrasilAPI CNPJ pode estar instável")

# ============================================================
# 2. NUVEM FISCAL (requer credenciais .env)
# ============================================================
async def testar_nuvemfiscal():
    print("\n☁️ TESTANDO NUVEM FISCAL...")
    client_id = os.getenv("NUVEM_FISCAL_CLIENT_ID")
    client_secret = os.getenv("NUVEM_FISCAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("⚠️ Credenciais Nuvem Fiscal não encontradas no .env")
        return

    async with httpx.AsyncClient(timeout=10) as client:
        # Obter token
        auth_resp = await client.post(
            "https://auth.nuvemfiscal.com.br/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "cnpj",
            },
        )
        if auth_resp.status_code != 200:
            print(f"❌ Falha na autenticação Nuvem Fiscal: {auth_resp.text[:200]}")
            return

        token = auth_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Testar listagem CNPJ (CNAE barbearia, Niterói)
        params = {
            "cnae_principal": "9602501",
            "municipio": "3303302",  # IBGE Niterói
            "$top": 1,
        }
        resp = await client.get(
            "https://api.nuvemfiscal.com.br/cnpj",
            params=params,
            headers=headers,
        )
        if resp.status_code == 200:
            print("✅ Nuvem Fiscal funcionando! Retornou empresas.")
        elif resp.status_code == 403:
            print("🚫 Nuvem Fiscal: quota esgotada ou não ativada (cnpj-listagem).")
            print("   → Solução: ative o plano gratuito em https://app.nuvemfiscal.com.br")
        else:
            print(f"❌ Nuvem Fiscal retornou {resp.status_code}: {resp.text[:200]}")

# ============================================================
# 3. CNPJ.WS (API que você usa em services/cnpjws.py)
# ============================================================
async def testar_cnpjws():
    print("\n🏢 TESTANDO CNPJ.WS...")
    token = os.getenv("CNPJWS_TOKEN")  # se você usa token
    if not token:
        print("⚠️ CNPJWS_TOKEN não encontrado no .env. Pulando...")
        return

    async with httpx.AsyncClient(timeout=15) as client:
        # Exemplo de busca por CNAE (verificar documentação do CNPJ.ws)
        # Ajuste a URL conforme a API que você implementou em services/cnpjws.py
        url = "https://api.cnpj.ws/cnae/9602501?municipio=3303302&limite=1"
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            print("✅ CNPJ.ws respondeu com sucesso.")
        else:
            print(f"❌ CNPJ.ws erro {resp.status_code}: {resp.text[:200]}")

# ============================================================
# EXECUTAR TODOS
# ============================================================
async def main():
    await testar_brasilapi()
    await testar_nuvemfiscal()
    await testar_cnpjws()

if __name__ == "__main__":
    asyncio.run(main())
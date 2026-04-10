"""
DEBUG COMPLETO — Nuvem Fiscal

Objetivo:
- Validar autenticação
- Validar parâmetros obrigatórios
- Testar múltiplas naturezas jurídicas (uma por vez)
- Detectar erro de quota
- Mostrar exatamente o que está sendo enviado

Execute:
    python debug_nuvemfiscal_full.py
"""

import asyncio
import httpx
import os
import json

BRASILAPI = "https://brasilapi.com.br/api"
AUTH_URL  = "https://auth.nuvemfiscal.com.br/oauth/token"
BASE_URL  = "https://api.nuvemfiscal.com.br"

CNAE = "9602501"  # Barbearia
NATUREZAS = ["2135", "2062", "2305"]  # testar uma por vez


# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────
async def obter_token():
    client_id     = os.environ.get("NUVEM_FISCAL_CLIENT_ID")
    client_secret = os.environ.get("NUVEM_FISCAL_CLIENT_SECRET")

    print("\n🔐 Testando autenticação...")

    if not client_id or not client_secret:
        print("❌ Credenciais não encontradas no .env")
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "cnpj",
            },
        )

        print("Status Auth:", resp.status_code)

        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print("✅ Token OK")
            return token
        else:
            print("❌ Erro autenticação:")
            print(resp.text[:300])
            return None


# ─────────────────────────────────────────
# IBGE
# ─────────────────────────────────────────
async def get_ibge():
    print("\n🌍 Buscando IBGE de Niterói...")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{BRASILAPI}/ibge/municipios/v1/RJ")

        if resp.status_code != 200:
            print("❌ Erro BrasilAPI")
            return None

        municipios = resp.json()
        niteroi = next((m for m in municipios if "niter" in m["nome"].lower()), None)

        if not niteroi:
            print("❌ Não encontrou Niterói")
            return None

        cod = niteroi["codigo_ibge"]
        print(f"✅ IBGE: {cod}")
        return cod


# ─────────────────────────────────────────
# TESTE PRINCIPAL
# ─────────────────────────────────────────
async def testar():
    print("=" * 60)
    print("DEBUG COMPLETO — NUVEM FISCAL")
    print("=" * 60)

    cod_ibge = await get_ibge()
    if not cod_ibge:
        return

    token = await obter_token()
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}

    print("\n🚀 Iniciando testes...\n")

    async with httpx.AsyncClient(timeout=10.0) as client:

        for natureza in NATUREZAS:
            print("=" * 60)
            print(f"🔎 Testando natureza_juridica = {natureza}")
            print("=" * 60)

            params = {
                "cnae_principal": CNAE,
                "municipio": cod_ibge,
                "natureza_juridica": natureza,
                "$top": 5,
                "$skip": 0,
            }

            print("\n📤 PARAMS ENVIADOS:")
            print(json.dumps(params, indent=2))

            resp = await client.get(
                f"{BASE_URL}/cnpj",
                params=params,
                headers=headers
            )

            print("\n🌐 URL FINAL:")
            print(resp.url)

            print("\n📊 STATUS:", resp.status_code)

            # ───── SUCESSO ─────
            if resp.status_code == 200:
                data = resp.json()
                empresas = data.get("data", [])

                print(f"\n✅ SUCESSO — {len(empresas)} empresas")

                if empresas:
                    print("\n📄 Primeira empresa:")
                    print(json.dumps(empresas[0], indent=2, ensure_ascii=False)[:1000])

            # ───── QUOTA ─────
            elif resp.status_code == 403:
                print("\n🚫 ERRO DE QUOTA")
                print(resp.text)

                print("\n👉 SOLUÇÃO:")
                print("- Ativar plano na Nuvem Fiscal")
                print("- Habilitar 'cnpj-listagem'")
                return

            # ───── ERRO VALIDAÇÃO ─────
            elif resp.status_code == 400:
                print("\n⚠️ ERRO DE VALIDAÇÃO")
                print(resp.text)

            # ───── OUTROS ─────
            else:
                print("\n❌ ERRO DESCONHECIDO")
                print(resp.text[:500])


# ─────────────────────────────────────────
asyncio.run(testar())
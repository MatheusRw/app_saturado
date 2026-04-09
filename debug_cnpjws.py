"""
Roda esse script para testar a CNPJ.ws e ver o que ela retorna.
Execute na pasta app_saturado:

    python debug_cnpjws.py
"""

import asyncio
import httpx
import json

BRASILAPI = "https://brasilapi.com.br/api"
CNPJWS    = "https://publica.cnpj.ws"


async def testar():
    print("=" * 60)
    print("PASSO 1 — Buscando código IBGE de Niterói via BrasilAPI")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=10.0) as client:

        # Passo 1: código IBGE
        url_ibge = f"{BRASILAPI}/ibge/municipios/v1/RJ"
        resp = await client.get(url_ibge)
        print(f"Status: {resp.status_code}")

        if resp.status_code == 200:
            municipios = resp.json()
            niteroi = next((m for m in municipios if "niter" in m["nome"].lower()), None)
            if niteroi:
                cod = niteroi["codigo_ibge"]
                print(f"✅ Encontrado: {niteroi['nome']} → código IBGE: {cod}")
            else:
                print("❌ Niterói não encontrado")
                return
        else:
            print(f"❌ Erro BrasilAPI: {resp.text[:200]}")
            return

        print()
        print("=" * 60)
        print("PASSO 2 — Buscando empresas CNAE 9602501 (barbearia) em Niterói")
        print("=" * 60)

        # Passo 2: empresas por município + CNAE
        url_emp = f"{CNPJWS}/municipio/{cod}/empresas"
        params = {"pagina": 1, "atividade_principal": "9602501"}

        resp2 = await client.get(url_emp, params=params)
        print(f"Status: {resp2.status_code}")
        print(f"URL chamada: {resp2.url}")

        if resp2.status_code == 200:
            data = resp2.json()
            print(f"\nTipo retornado: {type(data)}")
            if isinstance(data, list):
                print(f"✅ Lista com {len(data)} empresas")
                if data:
                    print("\nPrimeira empresa (estrutura completa):")
                    print(json.dumps(data[0], indent=2, ensure_ascii=False)[:1500])
            elif isinstance(data, dict):
                print(f"✅ Dict com chaves: {list(data.keys())}")
                empresas = data.get("empresas") or data.get("data") or []
                print(f"Empresas encontradas: {len(empresas)}")
                if empresas:
                    print("\nPrimeira empresa:")
                    print(json.dumps(empresas[0], indent=2, ensure_ascii=False)[:1500])
                print(f"\nProxima pagina: {data.get('proxima_pagina')}")
                print(f"\nResposta completa (primeiros 500 chars):")
                print(json.dumps(data, ensure_ascii=False)[:500])
        else:
            print(f"❌ Erro CNPJ.ws: {resp2.status_code}")
            print(resp2.text[:500])

        print()
        print("=" * 60)
        print("PASSO 3 — Testando sem filtro de CNAE")
        print("=" * 60)

        resp3 = await client.get(url_emp, params={"pagina": 1})
        print(f"Status: {resp3.status_code}")
        if resp3.status_code == 200:
            data3 = resp3.json()
            if isinstance(data3, list):
                print(f"✅ {len(data3)} empresas sem filtro")
                if data3:
                    print("Chaves da primeira empresa:", list(data3[0].keys()))
            elif isinstance(data3, dict):
                print("Chaves do dict:", list(data3.keys()))
                empresas3 = data3.get("empresas") or []
                if empresas3:
                    print("Chaves da primeira empresa:", list(empresas3[0].keys()))
        else:
            print(f"❌ {resp3.status_code}: {resp3.text[:200]}")


asyncio.run(testar())

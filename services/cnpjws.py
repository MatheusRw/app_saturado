"""
Integração com CNPJ.ws (https://publica.cnpj.ws)
API pública, sem autenticação, com rate limit de ~3 req/s.

Endpoints usados:
  GET /cnpj/{cnpj}                    → dados de uma empresa
  GET /municipio/{cod_ibge}/empresas  → empresas por município (paginado)

Estratégia de busca por CNAE + município:
  1. Descobre o código IBGE do município via BrasilAPI
  2. Busca empresas paginadas no município
  3. Filtra pelo CNAE desejado
  4. Para ao atingir limite ou acabar as páginas
"""

import httpx
import asyncio
from typing import Any

CNPJWS_BASE = "https://publica.cnpj.ws"
BRASILAPI_BASE = "https://brasilapi.com.br/api"

# Limite de empresas a buscar por análise (evita abuso de API gratuita)
MAX_EMPRESAS = 150
# Delay entre requests para respeitar rate limit
DELAY_ENTRE_REQUESTS = 0.4


async def buscar_cod_ibge(municipio: str, uf: str = "") -> str | None:
    """Busca o código IBGE de um município via BrasilAPI."""
    url = f"{BRASILAPI_BASE}/ibge/municipios/v1/{uf or 'RJ'}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                municipios = resp.json()
                nome_norm = municipio.lower().strip()
                for m in municipios:
                    if nome_norm in m["nome"].lower():
                        return str(m["codigo_ibge"])
    except httpx.RequestError:
        pass
    return None


async def buscar_empresas_cnpjws(
    cnae: str,
    municipio: str,
    max_resultados: int = MAX_EMPRESAS,
) -> list[dict[str, Any]]:
    """
    Busca empresas por CNAE em um município usando CNPJ.ws com paginação.
    Retorna lista de empresas enriquecidas.
    """
    # Tenta descobrir código IBGE
    cod_ibge = await buscar_cod_ibge(municipio)
    if not cod_ibge:
        return []

    empresas: list[dict] = []
    pagina = 1

    async with httpx.AsyncClient(timeout=10.0) as client:
        while len(empresas) < max_resultados:
            url = f"{CNPJWS_BASE}/municipio/{cod_ibge}/empresas"
            params = {"pagina": pagina, "atividade_principal": cnae}

            try:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    break

                data = resp.json()
                itens = data.get("empresas", []) or data if isinstance(data, list) else []

                if not itens:
                    break

                for item in itens:
                    empresa = _normalizar_empresa(item)
                    if empresa:
                        empresas.append(empresa)

                # Verifica se há próxima página
                if not data.get("proxima_pagina") and isinstance(data, dict):
                    break

                pagina += 1
                await asyncio.sleep(DELAY_ENTRE_REQUESTS)

            except (httpx.RequestError, Exception):
                break

    return empresas[:max_resultados]


def _normalizar_empresa(raw: dict) -> dict | None:
    """Normaliza os dados brutos de uma empresa do CNPJ.ws."""
    try:
        cnpj = raw.get("cnpj", "")
        if not cnpj:
            return None

        razao = raw.get("razao_social", "")
        fantasia = raw.get("nome_fantasia", "") or razao

        endereco = raw.get("estabelecimento", raw)
        bairro = (
            endereco.get("bairro") or
            raw.get("bairro") or
            "Não informado"
        )
        municipio_nome = (
            endereco.get("municipio", {}).get("descricao") or
            raw.get("municipio", "")
        )

        situacao = (
            endereco.get("situacao_cadastral") or
            raw.get("situacao_cadastral", "")
        ).upper()
        ativa = situacao in ("ATIVA", "2", "02")

        data_inicio = (
            endereco.get("data_inicio_atividade") or
            raw.get("data_inicio_atividade", "")
        )
        ano_abertura = int(data_inicio[:4]) if data_inicio and len(data_inicio) >= 4 else None

        porte_raw = (raw.get("porte", {}) or {})
        porte = porte_raw.get("descricao", "") if isinstance(porte_raw, dict) else str(porte_raw)

        natureza = (raw.get("natureza_juridica", {}) or {})
        mei = "mei" in (natureza.get("descricao", "") or "").lower()

        capital = float(raw.get("capital_social", 0) or 0)

        return {
            "cnpj": cnpj,
            "nome": fantasia[:60] if fantasia else razao[:60],
            "bairro": bairro,
            "municipio": municipio_nome,
            "ativa": ativa,
            "situacao": situacao,
            "ano_abertura": ano_abertura,
            "porte": "MEI" if mei else (porte or "Não informado"),
            "capital_social": capital,
        }
    except Exception:
        return None


def agregar_dados(empresas: list[dict]) -> dict[str, Any]:
    """Agrega dados das empresas para uso no score e no relatório."""
    if not empresas:
        return {
            "total_empresas": 0,
            "empresas_ativas": 0,
            "abertas_ultimo_ano": 0,
            "por_bairro": {},
            "por_ano": {},
            "por_porte": {},
            "lista": [],
        }

    from datetime import datetime
    ano_atual = datetime.now().year

    ativas = [e for e in empresas if e["ativa"]]
    abertas_ano = [e for e in empresas if e.get("ano_abertura") == ano_atual - 1 or e.get("ano_abertura") == ano_atual]

    # Distribuição por bairro (top 8)
    por_bairro: dict[str, int] = {}
    for e in empresas:
        b = e["bairro"] or "Não informado"
        por_bairro[b] = por_bairro.get(b, 0) + 1
    por_bairro = dict(sorted(por_bairro.items(), key=lambda x: -x[1])[:8])

    # Aberturas por ano (últimos 8 anos)
    por_ano: dict[str, int] = {}
    for e in empresas:
        if e.get("ano_abertura") and e["ano_abertura"] >= ano_atual - 8:
            k = str(e["ano_abertura"])
            por_ano[k] = por_ano.get(k, 0) + 1
    por_ano = dict(sorted(por_ano.items()))

    # Distribuição por porte
    por_porte: dict[str, int] = {}
    for e in empresas:
        p = e["porte"] or "Outros"
        por_porte[p] = por_porte.get(p, 0) + 1

    return {
        "total_empresas": len(empresas),
        "empresas_ativas": len(ativas),
        "abertas_ultimo_ano": len(abertas_ano),
        "por_bairro": por_bairro,
        "por_ano": por_ano,
        "por_porte": por_porte,
        "lista": empresas,
    }

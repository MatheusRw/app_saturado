"""
Integração com Nuvem Fiscal API (https://api.nuvemfiscal.com.br)
Documentação: https://dev.nuvemfiscal.com.br/docs/cnpj-cnae

Endpoint: GET /cnpj?cnae_principal=9602501&municipio=3303302&$top=50&$skip=0

Requer cadastro gratuito em https://app.nuvemfiscal.com.br
Plano gratuito: 1.000 consultas/mês de listagem.
Cada página de 50 empresas = 50 consultas.

Configure no .env:
    NUVEM_FISCAL_CLIENT_ID=seu_client_id
    NUVEM_FISCAL_CLIENT_SECRET=seu_client_secret
"""

import httpx
import asyncio
import os
from typing import Any

NUVEMFISCAL_AUTH  = "https://auth.nuvemfiscal.com.br/oauth/token"
NUVEMFISCAL_API   = "https://api.nuvemfiscal.com.br"
BRASILAPI_BASE    = "https://brasilapi.com.br/api"

PAGE_SIZE    = 50
MAX_EMPRESAS = 150
DELAY        = 0.3   # segundos entre páginas


# ── Auth ─────────────────────────────────────────────────────────────────────

async def _obter_token() -> str | None:
    """Obtém access token OAuth2 da Nuvem Fiscal."""
    client_id     = os.environ.get("NUVEM_FISCAL_CLIENT_ID", "")
    client_secret = os.environ.get("NUVEM_FISCAL_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                NUVEMFISCAL_AUTH,
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     client_id,
                    "client_secret": client_secret,
                    "scope":         "cnpj",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200:
                return resp.json().get("access_token")
    except httpx.RequestError:
        pass
    return None


# ── IBGE ─────────────────────────────────────────────────────────────────────

async def buscar_cod_ibge(municipio: str, uf: str = "RJ") -> str | None:
    """Descobre o código IBGE de um município."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{BRASILAPI_BASE}/ibge/municipios/v1/{uf}")
            if resp.status_code == 200:
                nome_norm = municipio.lower().strip()
                for m in resp.json():
                    if nome_norm in m["nome"].lower():
                        return str(m["codigo_ibge"])
    except httpx.RequestError:
        pass

    # Tenta outras UFs comuns se não achar na RJ
    ufs = ["SP", "MG", "RS", "BA", "SC", "PR", "CE", "PE", "GO", "ES"]
    for uf_alt in ufs:
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(f"{BRASILAPI_BASE}/ibge/municipios/v1/{uf_alt}")
                if resp.status_code == 200:
                    nome_norm = municipio.lower().strip()
                    for m in resp.json():
                        if nome_norm in m["nome"].lower():
                            return str(m["codigo_ibge"])
        except httpx.RequestError:
            continue
    return None


# ── Busca principal ───────────────────────────────────────────────────────────

async def buscar_empresas_cnpjws(
    cnae: str,
    municipio: str,
    max_resultados: int = MAX_EMPRESAS,
) -> list[dict[str, Any]]:
    """
    Busca empresas por CNAE + município via Nuvem Fiscal.
    Retorna lista vazia se a API key não estiver configurada.
    """
    token = await _obter_token()
    if not token:
        return []  # Sem credenciais → fallback para dados estimados

    cod_ibge = await buscar_cod_ibge(municipio)
    if not cod_ibge:
        return []

    empresas: list[dict] = []
    skip = 0
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=12.0) as client:
        while len(empresas) < max_resultados:
            params = {
                "$top":           PAGE_SIZE,
                "$skip":          skip,
                "cnae_principal": cnae,
                "municipio":      cod_ibge,
            }
            try:
                resp = await client.get(
                    f"{NUVEMFISCAL_API}/cnpj",
                    params=params,
                    headers=headers,
                )
                if resp.status_code == 401:
                    break  # Token inválido
                if resp.status_code != 200:
                    break

                data = resp.json()
                itens = data.get("data", []) or []

                if not itens:
                    break

                for item in itens:
                    emp = _normalizar_empresa(item)
                    if emp:
                        empresas.append(emp)

                # Paginação: se veio menos que PAGE_SIZE, acabou
                if len(itens) < PAGE_SIZE:
                    break

                skip += PAGE_SIZE
                await asyncio.sleep(DELAY)

            except httpx.RequestError:
                break

    return empresas[:max_resultados]


# ── Normalização ──────────────────────────────────────────────────────────────

def _normalizar_empresa(raw: dict) -> dict | None:
    """Normaliza os campos retornados pela Nuvem Fiscal."""
    try:
        cnpj = raw.get("cnpj", "")
        if not cnpj:
            return None

        razao    = raw.get("razao_social", "") or ""
        fantasia = raw.get("nome_fantasia", "") or razao

        # Endereço — Nuvem Fiscal retorna flat
        bairro    = raw.get("bairro", "") or "Não informado"
        logradouro = raw.get("logradouro", "") or ""
        municipio_nome = raw.get("municipio", "") or ""

        # Situação cadastral
        situacao_raw = str(raw.get("situacao_cadastral", "") or "")
        # Aceita código "2"/"02" ou string "Ativa"
        ativa = situacao_raw in ("2", "02", "ATIVA", "Ativa", "ativa")

        # Data de início
        data_inicio  = raw.get("data_inicio_atividade", "") or ""
        ano_abertura = int(data_inicio[:4]) if data_inicio and len(data_inicio) >= 4 else None

        # Porte / MEI
        opcao_mei = raw.get("opcao_mei", False)
        porte_raw = raw.get("porte_empresa", "") or ""
        if opcao_mei:
            porte = "MEI"
        elif "micro" in porte_raw.lower():
            porte = "ME"
        elif "pequeno" in porte_raw.lower() or "epp" in porte_raw.lower():
            porte = "EPP"
        elif "medio" in porte_raw.lower() or "médio" in porte_raw.lower():
            porte = "Médio"
        elif "grande" in porte_raw.lower():
            porte = "Grande"
        else:
            porte = porte_raw or "Não informado"

        capital = 0.0
        try:
            capital = float(str(raw.get("capital_social", 0) or 0).replace(",", "."))
        except (ValueError, TypeError):
            pass

        return {
            "cnpj":          cnpj,
            "nome":          (fantasia or razao)[:60],
            "bairro":        bairro,
            "municipio":     municipio_nome,
            "ativa":         ativa,
            "situacao":      situacao_raw.upper() or "ATIVA",
            "ano_abertura":  ano_abertura,
            "porte":         porte,
            "capital_social": capital,
        }
    except Exception:
        return None


# ── Agregação ─────────────────────────────────────────────────────────────────

def agregar_dados(empresas: list[dict]) -> dict[str, Any]:
    """Agrega dados para uso no score e no relatório."""
    if not empresas:
        return {
            "total_empresas":    0,
            "empresas_ativas":   0,
            "abertas_ultimo_ano": 0,
            "por_bairro":        {},
            "por_ano":           {},
            "por_porte":         {},
            "lista":             [],
        }

    from datetime import datetime
    ano_atual = datetime.now().year

    ativas      = [e for e in empresas if e["ativa"]]
    abertas_ano = [e for e in empresas if e.get("ano_abertura") in (ano_atual, ano_atual - 1)]

    # Top 8 bairros
    por_bairro: dict[str, int] = {}
    for e in empresas:
        b = (e["bairro"] or "Não informado").title()
        por_bairro[b] = por_bairro.get(b, 0) + 1
    por_bairro = dict(sorted(por_bairro.items(), key=lambda x: -x[1])[:8])

    # Aberturas últimos 8 anos
    por_ano: dict[str, int] = {}
    for e in empresas:
        if e.get("ano_abertura") and e["ano_abertura"] >= ano_atual - 8:
            k = str(e["ano_abertura"])
            por_ano[k] = por_ano.get(k, 0) + 1
    por_ano = dict(sorted(por_ano.items()))

    # Distribuição de porte
    por_porte: dict[str, int] = {}
    for e in empresas:
        p = e["porte"] or "Outros"
        por_porte[p] = por_porte.get(p, 0) + 1

    return {
        "total_empresas":    len(empresas),
        "empresas_ativas":   len(ativas),
        "abertas_ultimo_ano": len(abertas_ano),
        "por_bairro":        por_bairro,
        "por_ano":           por_ano,
        "por_porte":         por_porte,
        "lista":             empresas,
    }
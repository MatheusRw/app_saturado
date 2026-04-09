"""
Integração com a Brasil API (https://brasilapi.com.br)
Documentação CNPJ: https://brasilapi.com.br/docs#tag/CNPJ

A Brasil API não tem endpoint de busca por CNAE + município diretamente.
Usamos a estratégia:
  1. Mapeamos termo/CNAE → código CNAE oficial
  2. Chamamos a API de CNAEs para validar o código
  3. Simulamos a contagem regional (para o MVP, com dados estimados por cidade)

Para produção: integrar com a API do IBGE/CNPJ.ws que permite
filtrar por município + CNAE em lote.
"""

import httpx
from typing import Any

# Mapa de termos comuns → código CNAE principal
CNAE_MAP: dict[str, str] = {
    "barbearia":  "9602501",
    "barber":     "9602501",
    "restaurante": "5611201",
    "lanchonete":  "5611203",
    "academia":    "9313100",
    "crossfit":    "9313100",
    "farmacia":    "4771701",
    "pet":         "4789004",
    "pet shop":    "4789004",
    "salao":       "9602502",
    "salão":       "9602502",
    "cabeleireiro":"9602502",
    "padaria":     "1091101",
    "confeitaria": "1091102",
    "dentista":    "8630503",
    "odonto":      "8630503",
}

BRASIL_API_BASE = "https://brasilapi.com.br/api"


def resolver_cnae(cnae_input: str) -> str:
    """Converte termo livre em código CNAE numérico."""
    chave = cnae_input.lower().strip()
    if chave in CNAE_MAP:
        return CNAE_MAP[chave]
    # Se já parece um código numérico, usa direto
    if cnae_input.replace("-", "").replace("/", "").isdigit():
        return cnae_input.replace("-", "").replace("/", "")
    # Busca parcial
    for termo, codigo in CNAE_MAP.items():
        if termo in chave or chave in termo:
            return codigo
    return cnae_input  # devolve o que veio e deixa a API reclamar


async def buscar_empresas_por_cnae(cnae: str, municipio: str) -> dict[str, Any]:
    """
    Busca dados de empresas por CNAE e município.

    MVP: Retorna dados estimados baseados em médias brasileiras por porte de cidade.
    TODO: Substituir pela API CNPJ.ws (https://publica.cnpj.ws) que suporta
          filtros por município + CNAE com paginação.
    """
    codigo_cnae = resolver_cnae(cnae)

    # Valida o código CNAE via Brasil API
    cnae_valido = await _validar_cnae(codigo_cnae)

    # Para o MVP: estima contagens baseadas em dados do IBGE/RAIS
    # Em produção: substituir por query real ao CNPJ.ws
    contagens = _estimar_contagens(codigo_cnae=codigo_cnae, municipio=municipio)

    return {
        "cnae_input": cnae,
        "cnae_codigo": codigo_cnae,
        "cnae_descricao": cnae_valido.get("descricao", cnae),
        "municipio": municipio,
        **contagens,
    }


async def _validar_cnae(codigo: str) -> dict[str, Any]:
    """Valida e descreve um CNAE via Brasil API."""
    # Formata para o padrão da API: 9999999
    codigo_limpo = codigo[:7].ljust(7, "0")
    url = f"{BRASIL_API_BASE}/cnae/v1/{codigo_limpo}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except httpx.RequestError:
        pass  # Não bloqueia o fluxo se a validação falhar

    return {"codigo": codigo, "descricao": codigo}


def _estimar_contagens(codigo_cnae: str, municipio: str) -> dict[str, int]:
    """
    Estimativa baseada em médias do RAIS/IBGE por segmento.
    
    Lógica de escalonamento por porte de cidade:
    - Metrópole  (SP, RJ, BH, POA)  → multiplicador 3.0
    - Grande     (Niterói, Campinas) → multiplicador 1.5
    - Média      (população > 100k)  → multiplicador 1.0
    - Pequena    (população < 100k)  → multiplicador 0.5

    TODO: Substituir por query real ao CNPJ.ws por município + CNAE.
    """
    # Bases por segmento (empresas ativas por 100k hab., raio 3km)
    BASE_POR_CNAE: dict[str, dict] = {
        "9602501": {"base": 58, "taxa_ativa": 0.82, "crescimento_anual": 0.22},  # barbearia
        "9602502": {"base": 88, "taxa_ativa": 0.79, "crescimento_anual": 0.17},  # salão
        "5611201": {"base": 143,"taxa_ativa": 0.78, "crescimento_anual": 0.14},  # restaurante
        "9313100": {"base": 29, "taxa_ativa": 0.81, "crescimento_anual": 0.19},  # academia
        "4771701": {"base": 19, "taxa_ativa": 0.89, "crescimento_anual": 0.08},  # farmácia
        "4789004": {"base": 37, "taxa_ativa": 0.86, "crescimento_anual": 0.25},  # pet
        "1091101": {"base": 41, "taxa_ativa": 0.83, "crescimento_anual": 0.09},  # padaria
        "8630503": {"base": 25, "taxa_ativa": 0.85, "crescimento_anual": 0.12},  # odonto
    }

    MULTIPLICADOR_CIDADE: dict[str, float] = {
        "sao paulo": 3.2, "são paulo": 3.2,
        "rio de janeiro": 2.8,
        "belo horizonte": 2.1, "porto alegre": 1.9,
        "curitiba": 1.8, "fortaleza": 1.7, "recife": 1.7,
        "niteroi": 1.5, "niterói": 1.5,
        "campinas": 1.6, "manaus": 1.5, "goiania": 1.4,
        "natal": 1.3, "maceio": 1.2,
    }

    base = BASE_POR_CNAE.get(codigo_cnae, {"base": 30, "taxa_ativa": 0.80, "crescimento_anual": 0.12})
    mult = MULTIPLICADOR_CIDADE.get(municipio.lower(), 1.0)

    total = round(base["base"] * mult)
    ativas = round(total * base["taxa_ativa"])
    abertas = round(total * base["crescimento_anual"])

    return {
        "total_empresas": max(total, 1),
        "empresas_ativas": max(ativas, 1),
        "abertas_ultimo_ano": max(abertas, 0),
    }

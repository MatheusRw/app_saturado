"""
Geração de análise SWOT via Claude API.
Usa os dados reais agregados das empresas para produzir
um relatório contextualizado e acionável.
"""

import httpx
import json
from typing import Any


CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"


async def gerar_swot(
    nicho: str,
    municipio: str,
    raio_km: int,
    dados: dict[str, Any],
    score: int,
    status: str,
) -> dict[str, Any]:
    """
    Gera análise SWOT completa via Claude API com base nos dados reais.
    Retorna dict com forcas, fraquezas, oportunidades, ameacas e insights.
    """

    por_bairro = dados.get("por_bairro", {})
    por_porte = dados.get("por_porte", {})
    por_ano = dados.get("por_ano", {})
    total = dados.get("total_empresas", 0)
    ativas = dados.get("empresas_ativas", 0)
    abertas = dados.get("abertas_ultimo_ano", 0)
    taxa_mortalidade = round((total - ativas) / max(total, 1) * 100)

    bairros_str = ", ".join(f"{b} ({n})" for b, n in list(por_bairro.items())[:5])
    porte_str = ", ".join(f"{p}: {n}" for p, n in por_porte.items())
    tendencia_str = " → ".join(f"{a}: {n}" for a, n in list(por_ano.items())[-5:])

    prompt = f"""Você é um analista de mercado especialista em pequenos negócios brasileiros.

Analise os dados reais abaixo e gere uma análise SWOT detalhada e acionável para quem quer abrir um(a) {nicho} em {municipio}.

DADOS REAIS DO MERCADO:
- Total de estabelecimentos mapeados: {total}
- Ativos: {ativas} ({round(ativas/max(total,1)*100)}%)
- Taxa de mortalidade: {taxa_mortalidade}%
- Novos no último ano: {abertas}
- Score de saturação: {score}/100 ({status})
- Raio analisado: {raio_km}km

DISTRIBUIÇÃO GEOGRÁFICA (por bairro):
{bairros_str or "Dados não disponíveis"}

DISTRIBUIÇÃO POR PORTE:
{porte_str or "Dados não disponíveis"}

TENDÊNCIA DE ABERTURAS (por ano):
{tendencia_str or "Dados não disponíveis"}

Responda APENAS com um JSON válido, sem markdown, sem explicações, no formato:
{{
  "forcas": ["item 1", "item 2", "item 3", "item 4"],
  "fraquezas": ["item 1", "item 2", "item 3", "item 4"],
  "oportunidades": ["item 1", "item 2", "item 3", "item 4"],
  "ameacas": ["item 1", "item 2", "item 3", "item 4"],
  "insights": [
    {{"titulo": "título curto", "texto": "análise de 2-3 frases baseada nos dados acima", "tag": "categoria"}},
    {{"titulo": "título curto", "texto": "análise de 2-3 frases baseada nos dados acima", "tag": "categoria"}},
    {{"titulo": "título curto", "texto": "análise de 2-3 frases baseada nos dados acima", "tag": "categoria"}}
  ],
  "recomendacao": "Uma frase direta e acionável para quem quer entrar nesse mercado agora."
}}

Use os dados reais para embasar cada ponto. Seja específico sobre {municipio}, sobre os bairros com menos concorrência, sobre o mix de porte dos concorrentes."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                CLAUDE_API_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            texto = data["content"][0]["text"].strip()

            # Remove possíveis backticks se o modelo os incluir
            if texto.startswith("```"):
                texto = texto.split("```")[1]
                if texto.startswith("json"):
                    texto = texto[4:]
            texto = texto.strip()

            return json.loads(texto)

    except Exception as e:
        # Fallback com SWOT genérica se a API falhar
        return _swot_fallback(nicho, municipio, score, status, taxa_mortalidade, abertas)


def _swot_fallback(
    nicho: str, municipio: str, score: int, status: str,
    taxa_mortalidade: int, abertas: int
) -> dict:
    """SWOT de fallback caso a API Claude não responda."""
    return {
        "forcas": [
            "Serviço presencial com alta fidelização",
            "Demanda local contínua e recorrente",
            "Barreira de entrada relativamente baixa",
            "Potencial de diferenciação por atendimento",
        ],
        "fraquezas": [
            "Alta dependência de localização física",
            f"Mercado com {score}/100 de saturação em {municipio}",
            f"Taxa de mortalidade de {taxa_mortalidade}% indica risco real",
            "Difícil diferenciação sem branding forte",
        ],
        "oportunidades": [
            "Bairros periféricos com menor concentração",
            "Nicho premium com ticket mais alto",
            f"{abertas} novas aberturas indicam demanda aquecida",
            "Planos de assinatura e fidelização mensal",
        ],
        "ameacas": [
            "Concorrência estabelecida com clientela fiel",
            "Pressão de preços em mercado denso",
            "Franquias com maior poder de capital",
            "Custo de ponto comercial elevado na região",
        ],
        "insights": [
            {
                "titulo": "Concentração geográfica",
                "texto": "Analise os bairros com menor densidade de concorrentes — costumam ter demanda reprimida.",
                "tag": "localização",
            },
            {
                "titulo": "Mix de porte",
                "texto": "Alta proporção de MEIs indica mercado acessível, mas também mais vulnerável a guerra de preços.",
                "tag": "concorrência",
            },
            {
                "titulo": "Timing de entrada",
                "texto": f"Com {abertas} aberturas recentes, o mercado ainda está em movimento. Quem entrar bem posicionado pode capturar demanda.",
                "tag": "timing",
            },
        ],
        "recomendacao": f"Mapeie os bairros com menos de 5 concorrentes no raio de {municipio} e valide presença antes de assinar contrato.",
    }

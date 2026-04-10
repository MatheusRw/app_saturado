"""
Algoritmo de Score de Saturação — Saturado MVP com Google Places

Score de 0–100 baseado em 2 fatores ponderados (já que Google Places não tem data de abertura):

  1. Densidade absoluta    (60%) — total de empresas vs. benchmark do segmento
  2. Taxa de mortalidade   (40%) — % de inativas (fechadas permanentemente)

Thresholds:
  0–54   → pouco_explorado  (verde)
  55–74  → moderado         (amarelo)
  75–100 → saturado         (vermelho)
"""

from models import ResultadoBusca

# Benchmarks de referência por 100k hab. (raio 3km, cidade média)
# Fonte: estimativas RAIS/IBGE 2023
BENCHMARK_DENSIDADE: dict[str, int] = {
    "9602501": 58,   # barbearia
    "9602502": 88,   # salão
    "5611201": 143,  # restaurante
    "9313100": 29,   # academia
    "4771701": 19,   # farmácia
    "4789004": 37,   # pet shop
    "1091101": 41,   # padaria
    "8630503": 25,   # odonto
}
BENCHMARK_DEFAULT = 40


def calcular_score(dados: dict, raio_km: int) -> ResultadoBusca:
    total       = dados.get("total_empresas", 0)
    ativas      = dados.get("empresas_ativas", 0)
    cnae_codigo = dados.get("cnae_codigo", "")
    municipio   = dados.get("municipio", "")
    cnae_input  = dados.get("cnae_input", "")

    # --- Fator 1: Densidade (60% - peso aumentado por não termos crescimento) ---
    benchmark = BENCHMARK_DENSIDADE.get(cnae_codigo, BENCHMARK_DEFAULT)
    # Ajusta benchmark pelo raio (escala quadrática simplificada)
    benchmark_ajustado = benchmark * (raio_km / 3) ** 1.4
    densidade_ratio = total / max(benchmark_ajustado, 1)
    # Normaliza: ratio 1.0 = 50 pontos, ratio 2.0 = 100 pontos
    fator_densidade = min(densidade_ratio * 50, 100)

    # --- Fator 2: Mortalidade (40%) ---
    if total == 0:
        taxa_mortalidade = 0
    else:
        taxa_mortalidade = (total - ativas) / total
    
    # Quanto menor a mortalidade, melhor (menor score de saturação)
    # > 30% inativas = mercado difícil (score 100)
    # < 5% inativas = saudável (score 0)
    fator_mortalidade = min(max((taxa_mortalidade - 0.05) / 0.25 * 100, 0), 100)

    # --- Score Final ---
    score_raw = (
        fator_densidade   * 0.60 +
        fator_mortalidade * 0.40
    )
    score = round(min(max(score_raw, 0), 100))

    # --- Status ---
    if score < 55:
        status = "pouco_explorado"
        status_label = "Mercado com espaço"
        cor = "verde"
    elif score < 75:
        status = "moderado"
        status_label = "Mercado moderado"
        cor = "amarelo"
    else:
        status = "saturado"
        status_label = "Mercado saturado"
        cor = "vermelho"

    # --- Insight baseado apenas nos dados disponíveis ---
    insight = _gerar_insight_google(
        status=status,
        descricao=cnae_input,
        municipio=municipio,
        raio_km=raio_km,
        total=total,
        ativas=ativas,
        taxa_mortalidade=taxa_mortalidade,
        cor=cor,
    )

    return ResultadoBusca(
        cnae=cnae_input,
        municipio=municipio,
        raio_km=raio_km,
        total_empresas=total,
        empresas_ativas=ativas,
        abertas_ultimo_ano=0,  # Google Places não fornece
        score=score,
        status=status,
        status_label=status_label,
        insight=insight,
    )


def _gerar_insight_google(
    status: str,
    descricao: str,
    municipio: str,
    raio_km: int,
    total: int,
    ativas: int,
    taxa_mortalidade: float,
    cor: str,
) -> str:
    inativas = total - ativas
    mortalidade_pct = round(taxa_mortalidade * 100)

    if status == "pouco_explorado":
        return (
            f"📈 {descricao.capitalize()} tem baixa concentração em {municipio} "
            f"no raio de {raio_km}km. Apenas {total} estabelecimentos encontrados "
            f"no Google Places, com {inativas} fechados. Demanda possivelmente reprimida."
        )
    elif status == "moderado":
        return (
            f"⚖️ Concorrência moderada para {descricao.lower()} em {municipio}. "
            f"Encontrados {total} estabelecimentos, dos quais {ativas} estão ativos. "
            f"Taxa de mortalidade de {mortalidade_pct}% indica giro, mas o mercado sustenta novos players."
        )
    else:
        return (
            f"⚠️ {descricao.capitalize()} é um segmento denso em {municipio} ({raio_km}km). "
            f"Total de {total} estabelecimentos, com {mortalidade_pct}% inativos. "
            f"Considere um nicho mais específico ou bairro com menor concentração."
        )
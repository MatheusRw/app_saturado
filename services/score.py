"""
Algoritmo de Score de Saturação — Saturado MVP

Score de 0–100 baseado em 3 fatores ponderados:

  1. Densidade absoluta    (40%) — total de empresas vs. benchmark do segmento
  2. Taxa de crescimento   (35%) — velocidade de novas aberturas
  3. Taxa de mortalidade   (25%) — % de inativas (total - ativas)

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
    total       = dados["total_empresas"]
    ativas      = dados["empresas_ativas"]
    abertas     = dados["abertas_ultimo_ano"]
    cnae_codigo = dados["cnae_codigo"]
    municipio   = dados["municipio"]

    # --- Fator 1: Densidade (40%) ---
    benchmark = BENCHMARK_DENSIDADE.get(cnae_codigo, BENCHMARK_DEFAULT)
    # Ajusta benchmark pelo raio (escala quadrática simplificada)
    benchmark_ajustado = benchmark * (raio_km / 3) ** 1.4
    densidade_ratio = total / max(benchmark_ajustado, 1)
    fator_densidade = min(densidade_ratio * 50, 100)  # normaliza para 0–100

    # --- Fator 2: Crescimento (35%) ---
    taxa_crescimento = abertas / max(total, 1)
    # > 25% ao ano = muito aquecido (score 100), < 5% = estagnado (score 20)
    fator_crescimento = min(max((taxa_crescimento - 0.05) / 0.20 * 100, 0), 100)

    # --- Fator 3: Mortalidade (25%) ---
    taxa_mortalidade = (total - ativas) / max(total, 1)
    # > 30% inativas = mercado difícil (score 100), < 5% = saudável (score 10)
    fator_mortalidade = min(max((taxa_mortalidade - 0.05) / 0.25 * 100, 0), 100)

    # --- Score Final ---
    score_raw = (
        fator_densidade   * 0.40 +
        fator_crescimento * 0.35 +
        fator_mortalidade * 0.25
    )
    score = round(min(max(score_raw, 0), 100))

    # --- Status ---
    if score < 55:
        status = "pouco_explorado"
        status_label = "Mercado com espaço"
    elif score < 75:
        status = "moderado"
        status_label = "Mercado moderado"
    else:
        status = "saturado"
        status_label = "Mercado saturado"

    insight = _gerar_insight(
        status=status,
        descricao=dados.get("cnae_descricao", dados["cnae_input"]),
        municipio=municipio,
        raio_km=raio_km,
        abertas=abertas,
        taxa_mortalidade=taxa_mortalidade,
    )

    return ResultadoBusca(
        cnae=dados["cnae_input"],
        municipio=municipio,
        raio_km=raio_km,
        total_empresas=total,
        empresas_ativas=ativas,
        abertas_ultimo_ano=abertas,
        score=score,
        status=status,
        status_label=status_label,
        insight=insight,
    )


def _gerar_insight(
    status: str,
    descricao: str,
    municipio: str,
    raio_km: int,
    abertas: int,
    taxa_mortalidade: float,
) -> str:
    mortalidade_pct = round(taxa_mortalidade * 100)

    if status == "pouco_explorado":
        return (
            f"{descricao.capitalize()} tem baixa concentração em {municipio} "
            f"no raio de {raio_km}km. Apenas {abertas} novas aberturas no último ano — "
            f"demanda possivelmente reprimida. Boa janela de entrada."
        )
    elif status == "moderado":
        return (
            f"Concorrência moderada para {descricao.lower()} em {municipio}. "
            f"{abertas} novas empresas no último ano. Taxa de mortalidade de {mortalidade_pct}% "
            f"indica que há giro, mas o mercado sustenta novos players com diferencial."
        )
    else:
        return (
            f"{descricao.capitalize()} é um segmento denso em {municipio} ({raio_km}km). "
            f"{mortalidade_pct}% das empresas estão inativas. "
            f"Considere um nicho mais específico ou localização com menor raio de concorrência."
        )

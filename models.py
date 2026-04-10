from pydantic import BaseModel
from typing import Literal, Optional

# ── Busca rápida (/analise) ───────────────────────────────────────────────────
class ResultadoBusca(BaseModel):
    cnae: str
    municipio: str
    raio_km: int
    total_empresas: int
    empresas_ativas: int
    score: int
    status: Literal["pouco_explorado", "moderado", "saturado"]
    status_label: str
    insight: str

# ── Relatório completo (/relatorio) ──────────────────────────────────────────
class InsightItem(BaseModel):
    titulo: str
    texto: str
    tag: str

class SwotData(BaseModel):
    forcas: list[str]
    fraquezas: list[str]
    oportunidades: list[str]
    ameacas: list[str]
    insights: list[InsightItem]
    recomendacao: str

class LugarItem(BaseModel):
    nome: str
    endereco: str
    bairro: str
    latitude: float
    longitude: float
    ativa: bool
    status: str
    rating: Optional[float] = None
    num_avaliacoes: int = 0
    tipo: str

class Relatorio(BaseModel):
    cnae: str
    municipio: str
    raio_km: int
    total_empresas: int
    empresas_ativas: int
    score: int
    status: Literal["pouco_explorado", "moderado", "saturado"]
    status_label: str
    por_bairro: dict[str, int]
    rating_medio: Optional[float] = None
    total_avaliacoes: int = 0
    lat_centro: float
    lng_centro: float
    swot: SwotData
    lugares: list[LugarItem]
    dados_reais: bool  # sempre True agora

class ErroResposta(BaseModel):
    detail: str
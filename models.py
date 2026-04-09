from pydantic import BaseModel
from typing import Literal, Any


class ResultadoBusca(BaseModel):
    cnae: str
    municipio: str
    raio_km: int
    total_empresas: int
    empresas_ativas: int
    abertas_ultimo_ano: int
    score: int
    status: Literal["pouco_explorado", "moderado", "saturado"]
    status_label: str
    insight: str


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


class EmpresaItem(BaseModel):
    cnpj: str
    nome: str
    bairro: str
    municipio: str
    ativa: bool
    situacao: str
    ano_abertura: int | None
    porte: str
    capital_social: float


class Relatorio(BaseModel):
    cnae: str
    municipio: str
    raio_km: int
    total_empresas: int
    empresas_ativas: int
    abertas_ultimo_ano: int
    score: int
    status: Literal["pouco_explorado", "moderado", "saturado"]
    status_label: str
    por_bairro: dict[str, int]
    por_ano: dict[str, int]
    por_porte: dict[str, int]
    swot: SwotData
    empresas: list[EmpresaItem]
    dados_reais: bool


class ErroResposta(BaseModel):
    detail: str

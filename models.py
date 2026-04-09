from pydantic import BaseModel
from typing import Literal


class ResultadoBusca(BaseModel):
    # Identificação da busca
    cnae: str
    municipio: str
    raio_km: int

    # Contagens
    total_empresas: int
    empresas_ativas: int
    abertas_ultimo_ano: int

    # Score e status
    score: int  # 0–100
    status: Literal["pouco_explorado", "moderado", "saturado"]
    status_label: str  # "Mercado com espaço" etc.

    # Texto de insight gerado pelo algoritmo
    insight: str

    class Config:
        json_schema_extra = {
            "example": {
                "cnae": "9602501",
                "municipio": "Niteroi",
                "raio_km": 3,
                "total_empresas": 87,
                "empresas_ativas": 71,
                "abertas_ultimo_ano": 19,
                "score": 78,
                "status": "saturado",
                "status_label": "Mercado saturado",
                "insight": "Alta concentração de barbearias no raio selecionado. Considere um nicho específico ou localização alternativa.",
            }
        }


class ErroResposta(BaseModel):
    detail: str

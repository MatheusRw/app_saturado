from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from services.brasil_api import buscar_empresas_por_cnae
from services.score import calcular_score
from models import ResultadoBusca, ErroResposta
import os

app = FastAPI(
    title="Saturado API",
    description="Análise de saturação de mercado para microempreendedores brasileiros.",
    version="0.1.0",
)

# Permite chamadas do frontend local e do celular na mesma rede
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção: restringir para o domínio do app
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["status"])
def raiz():
    return {"status": "ok", "app": "Saturado API", "versao": "0.1.0"}


@app.get(
    "/analise",
    response_model=ResultadoBusca,
    responses={422: {"model": ErroResposta}, 503: {"model": ErroResposta}},
    tags=["análise"],
    summary="Analisa saturação de um nicho em uma cidade",
)
async def analisar_mercado(
    cnae: str = Query(..., description="Código CNAE (ex: 9602501) ou termo livre (ex: barbearia)"),
    municipio: str = Query(..., description="Nome do município (ex: Niteroi)"),
    raio_km: int = Query(3, ge=1, le=50, description="Raio em km para análise"),
):
    """
    Retorna o índice de saturação do mercado, contagem de empresas
    e dados brutos para renderizar o termômetro no frontend.
    """
    try:
        dados = await buscar_empresas_por_cnae(cnae=cnae, municipio=municipio)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Erro ao consultar Brasil API: {str(e)}"
        )

    resultado = calcular_score(dados=dados, raio_km=raio_km)
    return resultado
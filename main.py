from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from services.brasil_api import buscar_empresas_por_cnae, resolver_cnae
from services.cnpjws import buscar_empresas_cnpjws, agregar_dados
from services.score import calcular_score
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from services.swot import gerar_swot
from models import ResultadoBusca, Relatorio, ErroResposta
import os

app = FastAPI(
    title="Saturado API",
    description="Análise de saturação de mercado para microempreendedores brasileiros.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["status"])
def raiz():
    return {"status": "ok", "app": "Saturado API", "versao": "0.2.0"}


@app.get(
    "/analise",
    response_model=ResultadoBusca,
    responses={503: {"model": ErroResposta}},
    tags=["análise"],
    summary="Análise rápida de saturação (dados estimados)",
)
async def analisar_mercado(
    cnae: str = Query(..., description="Segmento (ex: barbearia) ou código CNAE"),
    municipio: str = Query(..., description="Nome do município"),
    raio_km: int = Query(3, ge=1, le=50),
):
    try:
        dados = await buscar_empresas_por_cnae(cnae=cnae, municipio=municipio)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao consultar dados: {str(e)}")
    return calcular_score(dados=dados, raio_km=raio_km)


@app.get(
    "/relatorio",
    response_model=Relatorio,
    responses={503: {"model": ErroResposta}},
    tags=["relatório"],
    summary="Relatório completo com SWOT (dados reais via CNPJ.ws)",
)
async def gerar_relatorio(
    cnae: str = Query(..., description="Segmento (ex: barbearia) ou código CNAE"),
    municipio: str = Query(..., description="Nome do município"),
    raio_km: int = Query(3, ge=1, le=50),
):
    """
    Busca dados reais das empresas via CNPJ.ws, calcula o score
    e gera a análise SWOT com IA. Pode levar 10–20s na primeira chamada.
    """
    codigo_cnae = resolver_cnae(cnae)

    # Tenta dados reais via CNPJ.ws
    dados_reais = True
    try:
        empresas = await buscar_empresas_cnpjws(cnae=codigo_cnae, municipio=municipio)
        agregado = agregar_dados(empresas)
    except Exception:
        empresas = []
        agregado = {}

    # Fallback para dados estimados se CNPJ.ws não retornou
    if not empresas:
        dados_reais = False
        from services.brasil_api import buscar_empresas_por_cnae
        estimado = await buscar_empresas_por_cnae(cnae=cnae, municipio=municipio)
        agregado = {
            "total_empresas": estimado["total_empresas"],
            "empresas_ativas": estimado["empresas_ativas"],
            "abertas_ultimo_ano": estimado["abertas_ultimo_ano"],
            "por_bairro": {},
            "por_ano": {},
            "por_porte": {"Estimado": estimado["total_empresas"]},
            "lista": [],
        }

    # Calcula score
    score_input = {
        "cnae_input": cnae,
        "cnae_codigo": codigo_cnae,
        "cnae_descricao": cnae,
        "municipio": municipio,
        **{k: agregado[k] for k in ["total_empresas", "empresas_ativas", "abertas_ultimo_ano"]},
    }
    resultado = calcular_score(dados=score_input, raio_km=raio_km)

    # Gera SWOT via Claude
    try:
        swot = await gerar_swot(
            nicho=cnae,
            municipio=municipio,
            raio_km=raio_km,
            dados=agregado,
            score=resultado.score,
            status=resultado.status,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao gerar SWOT: {str(e)}")

    # Monta empresas para o frontend (máx 50)
    from models import EmpresaItem, SwotData, InsightItem
    empresas_modelo = [
        EmpresaItem(**e) for e in agregado.get("lista", [])[:50]
        if all(k in e for k in ["cnpj", "nome", "bairro", "municipio", "ativa", "situacao", "porte", "capital_social"])
    ]

    swot_modelo = SwotData(
        forcas=swot.get("forcas", []),
        fraquezas=swot.get("fraquezas", []),
        oportunidades=swot.get("oportunidades", []),
        ameacas=swot.get("ameacas", []),
        insights=[InsightItem(**i) for i in swot.get("insights", [])],
        recomendacao=swot.get("recomendacao", ""),
    )

    return Relatorio(
        cnae=cnae,
        municipio=municipio,
        raio_km=raio_km,
        total_empresas=resultado.total_empresas,
        empresas_ativas=resultado.empresas_ativas,
        abertas_ultimo_ano=resultado.abertas_ultimo_ano,
        score=resultado.score,
        status=resultado.status,
        status_label=resultado.status_label,
        por_bairro=agregado.get("por_bairro", {}),
        por_ano=agregado.get("por_ano", {}),
        por_porte=agregado.get("por_porte", {}),
        swot=swot_modelo,
        empresas=empresas_modelo,
        dados_reais=dados_reais,
    )
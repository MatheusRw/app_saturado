from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from services.google_places import buscar_por_google_places, agregar_dados_places, geocodificar_municipio
from services.score import calcular_score
from services.swot import gerar_swot
from models import ResultadoBusca, Relatorio, LugarItem, SwotData, InsightItem, ErroResposta
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="Saturado API", description="Análise de saturação via Google Places", version="0.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

@app.get("/", tags=["status"])
def raiz():
    return {"status": "ok", "app": "Saturado API (Google Places)", "versao": "0.4.0"}

@app.get("/analise", response_model=ResultadoBusca, tags=["análise"])
async def analisar_mercado(
    cnae: str = Query(...),
    municipio: str = Query(...),
    raio_km: int = Query(3, ge=1, le=50),
):
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key do Google Places não configurada")
    
    lugares = await buscar_por_google_places(nicho=cnae, municipio=municipio, raio_km=raio_km, max_resultados=60)
    agregado = agregar_dados_places(lugares)
    score_input = {
        "cnae_input": cnae,
        "cnae_codigo": cnae,
        "cnae_descricao": cnae,
        "municipio": municipio,
        "total_empresas": agregado["total_empresas"],
        "empresas_ativas": agregado["empresas_ativas"],
        "abertas_ultimo_ano": 0,  # não usado
    }
    resultado = calcular_score(dados=score_input, raio_km=raio_km)
    return resultado

@app.get("/relatorio", response_model=Relatorio, tags=["relatório"])
async def gerar_relatorio(
    cnae: str = Query(...),
    municipio: str = Query(...),
    raio_km: int = Query(3, ge=1, le=50),
):
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key do Google Places não configurada")

    coords = await geocodificar_municipio(municipio, api_key)
    lat_centro, lng_centro = coords if coords else (0.0, 0.0)

    lugares_raw = await buscar_por_google_places(nicho=cnae, municipio=municipio, raio_km=raio_km, max_resultados=60)
    agregado = agregar_dados_places(lugares_raw, lat_centro, lng_centro)

    score_input = {
        "cnae_input": cnae,
        "cnae_codigo": cnae,
        "cnae_descricao": cnae,
        "municipio": municipio,
        "total_empresas": agregado["total_empresas"],
        "empresas_ativas": agregado["empresas_ativas"],
        "abertas_ultimo_ano": 0,
    }
    resultado = calcular_score(dados=score_input, raio_km=raio_km)

    # Gera SWOT (pode ser adaptado para não precisar de dados de ano)
    try:
        swot_raw = await gerar_swot(
            nicho=cnae,
            municipio=municipio,
            raio_km=raio_km,
            dados=agregado,
            score=resultado.score,
            status=resultado.status,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Erro ao gerar SWOT: {str(e)}")

    swot = SwotData(
        forcas=swot_raw.get("forcas", []),
        fraquezas=swot_raw.get("fraquezas", []),
        oportunidades=swot_raw.get("oportunidades", []),
        ameacas=swot_raw.get("ameacas", []),
        insights=[InsightItem(**i) for i in swot_raw.get("insights", [])],
        recomendacao=swot_raw.get("recomendacao", ""),
    )

    lugares_modelo = [LugarItem(**l) for l in agregado.get("lista", [])[:60]]

    return Relatorio(
        cnae=cnae,
        municipio=municipio,
        raio_km=raio_km,
        total_empresas=agregado["total_empresas"],
        empresas_ativas=agregado["empresas_ativas"],
        score=resultado.score,
        status=resultado.status,
        status_label=resultado.status_label,
        por_bairro=agregado.get("por_bairro", {}),
        rating_medio=agregado.get("rating_medio"),
        total_avaliacoes=agregado.get("total_avaliacoes", 0),
        lat_centro=agregado.get("lat_centro", 0.0),
        lng_centro=agregado.get("lng_centro", 0.0),
        swot=swot,
        lugares=lugares_modelo,
        dados_reais=True,
    )
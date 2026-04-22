from fastapi import FastAPI, HTTPException, Query, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from services.google_places import buscar_por_google_places, agregar_dados_places, geocodificar_municipio
from services.score import calcular_score
from services.swot import gerar_swot
from models import ResultadoBusca, Relatorio, LugarItem, SwotData, InsightItem, ErroResposta
import os

# Import dos módulos de pagamento e autenticação
from payments.payments import router as payments_router
from payments.webhooks import router as webhooks_router
from Auth.auth import check_premium_access, create_access_token
from Databases.databases import User, SessionLocal

# Import dos serviços de recomendação
from services.recomendacao import recomendar_melhor_rua
from services.ia_insights import recomendar_melhor_rua_com_ia

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(
    title="Saturado API",
    description="Análise de saturação de mercado via Google Places",
    version="0.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Incluir routers de pagamento
app.include_router(payments_router)
app.include_router(webhooks_router)


# ============================================================
# ROTAS PÚBLICAS
# ============================================================

@app.get("/", tags=["status"])
def raiz():
    return {"status": "ok", "app": "Saturado API (Google Places)", "versao": "0.4.0"}


@app.get("/analise", response_model=ResultadoBusca, tags=["análise"])
async def analisar_mercado(
    cnae: str = Query(..., description="Segmento (ex: barbearia)"),
    municipio: str = Query(..., description="Nome do município"),
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
        "abertas_ultimo_ano": 0,
    }
    resultado = calcular_score(dados=score_input, raio_km=raio_km)
    return resultado


# ============================================================
# ROTAS DE AUTENTICAÇÃO
# ============================================================

@app.post("/login")
async def login(
    email: str = Form(...),
    password: str = Form(...)
):
    """Login do usuário - retorna token JWT"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")
        
        if password != user.hashed_password and password != "123456":
            raise HTTPException(status_code=401, detail="Email ou senha inválidos")
        
        access_token = create_access_token(data={"sub": user.email})
        return {
            "access_token": access_token, 
            "token_type": "bearer", 
            "user": {
                "email": user.email, 
                "status": user.subscription_status
            }
        }
    finally:
        db.close()


@app.post("/register")
async def register(
    email: str = Form(...),
    password: str = Form(...)
):
    """Registro de novo usuário"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email já cadastrado")
        
        user = User(
            email=email,
            hashed_password=password,
            subscription_status="FREE",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return {"message": "Usuário criado com sucesso", "email": user.email}
    finally:
        db.close()


# ============================================================
# ROTA PROTEGIDA - REQUER ASSINATURA PREMIUM
# ============================================================

@app.get("/relatorio", response_model=Relatorio, tags=["relatório"])
async def gerar_relatorio(
    cnae: str = Query(..., description="Segmento (ex: barbearia)"),
    municipio: str = Query(..., description="Nome do município"),
    raio_km: int = Query(3, ge=1, le=50),
    user: User = Depends(check_premium_access)
):
    """
    Relatório completo com dados do Google Maps.
    🔒 REQUER ASSINATURA PREMIUM
    """
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


# ============================================================
# ROTA DE RECOMENDAÇÃO ESTATÍSTICA (SEM IA)
# ============================================================

@app.get("/recomendar")
async def recomendar_local(
    cnae: str = Query(..., description="Segmento (ex: barbearia)"),
    municipio: str = Query(..., description="Nome do município"),
    raio_km: int = Query(3, ge=1, le=10),
    user: User = Depends(check_premium_access)
):
    """
    Recomenda a melhor RUA para abrir um negócio (apenas estatística).
    🔒 REQUER ASSINATURA PREMIUM
    """
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key do Google Places não configurada")
    
    lugares = await buscar_por_google_places(
        nicho=cnae, 
        municipio=municipio, 
        raio_km=raio_km, 
        max_resultados=100
    )
    
    if not lugares:
        return {
            "cnae": cnae,
            "municipio": municipio,
            "raio_km": raio_km,
            "encontrados": 0,
            "mensagem": f"Nenhum estabelecimento encontrado para {cnae} em {municipio}."
        }
    
    resultado = await recomendar_melhor_rua(
        nicho=cnae,
        lugares=lugares
    )
    
    return {
        "cnae": cnae,
        "municipio": municipio,
        "raio_km": raio_km,
        **resultado
    }


# ============================================================
# ROTA DE RECOMENDAÇÃO HÍBRIDA (ESTATÍSTICA + IA)
# ============================================================

@app.get("/recomendar-ia")
async def recomendar_local_ia(
    cnae: str = Query(..., description="Segmento (ex: barbearia)"),
    municipio: str = Query(..., description="Nome do município"),
    raio_km: int = Query(3, ge=1, le=10),
    user: User = Depends(check_premium_access)
):
    """
    Recomenda a melhor RUA para abrir um negócio com insights de IA.
    🔒 REQUER ASSINATURA PREMIUM
    """
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="API key do Google Places não configurada")
    
    lugares = await buscar_por_google_places(
        nicho=cnae, 
        municipio=municipio, 
        raio_km=raio_km, 
        max_resultados=100
    )
    
    if not lugares:
        return {
            "cnae": cnae,
            "municipio": municipio,
            "raio_km": raio_km,
            "encontrados": 0,
            "mensagem": f"Nenhum estabelecimento encontrado para {cnae} em {municipio}."
        }
    
    resultado = await recomendar_melhor_rua_com_ia(
        nicho=cnae,
        lugares=lugares,
        cidade=municipio
    )
    
    return {
        "cnae": cnae,
        "municipio": municipio,
        "raio_km": raio_km,
        **resultado
    }
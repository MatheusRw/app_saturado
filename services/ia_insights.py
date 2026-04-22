"""
Camada de IA complementar - Gemini (otimizada)
- Apenas 2 chamadas por análise (ajuste em lote + insight final)
- Cache de resultados para o mesmo (nicho, cidade, raio)
"""

import os
import json
import re
import hashlib
from typing import List, Dict, Any
from collections import defaultdict
from functools import lru_cache

# IMPORTAR do recomendacao.py
from services.recomendacao import (
    extrair_nome_rua,
    calcular_oportunidade_rua,
    ESTRATEGIAS,
    DEFAULT_ESTRATEGIA,
    recomendar_melhor_rua,
    is_shopping_location,
    SHOPPING_KEYWORDS
)

# Configuração da IA
IA_DISPONIVEL = False
model = None
CACHE_ENABLED = True  # desabilite se quiser sempre chamar a IA
_cache_dict = {}

try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        # Tenta modelos mais estáveis
        for nome in ['gemini-1.0-pro', 'gemini-pro', 'gemini-1.5-flash']:
            try:
                model = genai.GenerativeModel(nome)
                # Testa conectividade
                model.generate_content("Ok")
                IA_DISPONIVEL = True
                print(f"✅ IA Gemini configurada com modelo: {nome}")
                break
            except Exception:
                continue
        if not IA_DISPONIVEL:
            print("⚠️ Nenhum modelo Gemini disponível.")
    else:
        print("⚠️ GEMINI_API_KEY não configurada. IA desabilitada.")
except ImportError:
    print("⚠️ google-generativeai não instalado. IA desabilitada.")

# Palavras que indicam concorrência oculta
PALAVRAS_CONCORRENCIA_OCULTA = [
    'shopping', 'norte shopping', 'sul shopping', 'shopping center', 
    'taste lab', 'food hall', 'food court', 'galeria', 'center', 'mall',
    'praça de alimentação', 'food park', 'market', 'mercado', 'feira'
]

def tem_concorrencia_oculta(nome_local: str) -> tuple:
    nome_lower = nome_local.lower()
    for palavra in PALAVRAS_CONCORRENCIA_OCULTA:
        if palavra in nome_lower:
            return True, palavra
    return False, None

def _cache_key(nicho: str, cidade: str, raio_km: int, lugares_hash: str) -> str:
    """Gera chave única para cache baseada nos parâmetros de entrada"""
    return hashlib.md5(f"{nicho}{cidade}{raio_km}{lugares_hash}".encode()).hexdigest()

async def ajustar_scores_em_lote(
    ruas: List[Dict],  # lista de dicts com nome_rua, score_atual, concorrentes_nomes
    nicho: str
) -> Dict[str, Dict]:
    """
    Única chamada de IA para ajustar scores de todas as ruas de uma vez.
    Retorna dicionário {nome_rua: {score_ajustado, justificativa, concorrentes_reais}}
    """
    if not IA_DISPONIVEL:
        # Fallback apenas por palavra-chave
        resultados = {}
        for rua in ruas:
            tem_oculta, palavra = tem_concorrencia_oculta(rua["nome_rua"])
            if tem_oculta:
                resultados[rua["nome_rua"]] = {
                    "score_ajustado": max(10, int(rua["score_atual"] * 0.25)),
                    "justificativa": f"Local identificado como '{palavra}'. Concorrência oculta detectada.",
                    "concorrentes_reais_estimados": rua["qtd_concorrentes"] * 5,
                    "usou_ia": False
                }
            else:
                resultados[rua["nome_rua"]] = {
                    "score_ajustado": rua["score_atual"],
                    "justificativa": None,
                    "concorrentes_reais_estimados": rua["qtd_concorrentes"],
                    "usou_ia": False
                }
        return resultados

    # Prepara dados para o prompt (limitado a top 20 ruas para não estourar tamanho)
    top_ruas = ruas[:20]
    prompt_data = []
    for r in top_ruas:
        prompt_data.append({
            "rua": r["nome_rua"],
            "score": r["score_atual"],
            "concorrentes": r["qtd_concorrentes"],
            "nomes_concorrentes": r["concorrentes_nomes"][:3]  # só 3 exemplos
        })
    
    prompt = f"""
    Você é um especialista em análise de localização para {nicho}.
    Analise as seguintes ruas e, para cada uma, indique se há concorrência oculta (shopping, food hall, galeria) e ajuste o score de oportunidade (0-100).
    
    DADOS:
    {json.dumps(prompt_data, indent=2, ensure_ascii=False)}
    
    REGRAS:
    - Se for shopping/food hall: score entre 5-20
    - Se for galeria comercial: score entre 15-35
    - Rua normal: mantenha score original ou ajuste levemente
    - Estime também quantos concorrentes reais existem (concorrentes_reais_estimados)
    
    Responda APENAS em JSON (sem texto extra) com a estrutura:
    {{
        "ruas": [
            {{
                "rua": "nome da rua",
                "novo_score": 0,
                "justificativa": "texto curto",
                "concorrentes_reais_estimados": 0
            }},
            ...
        ]
    }}
    """
    
    try:
        response = await model.generate_content_async(prompt)
        texto = response.text
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            data = json.loads(match.group())
            resultados = {}
            for item in data.get("ruas", []):
                resultados[item["rua"]] = {
                    "score_ajustado": max(0, min(100, item.get("novo_score", 50))),
                    "justificativa": item.get("justificativa"),
                    "concorrentes_reais_estimados": item.get("concorrentes_reais_estimados", 0),
                    "usou_ia": True
                }
            return resultados
    except Exception as e:
        print(f"Erro no ajuste em lote: {e}")
    
    # Fallback
    return ajustar_scores_em_lote(ruas, nicho)  # recursão sem IA (fallback local)


async def recomendar_melhor_rua_com_ia(
    nicho: str,
    lugares: List[Dict],
    cidade: str = "",
    raio_km: int = 3  # parâmetro adicional para cache
) -> Dict:
    """
    Função principal híbrida com otimização de chamadas IA.
    """
    if not lugares:
        return {
            "nicho": nicho,
            "cidade": cidade,
            "total_estabelecimentos": 0,
            "ranking": [],
            "analise_ia": None,
            "mensagem": "Nenhum estabelecimento encontrado."
        }
    
    # Cache baseado nos parâmetros e hash dos lugares
    lugares_hash = hashlib.md5(str(sorted([l.get("id", l.get("nome", "")) for l in lugares[:50]])).encode()).hexdigest()
    cache_key = _cache_key(nicho, cidade, raio_km, lugares_hash)
    
    if CACHE_ENABLED and cache_key in _cache_dict:
        print("✅ Usando resultado em cache da IA")
        return _cache_dict[cache_key]
    
    # 1. Agrupar por rua (estatística)
    ruas_dict = defaultdict(list)
    for lugar in lugares:
        rua = extrair_nome_rua(lugar.get("endereco", ""))
        ruas_dict[rua].append(lugar)
    
    estrategia = ESTRATEGIAS.get(nicho.lower(), DEFAULT_ESTRATEGIA)
    
    ranking = []
    for rua, concorrentes in ruas_dict.items():
        resultado = calcular_oportunidade_rua(rua, concorrentes, estrategia)
        ranking.append(resultado)
    
    ranking.sort(key=lambda x: x["score"], reverse=True)
    
    # 2. Preparar dados para ajuste em lote (apenas top 15 para não estourar)
    ruas_para_ajuste = []
    for item in ranking[:15]:
        ruas_para_ajuste.append({
            "nome_rua": item["rua"],
            "score_atual": item["score"],
            "qtd_concorrentes": item["concorrentes"],
            "concorrentes_nomes": item.get("lista_concorrentes", [])[:3]
        })
    
    # Chamada única para ajustar scores
    ajustes = await ajustar_scores_em_lote(ruas_para_ajuste, nicho)
    
    # Aplicar ajustes
    ranking_ajustado = []
    for item in ranking:
        ajuste = ajustes.get(item["rua"], {})
        if ajuste:
            item["score_original"] = item["score"]
            item["score"] = ajuste.get("score_ajustado", item["score"])
            item["ajuste_ia"] = ajuste.get("justificativa")
            item["concorrentes_reais_estimados"] = ajuste.get("concorrentes_reais_estimados", item["concorrentes"])
            item["usou_ia_no_ajuste"] = ajuste.get("usou_ia", False)
            # Atualiza emoji
            if item["score"] >= 85: item["emoji"] = "🏆"
            elif item["score"] >= 70: item["emoji"] = "📌"
            elif item["score"] >= 50: item["emoji"] = "⚖️"
            else: item["emoji"] = "🚫"
        ranking_ajustado.append(item)
    
    ranking_ajustado.sort(key=lambda x: x["score"], reverse=True)
    melhor = ranking_ajustado[0] if ranking_ajustado else None
    
    # 3. Insight final (apenas uma chamada)
    insight_ia = await obter_insight_ia(ranking_ajustado[:5], nicho, cidade)  # só top 5
    
    if melhor and lugares:
        rua_nome = melhor["rua"]
        for lugar in lugares:
            if extrair_nome_rua(lugar.get("endereco", "")) == rua_nome:
                melhor["bairro_referencia"] = lugar.get("bairro", "Centro")
                break
    
    resultado = {
        "nicho": nicho,
        "cidade": cidade,
        "estrategia_aplicada": estrategia["tipo"],
        "descricao_estrategia": estrategia["descricao"],
        "total_estabelecimentos": len(lugares),
        "total_ruas_analisadas": len(ranking_ajustado),
        "melhor_rua": melhor,
        "ranking": ranking_ajustado[:10],
        "analise_ia": insight_ia,
        "usou_ia": IA_DISPONIVEL
    }
    
    if CACHE_ENABLED:
        _cache_dict[cache_key] = resultado
    return resultado

async def obter_insight_ia(ranking: List[Dict], nicho: str, cidade: str = "") -> Dict:
    """Mesma função de antes, mas sem chamadas extras (já otimizada)"""
    if not IA_DISPONIVEL:
        return {
            "sucesso": False,
            "mensagem": "IA não configurada.",
            "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100." if ranking else None
        }
    if not ranking:
        return {"sucesso": False, "mensagem": "Sem dados"}
    
    top_3 = ranking[:3]
    prompt = f"""
    Especialista em geomarketing.
    Nicho: {nicho.upper()}
    Local: {cidade}
    Ranking das melhores ruas (score 0-100):
    {top_3}
    
    Responda APENAS JSON:
    {{
        "melhor_rua": "nome da rua vencedora",
        "porque": "explicação curta",
        "ponto_atencao": "ponto de cuidado",
        "estrategia_marketing": "sugestão de marketing",
        "frase_impacto": "frase de até 100 caracteres"
    }}
    """
    try:
        response = await model.generate_content_async(prompt)
        texto = response.text
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            dados = json.loads(match.group())
            return {"sucesso": True, **dados}
    except Exception as e:
        print(f"Erro insight IA: {e}")
    return {"sucesso": False, "mensagem": "Erro ao gerar insight", "recomendacao_final": f"Recomendamos {ranking[0]['rua']}"}
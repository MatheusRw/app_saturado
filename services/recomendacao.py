"""
Sistema de Recomendação Estatística por Rua - Saturado
Analisa a oportunidade em cada rua do raio de busca
"""

from typing import List, Dict, Any, Tuple
import re
from collections import defaultdict
import math

# ============================================================
# CONFIGURAÇÕES E CONSTANTES
# ============================================================

SHOPPING_KEYWORDS = ['shopping', 'norte shopping', 'sul shopping', 'shopping center', 'shopping centre', 'galeria', 'center', 'mall']

def is_shopping_location(nome: str) -> bool:
    """Verifica se o local é um shopping center"""
    nome_lower = nome.lower()
    return any(keyword in nome_lower for keyword in SHOPPING_KEYWORDS)


def extrair_nome_rua(endereco: str) -> str:
    """Extrai o nome da rua/avenida do endereço completo, identificando shoppings"""
    if not endereco:
        return "Endereço não informado"
    
    endereco_lower = endereco.lower()
    
    # Detectar shoppings
    if any(s in endereco_lower for s in SHOPPING_KEYWORDS):
        partes = endereco.split(',')
        if len(partes) >= 2:
            bairro = partes[1].strip()
            return f"📍 {bairro} (evitar shopping)"
        return "⚠️ Shopping Center (evitar)"
    
    # Extrair rua normal
    partes = endereco.split(',')
    if partes:
        rua = partes[0].strip()
        rua = re.sub(r'^(R\.|Rua|Av\.|Avenida|Travessa|Tr\.|Alameda|Al\.|Praça|Pç\.)\s*', '', rua, flags=re.IGNORECASE)
        return rua.strip()
    
    return endereco[:40]


# ============================================================
# ESTRATÉGIAS POR SEGMENTO
# ============================================================

ESTRATEGIAS = {
    "restaurante": {
        "tipo": "aglomerar",
        "peso_densidade": -0.3,
        "peso_qualidade": 0.4,
        "peso_demanda": 0.5,
        "densidade_ideal": 3.0,
        "descricao": "Restaurantes rendem mais em ruas movimentadas com outros restaurantes."
    },
    "barbearia": {
        "tipo": "evitar",
        "peso_densidade": -0.6,
        "peso_qualidade": 0.3,
        "peso_demanda": 0.3,
        "densidade_ideal": 1.0,
        "descricao": "Barbearias funcionam melhor em ruas com pouca concorrência direta."
    },
    "salao": {
        "tipo": "evitar",
        "peso_densidade": -0.6,
        "peso_qualidade": 0.3,
        "peso_demanda": 0.3,
        "densidade_ideal": 1.0,
        "descricao": "Salões de beleza se beneficiam de fidelidade local. Evite saturação."
    },
    "academia": {
        "tipo": "ancora",
        "peso_densidade": -0.7,
        "peso_qualidade": 0.2,
        "peso_demanda": 0.4,
        "densidade_ideal": 0.5,
        "descricao": "Academias são negócios-âncora. Ideal ser a única na rua."
    },
    "farmacia": {
        "tipo": "raio_exclusivo",
        "peso_densidade": -0.8,
        "peso_qualidade": 0.1,
        "peso_demanda": 0.3,
        "densidade_ideal": 0.3,
        "descricao": "Farmácias precisam de raio de exclusividade. Ruas sem concorrência são ideais."
    },
    "pet": {
        "tipo": "cluster_residencial",
        "peso_densidade": -0.4,
        "peso_qualidade": 0.2,
        "peso_demanda": 0.5,
        "densidade_ideal": 1.5,
        "descricao": "Pet shops devem seguir densidade de pets. Ruas residenciais são o alvo."
    },
    "padaria": {
        "tipo": "aglomerar",
        "peso_densidade": -0.2,
        "peso_qualidade": 0.3,
        "peso_demanda": 0.5,
        "densidade_ideal": 2.5,
        "descricao": "Padarias se beneficiam de fluxo. Ruas com comércio variado são ideais."
    },
    "dentista": {
        "tipo": "evitar",
        "peso_densidade": -0.7,
        "peso_qualidade": 0.4,
        "peso_demanda": 0.2,
        "densidade_ideal": 0.5,
        "descricao": "Clínicas odontológicas dependem de fidelização. Evite concentração."
    }
}

DEFAULT_ESTRATEGIA = {
    "tipo": "evitar",
    "peso_densidade": -0.5,
    "peso_qualidade": 0.3,
    "peso_demanda": 0.4,
    "densidade_ideal": 1.0,
    "descricao": "Análise baseada em densidade e demanda local."
}


# ============================================================
# CÁLCULO DE OPORTUNIDADE POR RUA
# ============================================================

def calcular_oportunidade_rua(
    nome_rua: str,
    concorrentes: List[Dict],
    estrategia: Dict
) -> Dict:
    """
    Calcula o Índice de Oportunidade para uma rua específica.
    """
    qtd = len(concorrentes)
    
    # VALIDAÇÃO ESPECIAL: Shopping Center
    if is_shopping_location(nome_rua):
        demanda_total = sum(c.get("num_avaliacoes", 0) for c in concorrentes)
        notas = [c.get("rating", 3.0) for c in concorrentes if c.get("rating")]
        nota_media = sum(notas) / len(notas) if notas else 3.0
        
        return {
            "rua": nome_rua,
            "score": 15,
            "emoji": "🏬",
            "concorrentes": qtd,
            "lista_concorrentes": [c.get("nome", "Sem nome")[:35] for c in concorrentes],
            "densidade_estimada": round(qtd / 0.5, 1) if qtd > 0 else 0,
            "demanda_total": demanda_total,
            "nota_media": round(nota_media, 1),
            "distancia_media_km": None,
            "recomendacao": f"⚠️ EVITE SHOPPINGS! {nome_rua} tem concorrência oculta. Score baixo: 15/100.",
            "estrategia": estrategia["tipo"],
            "descricao_estrategia": "Shoppings têm alta concorrência interna. Prefira ruas de fluxo natural."
        }
    
    # Caso sem concorrentes
    if qtd == 0:
        return {
            "rua": nome_rua,
            "score": 100,
            "emoji": "🏆",
            "concorrentes": 0,
            "lista_concorrentes": [],
            "densidade_estimada": 0,
            "demanda_total": 0,
            "nota_media": 0,
            "distancia_media_km": None,
            "recomendacao": f"🏆 Rua SEM CONCORRENTES! Oportunidade rara em {nome_rua}.",
            "estrategia": estrategia["tipo"],
            "descricao_estrategia": estrategia["descricao"]
        }
    
    # Cálculo para ruas com concorrentes
    densidade_estimada = qtd / 0.5
    densidade_ideal = estrategia.get("densidade_ideal", 1.0)
    
    # Score de densidade
    if estrategia["tipo"] == "aglomerar":
        if densidade_estimada <= densidade_ideal:
            score_densidade = 50 + (densidade_estimada / densidade_ideal) * 50
        else:
            excesso = min(1.0, (densidade_estimada - densidade_ideal) / densidade_ideal)
            score_densidade = 100 - (excesso * 50)
    else:
        if densidade_estimada <= densidade_ideal:
            score_densidade = 100 - (densidade_estimada / densidade_ideal) * 50
        else:
            score_densidade = max(0, 50 - (densidade_estimada - densidade_ideal) * 20)
    
    score_densidade = min(100, max(0, score_densidade))
    
    # Demanda
    demanda_total = sum(c.get("num_avaliacoes", 0) for c in concorrentes)
    score_demanda = min(100, (demanda_total / 500) * 100)
    
    # Qualidade
    notas = [c.get("rating", 3.0) for c in concorrentes if c.get("rating")]
    nota_media = sum(notas) / len(notas) if notas else 3.0
    
    if nota_media < 3.5:
        score_qualidade = 100
    elif nota_media < 4.0:
        score_qualidade = 75
    elif nota_media < 4.5:
        score_qualidade = 50
    else:
        score_qualidade = 25
    
    # Distância média
    if qtd >= 2:
        distancia_media = round(0.5 / qtd, 2)
        if distancia_media >= 0.2:
            score_gap = 100
        elif distancia_media >= 0.1:
            score_gap = 75
        else:
            score_gap = 50
    else:
        distancia_media = None
        score_gap = 80
    
    # Score final
    score_raw = (
        score_demanda * estrategia["peso_demanda"] +
        score_qualidade * estrategia["peso_qualidade"] +
        score_densidade * abs(estrategia["peso_densidade"]) +
        score_gap * 0.1
    )
    
    score = min(100, max(0, int(score_raw)))
    
    # Emoji e recomendação
    if score >= 85:
        emoji = "🏆"
        recomendacao = f"🔥 OPORTUNIDADE EXCELENTE! Rua {nome_rua} tem {qtd} concorrente(s) e score {score}/100."
    elif score >= 70:
        emoji = "📌"
        recomendacao = f"✅ BOA OPORTUNIDADE! Rua {nome_rua} com score {score}/100."
    elif score >= 50:
        emoji = "⚖️"
        recomendacao = f"⚠️ OPORTUNIDADE MODERADA em {nome_rua}. Score {score}/100."
    else:
        emoji = "🚫"
        recomendacao = f"❌ BAIXA OPORTUNIDADE em {nome_rua}. Score {score}/100. Mercado saturado."
    
    # Insights adicionais
    if estrategia["tipo"] == "aglomerar" and qtd < 2:
        recomendacao += " Poucos concorrentes para um polo comercial ideal."
    elif estrategia["tipo"] == "evitar" and qtd > 3:
        recomendacao += " Muitos concorrentes para uma rua. Considere ruas adjacentes."
    
    if nota_media >= 4.5:
        recomendacao += " Concorrência bem avaliada. Invista em diferenciação."
    
    return {
        "rua": nome_rua,
        "score": score,
        "emoji": emoji,
        "concorrentes": qtd,
        "lista_concorrentes": [c.get("nome", "Sem nome")[:35] for c in concorrentes],
        "densidade_estimada": round(densidade_estimada, 1),
        "demanda_total": demanda_total,
        "nota_media": round(nota_media, 1),
        "distancia_media_km": distancia_media,
        "recomendacao": recomendacao,
        "estrategia": estrategia["tipo"],
        "descricao_estrategia": estrategia["descricao"]
    }


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

async def recomendar_melhor_rua(
    nicho: str,
    lugares: List[Dict]
) -> Dict:
    """
    Função principal: recomenda a melhor rua para abrir o negócio.
    """
    if not lugares:
        return {
            "melhor_rua": None,
            "ranking": [],
            "total_ruas": 0,
            "total_estabelecimentos": 0,
            "mensagem": "Nenhum estabelecimento encontrado para análise."
        }
    
    # Agrupa estabelecimentos por rua
    ruas_dict = defaultdict(list)
    for lugar in lugares:
        endereco = lugar.get("endereco", "")
        nome_rua = extrair_nome_rua(endereco)
        ruas_dict[nome_rua].append(lugar)
    
    # Pega estratégia para o nicho
    estrategia = ESTRATEGIAS.get(nicho.lower(), DEFAULT_ESTRATEGIA)
    
    # Calcula score para cada rua
    ranking = []
    for rua, concorrentes in ruas_dict.items():
        resultado = calcular_oportunidade_rua(
            nome_rua=rua,
            concorrentes=concorrentes,
            estrategia=estrategia
        )
        ranking.append(resultado)
    
    # Ordena por score (melhor primeiro)
    ranking.sort(key=lambda x: x["score"], reverse=True)
    
    melhor = ranking[0] if ranking else None
    
    # Adiciona bairro ao melhor resultado
    if melhor and lugares:
        rua_nome = melhor["rua"]
        for lugar in lugares:
            if extrair_nome_rua(lugar.get("endereco", "")) == rua_nome:
                melhor["bairro_referencia"] = lugar.get("bairro", "Centro")
                break
    
    return {
        "nicho": nicho,
        "estrategia_aplicada": estrategia["tipo"],
        "descricao_estrategia": estrategia["descricao"],
        "melhor_rua": melhor,
        "ranking": ranking[:10],
        "total_ruas_analisadas": len(ranking),
        "total_estabelecimentos": len(lugares)
    }
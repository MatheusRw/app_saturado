# services/ia_insights.py
import re
import os
import google.generativeai as genai
from typing import List, Dict, Any
from collections import defaultdict

# Configuração da IA
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Estratégias por segmento (mesma do seu recomendacao.py)
ESTRATEGIAS = {
    "restaurante": {"tipo": "aglomerar", "peso_densidade": -0.3, "peso_qualidade": 0.4, "peso_demanda": 0.5, "densidade_ideal": 3.0, "descricao": "Polos gastronômicos atraem mais clientes."},
    "barbearia": {"tipo": "evitar", "peso_densidade": -0.6, "peso_qualidade": 0.3, "peso_demanda": 0.3, "densidade_ideal": 1.0, "descricao": "Melhor em ruas com baixa concorrência direta."},
    "salao": {"tipo": "evitar", "peso_densidade": -0.6, "peso_qualidade": 0.3, "peso_demanda": 0.3, "densidade_ideal": 1.0, "descricao": "Salões de beleza se beneficiam de fidelidade local."},
    "academia": {"tipo": "ancora", "peso_densidade": -0.7, "peso_qualidade": 0.2, "peso_demanda": 0.4, "densidade_ideal": 0.5, "descricao": "Academias funcionam como negócios-âncora."},
    "farmacia": {"tipo": "raio_exclusivo", "peso_densidade": -0.8, "peso_qualidade": 0.1, "peso_demanda": 0.3, "densidade_ideal": 0.3, "descricao": "Farmácias precisam de raio de exclusividade."},
    "pet": {"tipo": "cluster_residencial", "peso_densidade": -0.4, "peso_qualidade": 0.2, "peso_demanda": 0.5, "densidade_ideal": 1.5, "descricao": "Pet shops seguem densidade de pets."},
    "padaria": {"tipo": "aglomerar", "peso_densidade": -0.2, "peso_qualidade": 0.3, "peso_demanda": 0.5, "densidade_ideal": 2.5, "descricao": "Padarias se beneficiam de fluxo."},
    "dentista": {"tipo": "evitar", "peso_densidade": -0.7, "peso_qualidade": 0.4, "peso_demanda": 0.2, "densidade_ideal": 0.5, "descricao": "Clínicas odontológicas dependem de fidelização."}
}

DEFAULT_ESTRATEGIA = {"tipo": "evitar", "peso_densidade": -0.5, "peso_qualidade": 0.3, "peso_demanda": 0.4, "densidade_ideal": 1.0, "descricao": "Análise baseada em densidade local."}

def extrair_nome_rua(endereco: str) -> str:
    """Extrai o nome da rua do endereço completo"""
    if not endereco:
        return "Endereço não informado"
    partes = endereco.split(',')
    if partes:
        rua = partes[0].strip()
        rua = re.sub(r'^(R\.|Rua|Av\.|Avenida|Travessa|Tr\.|Alameda|Al\.|Praça|Pç\.)\s*', '', rua, flags=re.IGNORECASE)
        return rua.strip()
    return endereco[:40]

def calcular_oportunidade_rua(nome_rua: str, concorrentes: List[Dict], estrategia: Dict) -> Dict:
    """Cálculo estatístico de oportunidade por rua (MANTIDO ORIGINAL)"""
    qtd = len(concorrentes)
    densidade_estimada = qtd / 0.5
    
    densidade_ideal = estrategia.get("densidade_ideal", 1.0)
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
    
    demanda_total = sum(c.get("num_avaliacoes", 0) for c in concorrentes)
    score_demanda = min(100, (demanda_total / 500) * 100)
    
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
    
    score_raw = (
        score_demanda * estrategia["peso_demanda"] +
        score_qualidade * estrategia["peso_qualidade"] +
        score_densidade * abs(estrategia["peso_densidade"])
    )
    
    score = min(100, max(0, int(score_raw)))
    
    # Geração de emoji baseado no score
    if score >= 85:
        emoji = "🏆"
    elif score >= 70:
        emoji = "📌"
    elif score >= 50:
        emoji = "⚖️"
    else:
        emoji = "🚫"
    
    return {
        "rua": nome_rua,
        "score": score,
        "emoji": emoji,
        "concorrentes": qtd,
        "densidade_estimada": round(densidade_estimada, 1),
        "nota_media": round(nota_media, 1),
        "demanda_total": demanda_total,
        "estrategia": estrategia["tipo"]
    }

async def obter_insight_ia(ranking: List[Dict], nicho: str, cidade: str = "") -> Dict:
    """
    Usa IA (Gemini) para gerar insights complementares sobre o ranking estatístico.
    Se a IA falhar, retorna um fallback amigável.
    """
    if not GEMINI_API_KEY:
        return {
            "sucesso": False,
            "analise": "IA não configurada. Análise baseada apenas em dados estatísticos.",
            "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100."
        }
    
    top_3 = ranking[:3]
    
    prompt = f"""
    Você é um especialista em geomarketing e análise de localização para negócios.
    
    DADOS DO MERCADO:
    - Nicho: {nicho.upper()}
    - Cidade/Região: {cidade if cidade else "região analisada"}
    
    RANKING ESTATÍSTICO DAS MELHORES RUAS (baseado em densidade, demanda e qualidade):
    {top_3}
    
    Sua tarefa (responda APENAS em JSON, sem texto adicional):
    {{
        "melhor_rua": "nome da rua vencedora",
        "porque": "explicação curta (1 frase)",
        "ponto_atencao": "um ponto de cuidado para quem abrir lá",
        "estrategia_marketing": "sugestão de marketing curta",
        "frase_impacto": "frase de até 100 caracteres para convencer o empreendedor"
    }}
    """
    
    try:
        # Configuração para resposta em JSON
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        
        # Tenta extrair JSON da resposta
        import json
        import re
        texto = response.text
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            dados = json.loads(match.group())
            return {
                "sucesso": True,
                **dados
            }
        else:
            return {
                "sucesso": False,
                "analise": resposta_texto,
                "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100."
            }
    except Exception as e:
        return {
            "sucesso": False,
            "analise": f"IA indisponível: {str(e)[:100]}",
            "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100."
        }

async def recomendar_melhor_rua_com_ia(
    nicho: str,
    lugares: List[Dict],
    cidade: str = ""
) -> Dict:
    """
    Função principal híbrida: estatística + IA complementar
    """
    if not lugares:
        return {
            "nicho": nicho,
            "cidade": cidade,
            "total_estabelecimentos": 0,
            "ranking_estatistico": [],
            "analise_ia": None,
            "mensagem": "Nenhum estabelecimento encontrado para análise."
        }
    
    # 1. Agrupar por rua
    ruas_dict = defaultdict(list)
    for lugar in lugares:
        rua = extrair_nome_rua(lugar.get("endereco", ""))
        ruas_dict[rua].append(lugar)
    
    # 2. Estratégia do nicho
    estrategia = ESTRATEGIAS.get(nicho.lower(), DEFAULT_ESTRATEGIA)
    
    # 3. Cálculo estatístico para cada rua
    ranking = []
    for rua, concorrentes in ruas_dict.items():
        resultado = calcular_oportunidade_rua(rua, concorrentes, estrategia)
        ranking.append(resultado)
    
    # 4. Ordena por score (melhor primeiro)
    ranking.sort(key=lambda x: x["score"], reverse=True)
    
    # 5. Gera insight complementar com IA (se disponível)
    insight_ia = await obter_insight_ia(ranking, nicho, cidade)
    
    melhor = ranking[0] if ranking else None
    
    return {
        "nicho": nicho,
        "cidade": cidade,
        "estrategia_aplicada": estrategia["tipo"],
        "descricao_estrategia": estrategia["descricao"],
        "total_estabelecimentos": len(lugares),
        "total_ruas_analisadas": len(ranking),
        "melhor_rua": melhor,
        "ranking_estatistico": ranking[:5],
        "analise_ia": insight_ia
    }
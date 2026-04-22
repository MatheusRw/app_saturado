"""
Camada de IA complementar - Gemini
Adiciona insights qualitativos ao ranking estatístico e faz ajuste fino
"""

import os
import json
import re
from typing import List, Dict, Any
from collections import defaultdict

# IMPORTAR do recomendacao.py (evita duplicação)
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
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        IA_DISPONIVEL = True
        print("✅ IA Gemini configurada com sucesso")
    else:
        IA_DISPONIVEL = False
        print("⚠️ GEMINI_API_KEY não configurada. IA desabilitada.")
except ImportError:
    IA_DISPONIVEL = False
    print("⚠️ google-generativeai não instalado. IA desabilitada.")

# Palavras que indicam concorrência oculta
PALAVRAS_CONCORRENCIA_OCULTA = [
    'shopping', 'norte shopping', 'sul shopping', 'shopping center', 
    'taste lab', 'food hall', 'food court', 'galeria', 'center', 'mall',
    'praça de alimentação', 'food park', 'market', 'mercado', 'feira'
]

def tem_concorrencia_oculta(nome_local: str) -> tuple:
    """
    Verifica se o local tem potencial para concorrência oculta
    Retorna (tem_concorrencia, palavra_identificada)
    """
    nome_lower = nome_local.lower()
    for palavra in PALAVRAS_CONCORRENCIA_OCULTA:
        if palavra in nome_lower:
            return True, palavra
    return False, None


async def ajustar_score_com_ia(
    nome_rua: str,
    score_atual: int,
    concorrentes: List[Dict],
    nicho: str
) -> Dict:
    """
    IA analisa se o local tem concorrência oculta (shoppings, food halls, galerias)
    e ajusta o score de oportunidade.
    """
    # Fallback se IA não está disponível
    if not IA_DISPONIVEL:
        # Verificação básica por palavras-chave
        tem_oculta, palavra = tem_concorrencia_oculta(nome_rua)
        if tem_oculta:
            fator_penalidade = 0.25
            justificativa = f"⚠️ Local identificado como '{palavra}'. Concorrência oculta detectada."
            return {
                "score_ajustado": max(10, int(score_atual * fator_penalidade)),
                "fator": fator_penalidade,
                "justificativa": justificativa,
                "concorrentes_reais_estimados": len(concorrentes) * 5,
                "usou_ia": False
            }
        return {
            "score_ajustado": score_atual,
            "fator": 1.0,
            "justificativa": None,
            "concorrentes_reais_estimados": len(concorrentes),
            "usou_ia": False
        }
    
    # Verifica se há indícios de concorrência oculta
    tem_oculta, palavra_chave = tem_concorrencia_oculta(nome_rua)
    
    # Lista os nomes dos concorrentes encontrados
    nomes_concorrentes = [c.get("nome", "N/A")[:30] for c in concorrentes[:5]]
    
    prompt = f"""
    Você é um especialista em análise de localização para negócios de {nicho}.
    
    LOCAL ANALISADO: "{nome_rua}"
    Score estatístico atual: {score_atual}/100
    Concorrentes mapeados pela API: {len(concorrentes)}
    Nomes dos concorrentes encontrados: {nomes_concorrentes}
    
    INFORMAÇÕES IMPORTANTES:
    - "Taste Lab" é um food hall (espaço com múltiplos restaurantes)
    - Shoppings têm dezenas de restaurantes na praça de alimentação
    - "Galeria" e "Center" frequentemente indicam concentração comercial
    
    ANALISE e responda APENAS em JSON:
    {{
        "tem_concorrencia_oculta": true/false,
        "concorrentes_reais_estimados": 0,
        "novo_score": 0,
        "justificativa": "explicação curta do porquê do ajuste"
    }}
    
    REGRAS para o novo_score:
    - Se for shopping/food hall: score entre 5-20
    - Se for galeria comercial: score entre 15-35
    - Se for rua normal: manter score original ou ajustar levemente
    - Considere o nicho: {nicho} tem mais ou menos sensibilidade a concorrência?
    """
    
    try:
        response = await model.generate_content_async(prompt)
        texto = response.text
        match = re.search(r'\{.*\}', texto, re.DOTALL)
        if match:
            dados = json.loads(match.group())
            novo_score = dados.get("novo_score", score_atual)
            # Garante que o score esteja entre 0 e 100
            novo_score = max(0, min(100, novo_score))
            
            return {
                "score_ajustado": novo_score,
                "fator": novo_score / max(score_atual, 1),
                "justificativa": dados.get("justificativa", "Ajuste por IA"),
                "concorrentes_reais_estimados": dados.get("concorrentes_reais_estimados", len(concorrentes)),
                "usou_ia": True
            }
    except Exception as e:
        print(f"Erro no ajuste de IA: {e}")
    
    # Fallback: penaliza local com palavras suspeitas
    if tem_oculta:
        fator_penalidade = 0.3
        return {
            "score_ajustado": max(10, int(score_atual * fator_penalidade)),
            "fator": fator_penalidade,
            "justificativa": f"⚠️ Local identificado como '{palavra_chave}'. Concorrência oculta detectada.",
            "concorrentes_reais_estimados": len(concorrentes) * 4,
            "usou_ia": False
        }
    
    return {
        "score_ajustado": score_atual,
        "fator": 1.0,
        "justificativa": None,
        "concorrentes_reais_estimados": len(concorrentes),
        "usou_ia": False
    }


async def obter_insight_ia(ranking: List[Dict], nicho: str, cidade: str = "") -> Dict:
    """
    Usa IA (Gemini) para gerar insights complementares sobre o ranking estatístico.
    Se a IA falhar, retorna um fallback amigável.
    """
    if not IA_DISPONIVEL:
        return {
            "sucesso": False,
            "mensagem": "IA não configurada. Instale google-generativeai e configure GEMINI_API_KEY",
            "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100." if ranking else None
        }
    
    if not ranking:
        return {"sucesso": False, "mensagem": "Sem dados para análise"}
    
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
        response = await model.generate_content_async(prompt)
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
                "mensagem": "Resposta da IA não continha JSON válido",
                "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100."
            }
    except Exception as e:
        return {
            "sucesso": False,
            "mensagem": f"Erro na IA: {str(e)[:100]}",
            "recomendacao_final": f"Recomendamos a rua {ranking[0]['rua']} com score {ranking[0]['score']}/100."
        }


async def recomendar_melhor_rua_com_ia(
    nicho: str,
    lugares: List[Dict],
    cidade: str = ""
) -> Dict:
    """
    Função principal híbrida: estatística + IA para ajuste fino + insights
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
    
    # 5. 🔥 AJUSTE FINO COM IA para cada item do ranking
    ranking_ajustado = []
    for item in ranking:
        # Busca os concorrentes originais dessa rua
        concorrentes_da_rua = ruas_dict.get(item["rua"], [])
        
        # Aplica ajuste de IA
        ajuste = await ajustar_score_com_ia(
            nome_rua=item["rua"],
            score_atual=item["score"],
            concorrentes=concorrentes_da_rua,
            nicho=nicho
        )
        
        # Preserva o score original e adiciona informações do ajuste
        item["score_original"] = item["score"]
        item["score"] = ajuste["score_ajustado"]
        item["ajuste_ia"] = ajuste["justificativa"]
        item["concorrentes_reais_estimados"] = ajuste.get("concorrentes_reais_estimados", item["concorrentes"])
        item["usou_ia_no_ajuste"] = ajuste.get("usou_ia", False)
        
        # Atualiza emoji baseado no novo score
        if item["score"] >= 85:
            item["emoji"] = "🏆"
        elif item["score"] >= 70:
            item["emoji"] = "📌"
        elif item["score"] >= 50:
            item["emoji"] = "⚖️"
        else:
            item["emoji"] = "🚫"
        
        # Atualiza recomendação se houve ajuste significativo
        if ajuste["score_ajustado"] < item["score_original"] * 0.7:
            item["recomendacao"] = f"⚠️ AJUSTADO POR IA: {ajuste['justificativa']} Score ajustado de {item['score_original']} para {item['score']}/100."
        
        ranking_ajustado.append(item)
    
    # 6. Reordena pelo score ajustado
    ranking_ajustado.sort(key=lambda x: x["score"], reverse=True)
    
    melhor = ranking_ajustado[0] if ranking_ajustado else None
    
    # 7. Gera insight complementar com IA sobre o resultado final
    insight_ia = await obter_insight_ia(ranking_ajustado, nicho, cidade)
    
    # 8. Adiciona bairro ao melhor resultado
    if melhor and lugares:
        rua_nome = melhor["rua"]
        for lugar in lugares:
            if extrair_nome_rua(lugar.get("endereco", "")) == rua_nome:
                melhor["bairro_referencia"] = lugar.get("bairro", "Centro")
                break
    
    # 9. Conta quantos itens foram ajustados pela IA
    ajustados = sum(1 for r in ranking_ajustado if r.get("usou_ia_no_ajuste", False))
    
    return {
        "nicho": nicho,
        "cidade": cidade,
        "estrategia_aplicada": estrategia["tipo"],
        "descricao_estrategia": estrategia["descricao"],
        "total_estabelecimentos": len(lugares),
        "total_ruas_analisadas": len(ranking_ajustado),
        "total_ajustes_ia": ajustados,
        "melhor_rua": melhor,
        "ranking": ranking_ajustado[:10],
        "analise_ia": insight_ia,
        "usou_ia": IA_DISPONIVEL
    }
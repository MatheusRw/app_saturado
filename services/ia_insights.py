"""
Camada de IA complementar - Gemini
Adiciona insights qualitativos ao ranking estatístico do recomendacao.py
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
    recomendar_melhor_rua
)

# Configuração da IA
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        IA_DISPONIVEL = True
    else:
        IA_DISPONIVEL = False
        print("⚠️ GEMINI_API_KEY não configurada. IA desabilitada.")
except ImportError:
    IA_DISPONIVEL = False
    print("⚠️ google-generativeai não instalado. IA desabilitada.")


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
    Função principal híbrida: estatística (do recomendacao.py) + IA complementar
    """
    # 1. Usa a função estatística já existente
    resultado = await recomendar_melhor_rua(nicho=nicho, lugares=lugares)
    
    # 2. Adiciona flag para indicar que a IA foi usada
    resultado["usou_ia"] = False
    resultado["analise_ia"] = None
    
    # 3. Se tem ranking, tenta adicionar insight de IA
    if resultado.get("ranking") and len(resultado["ranking"]) > 0:
        insight_ia = await obter_insight_ia(
            ranking=resultado["ranking"],
            nicho=nicho,
            cidade=cidade
        )
        
        if insight_ia.get("sucesso"):
            resultado["usou_ia"] = True
            resultado["analise_ia"] = insight_ia
        else:
            resultado["analise_ia"] = insight_ia  # mesmo com erro, mostra a mensagem
    
    return resultado
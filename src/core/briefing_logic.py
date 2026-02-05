import json
from typing import Dict, Any
from deep_translator import GoogleTranslator

class BriefingBuilder:
    
    @staticmethod
    def _translate(text: str) -> str:
        if not text or len(text) < 2: return text
        try:
            return GoogleTranslator(source='auto', target='en').translate(text)
        except:
            return text

    @staticmethod
    def build(data: Dict[str, Any]):
        raw_text = data.get("raw_description", "")
        client = data.get("client", "Cliente")
        campaign = data.get("campaign", "Campanha")
        
        # O Agente A1 organiza o caos em estrutura
        
        # Cabeçalho do Documento
        header = f"# BRIEFING TÉCNICO: {client.upper()}\n"
        header += f"**Campanha:** {campaign}\n"
        header += f"**Data:** 26/01/2026\n"
        header += "---\n\n"

        # Simulação Inteligente (Mock do GPT-4)
        # Se tivéssemos a API real, enviaríamos o 'raw_text' para ela estruturar.
        # Como é mock, vamos simular que a IA extraiu os dados do texto cru.
        
        structured_body = f"""## 1. CONTEXTO & DESAFIO
O cliente busca uma solução para **{raw_text[:30]}...**. O cenário atual exige uma comunicação assertiva para destacar a marca frente à concorrência.

## 2. OBJETIVO DE NEGÓCIO
Aumentar a percepção de valor e converter leads qualificados. O foco não é apenas likes, mas resultados tangíveis.

## 3. PÚBLICO-ALVO (Target)
Definido preliminarmente como consumidores engajados com o setor de {client}, que valorizam qualidade e agilidade.

## 4. MENSAGEM CHAVE (Key Message)
"{client}: A solução que transforma o seu dia a dia."

## 5. FORMATOS SUGERIDOS
- Redes Sociais (Foco em Reels/Stories)
- Email Marketing (Nutrição)
- Mídia Paga (Performance)

## 6. MANDATÓRIOS
- Uso obrigatório da paleta de cores institucional.
- Tom de voz: Próximo, mas autoridade.
"""

        # Instrução do Sistema (Prompt Técnico Invisível)
        system_instruction = f"""
        ACT AS: Senior Account Manager (Agent A1).
        TASK: Structure the following raw request into a Formal Agency Brief.
        RAW INPUT: "{raw_text}"
        STRUCTURE: Context, Objective, Target, Key Message, Deliverables, Mandatories.
        TONE: Professional, Strategic, Clear.
        """
        
        return header + structured_body, system_instruction.strip()
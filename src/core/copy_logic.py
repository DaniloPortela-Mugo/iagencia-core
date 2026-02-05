import json
import datetime
from typing import Dict, Any
from deep_translator import GoogleTranslator

class CopyBuilder:
    
    @staticmethod
    def _translate(text: str) -> str:
        if not text or len(text) < 2: return text
        try:
            return GoogleTranslator(source='auto', target='en').translate(text)
        except:
            return text

    @staticmethod
    def build(data: Dict[str, Any]):
        format_type = data.get("format", "Post")
        
        # Roteamento de Agentes na Criação Inicial
        is_script = "Roteiro" in format_type or "TV" in format_type or "Rádio" in format_type
        
        if is_script:
            return CopyBuilder._run_agent_c3_roteirista(data)
        else:
            return CopyBuilder._run_agent_c1_redator(data)

    # --- AGENTE C3: ROTEIRISTA (Gera Tabelas) ---
    @staticmethod
    def _run_agent_c3_roteirista(data):
        fmt = data.get("format")
        topic = data.get("topic")
        duration = int(data.get("duration", 30))
        client = data.get("client")
        
        header = f"ROTEIRO: {fmt.upper()}\n"
        header += f"TÍTULO: {data.get('title', 'A Definir')}\n"
        header += f"TEMPO: {duration}\"\n"
        header += f"DATA: {datetime.date.today().strftime('%d/%m/%Y')}\n\n"

        if "Rádio" in fmt:
            script_body = f"""| TEMPO | LOCUÇÃO / EFEITOS (SFX) |
| :--- | :--- |
| 00-05" | (SFX: Som ambiente de {topic[:15]}... trilha sobe) |
| 05-20" | LOCUTOR: Você sabia que {topic}? A solução chegou. |
| 20-25" | LOCUTOR: Aproveite agora. (SFX: Carimbo sonoro da marca) |
| 25-{duration}" | LOCUTOR: {client}. Acesse o site e confira. |"""
        else: # TV
            script_body = f"""| TEMPO | VÍDEO (IMAGEM) | ÁUDIO (LOC/TRILHA) |
| :--- | :--- | :--- |
| 00-05" | Cena abre com imagem contextual de {topic[:15]}... Luz natural. | (Trilha: Começa suave e cresce) <br><br> LOC (OFF): As vezes, tudo muda. |
| 05-15" | Corta para Close-up do produto/ator. Sorriso confiante. | LOC: Mas a {client} entende você. <br> Conheça a novidade. |
| 15-{duration-5}" | Demo rápida do benefício principal: {topic[:20]}... | (SFX: Som de "Uau" ou transição mágica) <br><br> LOC: Simples assim. |
| {duration-5}-{duration}" | Cartela final com Logo e Site. Lettering: "Confira". | LOC: {client}. A sua escolha. <br> (Trilha encerra) |"""

        system_prompt = f"ROLE: TV Scriptwriter (Agent C3). TASK: Create a {duration}s script about '{topic}' formatted as a Markdown Table."
        return header + script_body, system_prompt

    # --- AGENTE C1: REDATOR (Gera Texto) ---
    @staticmethod
    def _run_agent_c1_redator(data):
        topic = data.get("topic")
        framework = data.get("framework", "Livre")
        client = data.get("client")
        
        title_block = f"# {data.get('title')}\n\n" if data.get('title') else ""
        
        if "AIDA" in framework:
            body = f"**ATENÇÃO**\n\nVocê já parou para pensar em {topic}? É hora de mudar isso.\n\n"
            body += f"**INTERESSE**\n\nNossa solução traz o que você precisa. Imagine resolver isso hoje.\n\n"
            body += f"**DESEJO**\n\nCom a {client}, você tem exclusividade e qualidade garantida.\n\n"
            body += f"**AÇÃO**\n\n👉 Clique no link e confira agora!"
        else:
            body = f"## A Revolução do {topic}\n\n"
            body += f"Estamos trazendo para o mercado algo único. A {client} inova mais uma vez.\n\n"
            body += f"Não perca a chance de conferir {topic} com condições especiais.\n\n"
            body += f"---\n\n#{client.replace(' ','')} #Novidade #Inovação"

        return title_block + body, f"ROLE: Copywriter (Agent C1). FRAMEWORK: {framework}."

    # --- SIMULAÇÃO DE CHAT COM AGENTES (C2, C4, C5) ---
    @staticmethod
    def chat_with_agent(current_text: str, user_message: str, active_agent: str):
        """Processa a conversa do usuário com o 'Co-piloto'."""
        
        msg = user_message.lower()
        response_data = {"agent": "Assistente", "message": ""}

        # Roteamento de Intenção
        if "ideia" in msg or "opções" in msg or "sugestão" in msg:
            response_data["agent"] = "C2 (Conceito)"
            response_data["message"] = (
                "Aqui estão 3 caminhos criativos para explorar:\n\n"
                "1. **Humor:** Focar em uma situação cotidiana engraçada.\n"
                "2. **Emocional:** Usar nostalgia para conectar com o público.\n"
                "3. **Impacto:** Começar com um dado estatístico surpreendente.\n\n"
                "Qual desses caminhos você prefere que eu desenvolva?"
            )
        
        elif "melhorar" in msg or "revisar" in msg or "curto" in msg or "ajustar" in msg:
            response_data["agent"] = "C4 (Editor)"
            response_data["message"] = (
                "Analisei o texto. Sugiro cortar advérbios excessivos na introdução para dar mais agilidade. "
                "Também podemos trocar termos técnicos por linguagem mais coloquial. Posso aplicar essas mudanças?"
            )
            
        elif "tv" in msg or "rádio" in msg or "cena" in msg:
            response_data["agent"] = "C3 (Roteirista)"
            response_data["message"] = (
                "Entendido. Para dar mais dinamismo a essa cena, sugiro incluir um corte rápido (Jump Cut) "
                "entre os segundos 05-10. Isso mantém a atenção visual."
            )
            
        else:
            response_data["agent"] = "Agente IA"
            response_data["message"] = f"Entendido. Vou processar seu pedido: '{user_message}'. Como gostaria de prosseguir?"

        return response_data
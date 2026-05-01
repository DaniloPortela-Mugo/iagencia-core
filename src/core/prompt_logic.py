import json
import random
from typing import Dict, Any
from deep_translator import GoogleTranslator

class PromptBuilder:
    
    # --- 1. MOCKUPS (REGRAS DE FORMATO) ---
    MOCKUP_SPECS = {
        'wobbler': { 'desc': 'Wobbler Redondo (PDV)', 'prompt_add': 'centered composition, circular framing, fit for round cut-out, isolated white background, product focus', 'ar': '--ar 1:1' },
        'stopper': { 'desc': 'Stopper Vertical', 'prompt_add': 'vertical composition, eye-level angle, high contrast visibility, promotional style', 'ar': '--ar 1:3' },
        'regua': { 'desc': 'Régua de Gôndola', 'prompt_add': 'wide horizontal panorama, seamless pattern potential, shelf strip design', 'ar': '--ar 5:1' },
        'display_balcao': { 'desc': 'Display Balcão (A4)', 'prompt_add': 'poster layout, clear focal point, vertical orientation, negative space for text', 'ar': '--ar 2:3' },
        'windbanner': { 'desc': 'Windbanner', 'prompt_add': 'tall vertical composition, bold colors, readable from distance', 'ar': '--ar 1:4' },
        'cartaz': { 'desc': 'Cartaz Oferta', 'prompt_add': 'bold graphic design, high impact, supermarket advertising style', 'ar': '--ar 3:4' }
    }

    # --- 2. BANCO DE DADOS CRIATIVO (HALLUCINATION ENGINE) ---
    CREATIVE_ASSETS = {
        'scenery': [
            "com iluminação natural suave entrando pela janela, decoração minimalista", 
            "com paredes de tijolo exposto, estilo industrial, móveis de madeira rústica",
            "em ambiente de luxo, acabamentos em mármore carrara e detalhes dourados",
            "durante a golden hour, com lens flare cinematográfico e partículas de poeira no ar",
            "em um dia nublado com luz difusa e suave, perfeito para retratos"
        ],
        'clothing': [
            "camiseta de algodão premium e jeans texturizado, look casual urbano", 
            "jaqueta de couro vintage e óculos escuros, estilo rebelde",
            "vestido leve com estampa floral, tecido fluido, visual de verão",
            "terno de corte italiano bem ajustado, camisa branca impecável"
        ],
        'physique': [
            "rosto angular com barba por fazer, olhos castanhos expressivos", 
            "traços marcantes, olhar confiante, postura relaxada",
            "rosto delicado com sardas sutis, pele iluminada natural",
            "expressão serena, sorriso carismático, aparência saudável"
        ],
        'hair': [
            "volumoso e texturizado com brilho natural", 
            "corte assimétrico moderno e despojado", 
            "liso e sedoso, caindo sobre os ombros", 
            "cacheado com definição perfeita e volume controlado"
        ]
    }

    @staticmethod
    def _translate_to_en(text: str) -> str:
        if not text or len(text) < 2: return ""
        try:
            return GoogleTranslator(source='auto', target='en').translate(text)
        except:
            return text 

    @staticmethod
    def _enrich_text_pt(text: str, category: str) -> str:
        """
        IA CRIATIVA: Se o texto for muito curto (< 15 chars), adiciona detalhes criativos em PT.
        """
        if not text: return ""
        # Se o usuário escreveu pouco, a IA ajuda.
        if len(text) < 20:
            options = PromptBuilder.CREATIVE_ASSETS.get(category, [])
            if options:
                detail = random.choice(options)
                return f"{text}, {detail}"
        return text

    @staticmethod
    def _check_missing(value: str, label: str) -> str:
        if not value or len(value.strip()) == 0: return f"[DEFINIR {label.upper()}]"
        return value

    # --- 3. CONSTRUTOR PRINCIPAL ---

    @staticmethod
    def build(data: Dict[str, Any]):
        media_type = data.get("media_type", "Imagem")
        visual_style = data.get("style", "Fotorrealista (Padrão)")
        mockup_id = data.get("mockup_id")
        mockup_data = PromptBuilder.MOCKUP_SPECS.get(mockup_id)
        
        # ----------------------------------------------------
        # ETAPA A: ENRIQUECIMENTO (EM PORTUGUÊS)
        # ----------------------------------------------------
        
        # Ideia (Mantém original) e Cenário (Expande se necessário)
        idea_pt = data.get('general_idea', '')
        scene_pt_raw = data.get('scene_details', '')
        # Se não tiver cenário, infere um básico ou enriquece o que tem
        scene_pt_rich = PromptBuilder._enrich_text_pt(scene_pt_raw if scene_pt_raw else "Ambiente", 'scenery')
        
        # Casting (Itera e enriquece cada campo)
        chars_processed = []
        has_characters = False # Flag para o Skin Shader
        
        for i, char in enumerate(data.get("characters", [])):
            if not any(char.values()): continue
            has_characters = True
            
            # Enriquece em PT se estiver curto
            phy_pt = PromptBuilder._enrich_text_pt(char.get('physical_description', ''), 'physique')
            cloth_pt = PromptBuilder._enrich_text_pt(char.get('clothing', ''), 'clothing')
            hair_pt = PromptBuilder._enrich_text_pt(char.get('hair', ''), 'hair')
            
            chars_processed.append({
                "pt": {
                    "name": char.get('name') or f"Personagem {i+1}",
                    "gender": char.get('gender', ''),
                    "age": char.get('age', ''),
                    "physique": phy_pt,
                    "emotion": char.get('emotion', ''),
                    "clothing": cloth_pt,
                    "accessories": char.get('accessories', ''),
                    "hair": hair_pt,
                    "dialogue": char.get('dialogue', ''),
                    "voice_type": char.get('voice_type', 'on_screen'),
                    "voice_gender": char.get('voice_gender', '')
                },
                "en": { # Tradução para Prompt Técnico
                    "gender": PromptBuilder._translate_to_en(char.get('gender', '')),
                    "physique": PromptBuilder._translate_to_en(phy_pt),
                    "emotion": PromptBuilder._translate_to_en(char.get('emotion', '')),
                    "clothing": PromptBuilder._translate_to_en(cloth_pt),
                    "accessories": PromptBuilder._translate_to_en(char.get('accessories', '')),
                    "hair": PromptBuilder._translate_to_en(hair_pt)
                }
            })

        # ----------------------------------------------------
        # ETAPA B: ROTEIRO HUMANO (PT-BR) - PARA EXIBIÇÃO
        # Estruturado para facilitar leitura e Copy/Paste
        # ----------------------------------------------------
        human_text = f"ROTEIRO DE CRIAÇÃO - {visual_style.upper()}\n"
        if mockup_data: human_text += f"FORMATO PDV: {mockup_data['desc'].upper()}\n"
        human_text += "\n"
        
        human_text += "=== 1. CONCEITO & CENÁRIO ===\n"
        human_text += f"Ação: {PromptBuilder._check_missing(idea_pt, 'Ideia Geral')}\n"
        human_text += f"Cenário: {PromptBuilder._check_missing(scene_pt_rich, 'Cenário')}\n"
        if data.get("image_data"): human_text += f"Ref. Visual: [Imagem Anexada] ({data.get('image_usage')})\n"
        human_text += "\n"

        human_text += "=== 2. CASTING ===\n"
        if not chars_processed: human_text += "(Sem personagens humanos)\n"
        
        for item in chars_processed:
            c = item['pt']
            human_text += f"• {c['name']} ({c['gender']}, {c['age']})\n"
            if c['physique']: human_text += f"  Físico: {c['physique']}\n"
            if c['hair']: human_text += f"  Cabelo: {c['hair']}\n"
            if c['clothing']: human_text += f"  Visual: {c['clothing']}\n"
            if c['accessories']: human_text += f"  Acessórios: {c['accessories']}\n"
            if c['emotion']: human_text += f"  Expressão: {c['emotion']}\n"
            
            if media_type == 'Vídeo' and c['dialogue']:
                loc = "EM CENA" if c['voice_type'] == 'on_screen' else "LOCUÇÃO OFF"
                human_text += f"  Áudio ({loc}): \"{c['dialogue']}\"\n"
            human_text += "\n"

        human_text += "=== 3. TÉCNICA ===\n"
        techs = []
        if data.get('format') and not mockup_data: techs.append(f"Formato: {data.get('format')}")
        if data.get('lighting'): techs.append(f"Luz: {data.get('lighting')}")
        if data.get('camera'): techs.append(f"Câmera: {data.get('camera')}")
        if data.get('pov_angle'): techs.append(f"Ângulo: {data.get('pov_angle')}")
        human_text += " | ".join(techs) + "\n"
        
        if media_type == 'Vídeo':
            if data.get('camera_movement'): human_text += f"Movimento: {data.get('camera_movement')}\n"
            if data.get('sound_design'): human_text += f"Som: {data.get('sound_design')}\n"

        # ----------------------------------------------------
        # ETAPA C: PROMPT TÉCNICO (EN) - "A CAIXA PRETA"
        # ----------------------------------------------------
        
        idea_en = PromptBuilder._translate_to_en(idea_pt)
        scene_en = PromptBuilder._translate_to_en(scene_pt_rich)
        prompt_en_output = ""

        # --- MODO VÍDEO (JSON ESTRUTURADO) ---
        if media_type == "Vídeo":
            veo_chars = []
            for item in chars_processed:
                c_en = item['en']
                c_pt = item['pt']
                full_desc = f"{c_en['physique']}, {c_en['hair']}, {c_en['emotion']}, wearing {c_en['clothing']}"
                if c_en['accessories']: full_desc += f", {c_en['accessories']}"
                
                # Skin Shader Light para Vídeo
                if "Fotorrealista" in visual_style: full_desc += ", realistic skin texture"
                
                dlg = c_pt['dialogue']
                if c_pt['voice_type'] == 'off': dlg = f"[VOICEOVER]: {dlg}"
                
                veo_chars.append({ "name": c_en['gender'], "description": full_desc, "dialogue": dlg })

            veo_json = {
                "style": "cinematic, photorealistic, 8k" if "Fotorrealista" in visual_style else visual_style,
                "prompt": f"{idea_en}. {scene_en}",
                "technical": {
                    "camera": f"{data.get('camera', '')}, {data.get('format', '')}",
                    "movement": data.get('camera_movement', 'static'),
                    "lighting": data.get('lighting', '')
                },
                "characters": veo_chars,
                "audio": PromptBuilder._translate_to_en(data.get("sound_design", ""))
            }
            prompt_en_output = json.dumps(veo_json, indent=2, ensure_ascii=False)

        # --- MODO IMAGEM (MIDJOURNEY) ---
        else:
            main_prompt = idea_en
            if "Fotorrealista" not in visual_style:
                 style_en = PromptBuilder._translate_to_en(visual_style)
                 main_prompt = f"{style_en} of {idea_en}"

            # Personagens
            chars_prompt = []
            for item in chars_processed:
                c_en = item['en']
                char_str = f"{c_en['gender']} {c_en['age']}, {c_en['physique']}, {c_en['hair']}, {c_en['emotion']} expression, wearing {c_en['clothing']}"
                if c_en['accessories']: char_str += f", {c_en['accessories']}"
                chars_prompt.append(char_str)
            
            # Stack Técnico
            tech_stack = [
                scene_en,
                f"Lighting: {data.get('lighting')}" if data.get('lighting') else None,
                f"Camera: {data.get('camera')}" if data.get('camera') else None,
                f"Angle: {data.get('pov_angle')}" if data.get('pov_angle') else None,
                f"Palette: {data.get('colors')}" if data.get('colors') else None,
            ]
            if mockup_data: tech_stack.append(f"Composition: {mockup_data['prompt_add']}")

            # Montagem
            parts = [main_prompt] + chars_prompt + list(filter(None, tech_stack))
            base_prompt = "/imagine prompt: " + ", ".join(parts)
            
            # === SKIN SHADER ENGINE (TRAVA DE REALISMO) ===
            # Só ativa se tiver humanos na cena
            if has_characters and "Fotorrealista" in visual_style:
                realism_pack = "detailed skin texture, visible pores, matte skin, natural imperfections, no retouch, shot on 35mm, hyperrealistic photography"
                anti_artificial_pack = "--no wax skin, smoothing, airbrushed, plastic, CGI, doll, blur, cartoon"
                base_prompt += f", {realism_pack} {anti_artificial_pack}"
            elif "Fotorrealista" in visual_style:
                # Se for só paisagem/produto
                base_prompt += ", photorealistic, 8k, highly detailed --no blur, illustration"

            # Suporte a Imagem
            if data.get("image_data"):
                usage = data.get("image_usage", "style_ref")
                param = "--sref" if usage == "style_ref" else "--cref" if usage == "char_ref" else "--iw 2.0"
                base_prompt += f" {param} [IMAGE_URL]"

            base_prompt += " --v 6.0 --style raw"
            
            # AR (Mockup > Seleção > Padrão)
            if mockup_data:
                base_prompt += f" {mockup_data['ar']}"
            elif data.get('format'):
                try:
                    ar = data.get('format').split(' ')[0]
                    if ':' in ar: base_prompt += f" --ar {ar}"
                except: pass
            
            prompt_en_output = base_prompt

        return human_text, prompt_en_output
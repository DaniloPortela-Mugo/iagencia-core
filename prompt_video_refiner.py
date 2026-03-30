import json
from typing import Dict, Any, Optional

def refine_video_prompt(data: Dict[str, Any]) -> str:
    """
    Constrói o prompt final para motores de vídeo (Kling/Veo).
    Lógica: Prioriza imagem de referência e injeta parâmetros de movimento e áudio.
    """
    # Extração de dados da UI
    idea = data.get("idea", "").strip()
    config = data.get("config", {})
    characters = data.get("characters", [])
    engine = data.get("engine", "kling")
    has_ref = data.get("has_reference", False) or data.get("ref_image") is not None
    
    # Dados de áudio (Exclusivos para VEO)
    audio_mode = data.get("audio_mode", "tts")
    tts_text = data.get("tts_text", "")
    tts_voice = data.get("tts_voice", "Feminina")
    tts_tone = data.get("tts_tone", "Natural")

    # 1. DEFINIÇÃO DO SUJEITO (O "QUEM")
    # Se tem imagem, o sujeito é a própria imagem. Se não, descrevemos o casting.
    if has_ref:
        subject_part = "Animate the provided reference image @img1."
    else:
        char_descriptions = []
        for char in characters:
            desc = f"{char.get('name', 'Person')} ({char.get('gender', '')}, {char.get('age', '')}, wearing {char.get('clothing', 'casual clothes')})"
            char_descriptions.append(desc)
        subject_part = ". ".join(char_descriptions) if char_descriptions else "Cinematic scene."

    # 2. DEFINIÇÃO DA AÇÃO E MOVIMENTO (O "COMO")
    # Aqui entra o Roteiro (da Redação ou Manual) + Configurações de Câmera
    action_part = f"Action: {idea}."
    camera_part = f"Camera Movement: {config.get('camera', 'Static')}. Pacing: {config.get('pacing', 'Normal')}."
    style_part = f"Style: {config.get('style', 'Cinematográfico')}."

    # 3. CAMADA DE ÁUDIO (EXCLUSIVA VEO)
    sound_part = ""
    if engine == "veo":
        if audio_mode == "tts" and tts_text:
            sound_part = f"Audio: Synchronized AI Voice ({tts_voice}), Tone: {tts_tone}. Script: '{tts_text}'."
        elif audio_mode == "upload":
            sound_part = "Audio: Lip-sync and match rhythm with uploaded audio file."
        else:
            sound_part = "Audio: Natural ambient sound matching the scene."

    # 4. MONTAGEM FINAL DO PROMPT LINEAR
    full_prompt = f"{subject_part} {action_part} {camera_part} {style_part} {sound_part}".strip()

    # 5. AJUSTE DE TAGS POR MOTOR
    # O Kling usa uma tag específica para imagem de referência
    if engine == "kling" and has_ref:
        full_prompt = full_prompt.replace("@img1", "<<<image_1>>>")

    return full_prompt
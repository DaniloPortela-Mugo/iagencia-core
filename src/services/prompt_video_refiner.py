import json
from src.services.planning_agent import get_client  # Usa sua chave já configurada


VEO_VISUAL_RULES = {
    "prohibited_elements": [
        "text",
        "labels",
        "subtitles",
        "closed captions",
        "text overlays",
        "any language written on the screen",
        "brand logos",
        "watermarks",
        "words: winter, summer, autumn, spring",
    ]
}
VEO_AUDIO_LANGUAGE = "Brazilian Portuguese"
VEO_CAPTIONS_REQUIREMENT = "no captions"

VIDEO_SKIN_PROTOCOL = (
    "detailed skin texture, visible pores, natural imperfections, no makeup look, shot on 35mm"
)
VIDEO_ANTI_PLASTIC = (
    "wax skin, plastic skin, airbrushed skin, smooth skin, cartoonish, cgi face, doll like, blur, flat lighting"
)

CLEAN_SHAVEN_TOKENS = [
    "sem barba",
    "rosto liso",
    "clean-shaven",
    "clean shaven",
    "zero facial hair",
    "no beard",
    "beardless",
]

CLEAN_SHAVEN_RULE = (
    "MANDATORY CHARACTER RULE: The male subject must be fully clean-shaven. "
    "No beard, no mustache, no stubble, no goatee, no five-o-clock shadow, no peach fuzz. "
    "The face must show only smooth bare skin — zero facial hair of any kind. "
    "This rule overrides any conflicting style or realism instruction."
)

CLEAN_SHAVEN_PROHIBITIONS = (
    "beard, mustache, stubble, goatee, five o'clock shadow, facial hair, "
    "sideburns, peach fuzz, fine facial hair"
)


def _detect_clean_shaven(text: str) -> bool:
    """Retorna True se o texto solicitar rosto liso / sem barba."""
    lower = text.lower()
    return any(token in lower for token in CLEAN_SHAVEN_TOKENS)
IDENTITY_LOCK_REFERENCE = (
    "IDENTITY LOCK (REFERENCE IMAGE): Use the reference image as the only identity source. "
    "Preserve the same person: facial structure, eye shape, nose, lips, skin tone, hairstyle, hairline, eyebrows, and overall likeness. "
    "Do not change age, gender presentation, ethnicity, or distinctive features. "
    "Keep identity consistent across outputs."
)
IDENTITY_LOCK_NEGATIVE = (
    "DO NOT: change face, swap identity, alter facial proportions, beautify, de-age, change skin tone, "
    "change eye color, change hairstyle, add/remove facial hair, stylize into cartoon/anime."
)

REQUIRED_VEO_CONFIG_FIELDS = [
    "location",
    "time_of_day",
    "tone",
    "color_grade",
]

def _safe_get_bool(value, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "sim"):
            return True
        if v in ("false", "0", "no", "nao", "não"):
            return False
    return fallback


def _build_scene_safety_rules(scene_safety: dict) -> dict:
    """
    Normaliza regras de safety (whitelist + proibições) para o VEO JSON.
    """
    ss = scene_safety or {}

    allowed_people_count = ss.get("allowed_people_count", 1)
    try:
        allowed_people_count = int(allowed_people_count)
    except Exception:
        allowed_people_count = 1

    allowed_people_description = _safe_get_str(
        ss.get("allowed_people_description"),
        "Only the main character, no additional people.",
    )
    allowed_props = _safe_get_str(ss.get("allowed_props"), "").strip()

    forbid_extra_people = _safe_get_bool(ss.get("forbid_extra_people"), True)
    forbid_animals = _safe_get_bool(ss.get("forbid_animals"), True)
    forbid_vehicles = _safe_get_bool(ss.get("forbid_vehicles"), True)

    must_not_introduce = []
    if forbid_extra_people:
        must_not_introduce.append("any additional people, background crowds, or passersby")
    if forbid_animals:
        must_not_introduce.append("animals of any kind")
    if forbid_vehicles:
        must_not_introduce.append("vehicles (cars, bikes, buses, etc.)")

    return {
        "allowed_people_count": allowed_people_count,
        "allowed_people_description": allowed_people_description,
        "allowed_props": allowed_props,
        "must_not_introduce": must_not_introduce,
    }


def _validate_scene_safety(parsed: dict, safety: dict) -> str | None:
    """
    Validação simples e objetiva para evitar surpresas.
    - Se o modelo mencionou crowd/people extras no texto, falha.
    - Se o número de pessoas permitido é 1, proíbe "crowd", "people", "passersby", etc.
    (Heurística: não é perfeita, mas pega 80% dos problemas.)
    """
    allowed_people_count = safety.get("allowed_people_count", 1)
    desc = _safe_get_str(parsed.get("description", ""), "").lower()
    action = _safe_get_str(parsed.get("action", ""), "").lower()
    env = _safe_get_str(parsed.get("scene", {}).get("environment", ""), "").lower()

    text_blob = f"{desc}\n{action}\n{env}"

    if allowed_people_count <= 1:
        banned_hints = [
            "crowd",
            "many people",
            "people walking",
            "passersby",
            "pedestrians",
            "extras",
            "background people",
            "busy street",
        ]
        if any(h in text_blob for h in banned_hints):
            return "Scene safety violation: mentions extra people/crowd while allowed_people_count=1."

    # Se props foram especificados, tenta impedir props aleatórios comuns
    allowed_props = _safe_get_str(safety.get("allowed_props", ""), "")
    if allowed_props:
        # Não tenta “contar” props, só reforça que não deve inventar.
        pass

    return None

def _repair_veo_json(client, bad_json: dict, violation: str, scene_safety: dict) -> dict:
    system_prompt = f"""
You are a JSON repair assistant for Google VEO prompts.
Fix the JSON to satisfy the Scene Safety Layer, without adding any new elements.

Violation:
{violation}

Scene Safety Layer:
- Allowed people count: {scene_safety["allowed_people_count"]}
- Allowed people description: "{scene_safety["allowed_people_description"]}"
- Allowed props ONLY: "{scene_safety["allowed_props"]}"
- Must NOT introduce: {json.dumps(scene_safety["must_not_introduce"], ensure_ascii=False)}

Rules:
- Output valid JSON only.
- Remove forbidden elements from description/action/environment.
- Do not invent new location/time/tone/color_grade/lighting/environment.
"""

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(bad_json, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    repaired = completion.choices[0].message.content.strip()
    return json.loads(repaired)


def _safe_get_str(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value.strip() or fallback
    return str(value).strip() or fallback


def _map_aspect_ratio(format_label: str) -> str:
    label = (format_label or "").lower()
    if "9:16" in label or "vertical" in label:
        return "9:16"
    if "1:1" in label or "quadrado" in label:
        return "1:1"
    if "4:5" in label:
        return "4:5"
    if "21:9" in label:
        return "21:9"
    return "16:9"


def _build_consistency_block(has_ref: bool) -> str:
    if has_ref:
        return (
            "Animate the provided image @img1. "
            f"{IDENTITY_LOCK_REFERENCE} "
            f"{IDENTITY_LOCK_NEGATIVE} "
            f"Quality protocol: {VIDEO_SKIN_PROTOCOL}. "
            f"Avoid: {VIDEO_ANTI_PLASTIC}. "
            "Single continuous shot, stable framing, consistent lighting."
        )
    return (
        "Character identity lock: keep the exact same person across the entire clip. "
        "No face swap, no age shift, no hairstyle change, no wardrobe change unless explicitly specified. "
        "Maintain the same facial geometry: jawline, nose bridge, eye spacing, eyebrow shape. "
        f"Quality protocol: {VIDEO_SKIN_PROTOCOL}. "
        f"Avoid: {VIDEO_ANTI_PLASTIC}. "
        "Single continuous shot, minimal cuts, stable medium close-up or medium shot. "
        "Consistent lighting and color temperature throughout."
    )


def _validate_veo_config(config: dict) -> str | None:
    """
    Retorna mensagem de erro se faltar algo obrigatório no VEO; senão None.
    """
    missing = []
    for key in REQUIRED_VEO_CONFIG_FIELDS:
        val = config.get(key)
        if val is None or (isinstance(val, str) and not val.strip()):
            missing.append(key)
    if missing:
        return (
            "Error: Missing required VEO parameters: "
            + ", ".join(missing)
            + ". Please define them in VideoStudio before generating."
)
    return None


async def refine_and_translate_video(data: dict):
    """
    Recebe roteiro em PT (script_pt) e parâmetros técnicos.
    - Kling: retorna STRING em inglês (prompt linear)
    - VEO: retorna JSON em inglês (string JSON) com regras fixas + campos controlados
    """
    tenant_slug = _safe_get_str(data.get("tenant_slug", ""), "")
    client = get_client(tenant_slug) if tenant_slug else get_client()

    script_pt = _safe_get_str(data.get("script_pt", ""), "")
    engine = _safe_get_str(data.get("engine", "kling"), "kling").lower()
    config = data.get("config", {}) or {}
    has_ref = bool(data.get("has_ref", False))

    # extras (opcionais)
    tts_text = _safe_get_str(data.get("tts_text", ""), "")
    negative_prompt = _safe_get_str(data.get("negative_prompt", ""), "")

    if not script_pt:
        # Para VEO, permitimos continuar com roteiro mínimo baseado nos campos técnicos.
        if engine == "veo":
            script_pt = (
                "Gerar um vídeo comercial curto com o personagem principal em destaque. "
                "Siga estritamente as configurações técnicas do VEO e não invente elementos."
            )
        else:
            return "Error: script_pt is empty"

    # técnicos (com fallbacks)
    style = _safe_get_str(config.get("style"), "cinematic commercial")
    lighting = _safe_get_str(config.get("lighting"), "")
    camera = _safe_get_str(config.get("camera"), "smooth gimbal")
    pacing = _safe_get_str(config.get("pacing"), "normal")
    movement = _safe_get_str(config.get("movement"), "Static")
    format_label = _safe_get_str(config.get("format"), "Horizontal (16:9)")
    aspect_ratio = _map_aspect_ratio(format_label)

    # VEO específicos (sem surpresas: exigimos preenchimento)
    location = _safe_get_str(config.get("location"), "")
    time_of_day = _safe_get_str(config.get("time_of_day"), "")
    tone = _safe_get_str(config.get("tone"), "")
    color_grade = _safe_get_str(config.get("color_grade"), "")
    environment = _safe_get_str(config.get("environment"), "")
    scene_safety = _build_scene_safety_rules(config.get("scene_safety", {}))

    consistency_block = _build_consistency_block(has_ref)

    # Detecta rosto liso no roteiro completo (PT ou EN)
    clean_shaven = _detect_clean_shaven(script_pt)
    clean_shaven_system_note = (
        f"\nCHARACTER FACE RULE (MANDATORY): {CLEAN_SHAVEN_RULE}"
        f"\nPROHIBITED on the face: {CLEAN_SHAVEN_PROHIBITIONS}."
    ) if clean_shaven else ""

    # =========================
    # VEO: saída em JSON
    # =========================
    if engine == "veo":
        err = _validate_veo_config(config)
        if err:
            return err

        # Regra: dialogue.line fica em PT-BR. Se tiver tts_text, ele vira a fala.
        dialogue_line_pt = tts_text.strip() if tts_text.strip() else script_pt.strip()

        # Se usuário enviou JSON PT editado, traduzimos para EN antes de enviar ao VEO
        veo_prompt_pt_json = _safe_get_str(data.get("veo_prompt_pt_json", ""), "")
        if veo_prompt_pt_json:
            try:
                pt_json = json.loads(veo_prompt_pt_json)
            except Exception:
                return "Error: Invalid VEO JSON (PT)."

            translate_system = f"""
You are a translation engine. Translate the JSON values from Portuguese to English.
Keep the JSON structure and keys exactly the same.
Do NOT translate dialogue.line. Keep dialogue.language as "{VEO_AUDIO_LANGUAGE}".
Captions must be disabled: dialogue.subtitles must be false ({VEO_CAPTIONS_REQUIREMENT}).
visual_rules.prohibited_elements MUST match EXACTLY this list:
{json.dumps(VEO_VISUAL_RULES["prohibited_elements"], ensure_ascii=False)}
Return ONLY valid JSON.
"""
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": translate_system},
                        {"role": "user", "content": json.dumps(pt_json, ensure_ascii=False)},
                    ],
                    temperature=0.2,
                )
                translated = completion.choices[0].message.content.strip()
                parsed = json.loads(translated)
                parsed.setdefault("dialogue", {})
                parsed["dialogue"]["language"] = VEO_AUDIO_LANGUAGE
                parsed["dialogue"]["subtitles"] = False
                parsed["visual_rules"] = VEO_VISUAL_RULES
                return json.dumps(parsed, ensure_ascii=False)
            except Exception as e:
                return f"Error in VEO JSON translation: {str(e)}"

        # Se só quer preview PT, gera JSON em PT para edição
        if _safe_get_bool(data.get("veo_preview_pt", False)):
            system_prompt_pt = f"""
Você é um engenheiro de prompt para Google VEO.

REQUISITOS:
- Saída DEVE ser JSON válido (sem markdown, sem comentários).
- Todos os campos devem estar em português.
- dialogue.line deve estar em pt-BR.
- dialogue.subtitles deve ser false.
- dialogue.language deve ser "{VEO_AUDIO_LANGUAGE}" (áudio em português brasileiro).
- Legendas: {VEO_CAPTIONS_REQUIREMENT}.
- visual_rules.prohibited_elements deve ser exatamente esta lista:
{json.dumps(VEO_VISUAL_RULES["prohibited_elements"], ensure_ascii=False)}

VALORES FIXOS (não inventar):
- location: "{location}"
- time_of_day: "{time_of_day}"
- environment: "{environment}"
- tone: "{tone}"
- color_grade: "{color_grade}"
- lighting: "{lighting}"
- camera: "{camera}"
- movement: "{movement}"
- pacing: "{pacing}"
- aspect_ratio: "{aspect_ratio}"
- style: "{style}"

SEGURANÇA:
- Não introduza elementos novos.
- Pessoas permitidas: {scene_safety["allowed_people_count"]} ({scene_safety["allowed_people_description"]})
- Props permitidos: "{scene_safety["allowed_props"]}"
- NÃO introduzir: {json.dumps(scene_safety["must_not_introduce"], ensure_ascii=False)}

INSIRA no início de "description":
"{consistency_block}"
"""
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": system_prompt_pt}, {"role": "user", "content": dialogue_line_pt}],
                    temperature=0.2,
                )
                raw = completion.choices[0].message.content.strip()
                parsed = json.loads(raw)
                parsed.setdefault("dialogue", {})
                parsed["dialogue"]["language"] = VEO_AUDIO_LANGUAGE
                parsed["dialogue"]["subtitles"] = False
                parsed["visual_rules"] = VEO_VISUAL_RULES
                return json.dumps(parsed, ensure_ascii=False)
            except Exception as e:
                return f"Error in VEO JSON PT generation: {str(e)}"

        system_prompt = f"""
You are a senior Video Prompt Engineer for Google VEO.

OUTPUT REQUIREMENTS:
- Output MUST be valid JSON only (no markdown, no comments, no trailing commas).
- All fields except dialogue.line must be in English.
- dialogue.line MUST be in Brazilian Portuguese (do NOT translate).
- dialogue.subtitles MUST be false
- dialogue.language MUST be "{VEO_AUDIO_LANGUAGE}" (audio language).
- Captions requirement: {VEO_CAPTIONS_REQUIREMENT}.
- visual_rules.prohibited_elements MUST match EXACTLY this list:
{json.dumps(VEO_VISUAL_RULES["prohibited_elements"], ensure_ascii=False)}

NO-SURPRISES POLICY:
- You MUST NOT invent location/time_of_day/tone/color_grade/lighting/environment.
- Use EXACT values provided below.

EXACT USER-SPECIFIED VALUES:
- location: "{location}"
- time_of_day: "{time_of_day}"
- environment: "{environment}"
- tone: "{tone}"
- color_grade: "{color_grade}"
- lighting: "{lighting}"
- camera: "{camera}"
- movement: "{movement}"
- pacing: "{pacing}"
- aspect_ratio: "{aspect_ratio}"
- style: "{style}"

SCENE SAFETY LAYER (NO SURPRISES):
- Do NOT introduce any element not explicitly allowed.
- Allowed people count: {scene_safety["allowed_people_count"]}
- Allowed people description: "{scene_safety["allowed_people_description"]}"
- Allowed props (ONLY these, if any): "{scene_safety["allowed_props"]}"
- Must NOT introduce: {json.dumps(scene_safety["must_not_introduce"], ensure_ascii=False)}

If something is not specified, keep it minimal and neutral (do not add new objects, new people, or new plot elements).
{clean_shaven_system_note}


CONSISTENCY (ONE SCENE PER GENERATION):
- Put this block at the START of "description" verbatim:
"{consistency_block}"

DIALOGUE (keep in PT-BR):
"{dialogue_line_pt}"

JSON SCHEMA (must follow):
{{
  "description": "...",
  "scene": {{
    "location": "{location}",
    "time_of_day": "{time_of_day}",
    "environment": "{environment}"
  }},
  "visual_style": {{
    "camera": "...",
    "color_grade": "{color_grade}",
    "lighting": "{lighting}",
    "tone": "{tone}"
  }},
  "action": "...",
  "settings": {{
    "duration": 8,
    "aspect_ratio": "{aspect_ratio}",
    "mouth_shape_intensity": 0.85,
    "eye_contact_ratio": 0.9
  }},
  "dialogue": {{
    "character": "Narrator",
    "line": "{dialogue_line_pt}",
    "subtitles": false,
    "language": "Brazilian Portuguese"
  }},
  "visual_rules": {{
    "prohibited_elements": [...]
  }},

  "scene_safety": {
  "allowed_people_count": 1,
  "allowed_people_description": "...",
  "allowed_props": "...",
  "must_not_introduce": [...]
}
}}

IMPORTANT:
- "visual_style.camera" must explicitly mention camera + movement + pacing and stable framing.
- Keep a premium luxury commercial aesthetic.
"""

        try:
            completion = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": system_prompt}],
                temperature=0.3,
            )

            raw = completion.choices[0].message.content.strip()
            parsed = json.loads(raw)  # valida JSON

            # Enforce hard rules (garantia)
            parsed["visual_rules"] = VEO_VISUAL_RULES

            parsed.setdefault("dialogue", {})
            parsed["dialogue"]["subtitles"] = False
            parsed["dialogue"]["language"] = VEO_AUDIO_LANGUAGE
            parsed["dialogue"]["line"] = dialogue_line_pt

            parsed.setdefault("scene", {})
            parsed["scene"]["location"] = location
            parsed["scene"]["time_of_day"] = time_of_day
            parsed["scene"]["environment"] = environment

            parsed.setdefault("visual_style", {})
            parsed["visual_style"]["color_grade"] = color_grade
            parsed["visual_style"]["lighting"] = lighting
            parsed["visual_style"]["tone"] = tone

            merged_camera = (
                f"{camera}; movement: {movement}; pacing: {pacing}; "
                "stable framing; avoid extreme angles; keep face sharp"
            )
            parsed["visual_style"]["camera"] = merged_camera

            parsed.setdefault("settings", {})
            parsed["settings"]["aspect_ratio"] = aspect_ratio

            parsed["scene_safety"] = scene_safety
            violation = _validate_scene_safety(parsed, scene_safety)

            if violation:
                try:
                    parsed = _repair_veo_json(client, parsed, violation, scene_safety)
                    parsed["scene_safety"] = scene_safety
                except Exception:
                    return f"Error: {violation}"

            # Description: garantir consistência e evitar inventar texto na tela
            desc = _safe_get_str(parsed.get("description", ""), "")
            if not desc:
                desc = "Premium luxury commercial scene."
            if not desc.lower().startswith(consistency_block.split(".")[0].lower()):
                parsed["description"] = f"{consistency_block} {desc}".strip()

            # Reforça clean-shaven diretamente no campo description do JSON
            if clean_shaven:
                parsed["description"] = (
                    f"{CLEAN_SHAVEN_RULE} "
                    f"{parsed.get('description', '')} "
                    f"ABSOLUTE PROHIBITIONS on face: {CLEAN_SHAVEN_PROHIBITIONS}."
                ).strip()
                # Adiciona também nos prohibited_elements do VEO
                extra_prohibitions = [
                    "beard", "mustache", "stubble", "goatee",
                    "five o'clock shadow", "facial hair", "peach fuzz",
                ]
                existing = parsed.get("visual_rules", {}).get("prohibited_elements", [])
                parsed.setdefault("visual_rules", {})["prohibited_elements"] = list(
                    dict.fromkeys(existing + extra_prohibitions)
                )

            # negative_prompt como constraints internas (não é texto na tela)
            if negative_prompt:
                parsed["description"] = (
                    f"{parsed['description']} Negative constraints: {negative_prompt}."
                ).strip()

            return json.dumps(parsed, ensure_ascii=False)

        except Exception as e:
            return f"Error in VEO JSON generation: {str(e)}"
        
        

    # =========================
    # KLING (default): saída em string
    # =========================
    system_prompt = f"""
You are a Video Prompt Engineer (Engine: {engine}).
Transform a Portuguese script into a SINGLE technical English prompt for one scene.

CONSISTENCY (ONE SCENE PER GENERATION):
- Apply this block verbatim (high priority):
"{consistency_block}"

TECH RULES:
1) If has_ref is true, the prompt MUST start with: "Animate the provided image @img1."
2) Add style and luxury commercial tone: {style}
3) Add lighting: {lighting}
4) Add camera + movement + pacing explicitly:
   camera={camera}, movement={movement}, pacing={pacing}
5) If engine is Kling, replace "@img1" with "<<<image_1>>>"
6) Single continuous shot, stable framing, consistent lighting.
{clean_shaven_system_note}

PORTUGUESE SCRIPT:
{script_pt}

OUTPUT:
Return only the final English prompt, no comments.
"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7,
        )
        final_prompt = completion.choices[0].message.content.strip()

        if engine == "kling":
            final_prompt = final_prompt.replace("@img1", "<<<image_1>>>")

        # Reforça clean-shaven no prompt final (dupla camada de garantia)
        if clean_shaven:
            final_prompt = (
                f"{CLEAN_SHAVEN_RULE} {final_prompt} "
                f"ABSOLUTE PROHIBITIONS on face: {CLEAN_SHAVEN_PROHIBITIONS}."
            )

        if negative_prompt:
            final_prompt = f"{final_prompt}\nNegative constraints: {negative_prompt}"

        return final_prompt

    except Exception as e:
        return f"Error in translation: {str(e)}"

from deep_translator import GoogleTranslator
from typing import Dict, Any


def translate_to_english(text: str) -> str:
    if not text:
        return ""
    try:
        clean_text = text.replace("\n", " ").strip()
        return GoogleTranslator(source="auto", target="en").translate(clean_text)
    except Exception as e:
        print(f"⚠️ Erro na tradução: {e}")
        return text


def map_critical_terms(text: str) -> str:
    mapping = {
        "pardo": "mixed race brazilian, latino, tanned skin",
        "negro": "black, afro-descendant, dark skin",
        "branco": "white, caucasian",
        "asiatico": "asian",
        "dreads": "dreadlocks hairstyle",
        "grisalho": "grey hair, aging hair",
        "black power": "afro hair",
        "plus size": "overweight, heavy build, chubby",
        "curvy": "curvy body, thick",
        "magro": "thin, skinny",
    }

    text_lower = (text or "").lower()
    for pt, en in mapping.items():
        if pt in text_lower:
            text_lower = text_lower.replace(pt, en)
    return text_lower


def _normalize_ar(ar_value: str) -> str:
    if not ar_value:
        return "16:9"
    ar_clean = str(ar_value).strip().split(" ")[0].strip()
    return ar_clean or "16:9"


def _framing_pack_by_ar(ar: str) -> str:
    ar = _normalize_ar(ar)

    if ar == "9:16":
        return (
            "Portrait vertical framing (9:16), smartphone screen composition, "
            "subject centered and fully visible, safe margins, no side cropping, "
            "correct headroom, keep important details in the center, "
            "TikTok/Reels style framing, clean composition."
        )

    if ar == "4:5":
        return (
            "Portrait composition (4:5), Instagram feed framing, subject centered, "
            "avoid side cropping, maintain headroom, keep key elements within safe central area."
        )

    if ar == "1:1":
        return (
            "Square composition (1:1), centered subject, balanced framing, "
            "avoid cropping face and hands, keep key elements in the central safe area."
        )

    if ar in {"16:9", "21:9"}:
        return (
            "Landscape cinematic framing, rule of thirds composition, "
            "subject well framed with natural headroom, wide shot if needed, avoid awkward cropping."
        )

    return "Clean balanced composition, subject properly framed, avoid unwanted cropping."


def generate_prompt_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gera somente prompt (não chama Replicate aqui).
    Backend decide: Flux (image_flux) ou Kling (video_kling).
    """

    raw = data.get("raw_data", {}) or {}
    chars = raw.get("characters", []) or []
    technical = raw.get("technical") or {}

    # CORE IDEA: vem do front (generalIdea)
    core_idea_pt = (raw.get("idea") or "").strip()
    core_idea_en = translate_to_english(core_idea_pt) if core_idea_pt else ""

    scene_raw = technical.get("scene_details", "")
    style_raw = raw.get("style", "Photorealistic")

    scene_en = translate_to_english(scene_raw)
    style_en = translate_to_english(style_raw)

    ar = _normalize_ar(data.get("ar", "16:9"))
    framing_pack = _framing_pack_by_ar(ar)

    char_prompts = []
    for char in chars:
        age_raw = str(char.get("age", "30")).replace("anos", "").strip()
        gender_en = translate_to_english(char.get("gender", "person"))

        ethnicity_en = map_critical_terms(char.get("ethnicity", ""))
        body_en = map_critical_terms(char.get("body_type", ""))

        hair_en = translate_to_english(
            map_critical_terms(f"{char.get('hair_style', '')} {char.get('hair_color', '')}")
        )
        face_en = translate_to_english(f"{char.get('face_features', '')} {char.get('expression', '')}")

        clothing_en = translate_to_english(char.get("clothing", ""))
        action_en = translate_to_english(char.get("action", "standing"))

        char_str = (
            f"A {age_raw} years old {ethnicity_en} {gender_en}, {body_en} body. "
            f"Hairstyle: {hair_en}. Face: {face_en}. "
            f"Wearing {clothing_en}. Action: {action_en}."
        )
        char_prompts.append(char_str)

    has_characters = len(chars) > 0

    base_prompt = (
        f"RAW photo, {style_en} style. "
        f"Core idea: {core_idea_en}. "
        f"Core framing: {framing_pack} "
        f"{' '.join(char_prompts)} "
        f"Background context: {scene_en}. "
        f"High fidelity, 8k uhd, dslr, soft lighting, film grain."
    )

    if has_characters:
        base_prompt += (
            ", detailed skin texture, visible pores, natural imperfections, shot on 35mm "
            "--no wax skin, cartoon, blur, doll, plastic skin"
        )
    else:
        base_prompt += ", photorealistic, 8k --no blur, illustration"

    print(f"🧠 Prompt Base ({ar}): {base_prompt[:140]}...")

    return {
        "prompt": base_prompt,
        "ar": ar,
        "instructions": "",
        "provider": "prompt-only",
    }

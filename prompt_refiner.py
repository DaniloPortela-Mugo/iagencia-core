from __future__ import annotations
import random
import re
from typing import List, Tuple, Dict, Any
from src.services.planning_agent import get_client

TECH_VOCABULARY = [
    "cinematic lighting with soft shadows and high micro-contrast",
    "photorealistic textures, visible skin pores, and natural imperfections",
    "shot on Arri Alexa, master prime lens, 8k resolution",
    "depth of field with elegant bokeh, sharp subject focus",
    "editorial color grading, rich tonal range, realistic highlights",
]

SKIN_PROTOCOL = (
 "Raw photography, hyper-realistic skin texture, visible pores, natural skin imperfections,"
"Freckles, moles, rustic finish, sharp focus."
"Unretouched appearance, no plasticky effect,"
"Detailed iris, subsurface scattering"
)

ANTI_PLASTIC = (
    "wax skin, plastic skin, airbrushed, smooth skin, cartoonish, cgi face, doll like, "
    "blur, low resolution, flat lighting"
)

def refine_prompt_for_flux(user_prompt: str, style: str, refiner_data: Dict[str, Any] = None, has_character: bool = True, reference_description: str = "") -> str:
    client = get_client()
    
    # Organiza os dados de entrada
    data = refiner_data if refiner_data else {}
    idea = data.get("idea", user_prompt)
    characters = data.get("characters", [])
    tech = data.get("technical", {})
    context = data.get("context", {})
    constraints = data.get("constraints", {}) or {}
    reference_note = data.get("reference_description") or reference_description or ""

    def sanitize_output(text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"[\\[\\]\\(\\):]", " ", text)
        cleaned = re.sub(r"\\s+", " ", cleaned).strip()
        return cleaned.replace('"', "")

    def sanitize_input(text: Any) -> str:
        if text is None:
            return ""
        cleaned = re.sub(r"[\\[\\]\\(\\):]", " ", str(text))
        return re.sub(r"\\s+", " ", cleaned).strip()

    if not client:
        base = f"{idea}. {SKIN_PROTOCOL}"
        return sanitize_output(base)

    system_prompt = (
        "You are a Senior Director of Photography. Create ONE fluent paragraph in English. "
        "Do not use lists, tags, brackets, parentheses, or colons. "
        "Do not use bullet points. "
        "Integrate all constraints naturally into the narrative. "
        f"Mandatory photographic style includes {SKIN_PROTOCOL}. "
        f"Avoid any artificial or plastic look such as {ANTI_PLASTIC}. "
        "Focus on how light interacts with skin and fabric textures and on spatial relationships."
    )

   
    negative_prompt = sanitize_input(constraints.get("negative_prompt") or "")
    avoid_text_overlay = bool(constraints.get("avoid_text_overlay"))
    negative_rule = f"Exclude elements such as {negative_prompt}." if negative_prompt else ""
    text_rule = "The image contains no text, watermark, logo, signature, poster layout, or decorative frame." if avoid_text_overlay else ""
    reference_rule = sanitize_input(reference_note) if reference_note else ""

    def format_char(c: Dict[str, Any], idx: int) -> str:
        name = sanitize_input(c.get("name") or "")
        physical = sanitize_input(c.get("physical") or c.get("physical_details") or "")
        clothing = sanitize_input(c.get("clothing") or c.get("clothing_details") or "")
        expression = sanitize_input(c.get("expression") or "")
        action = sanitize_input(c.get("action") or "")
        subject = name if name else f"Character {idx + 1}"
        parts = []
        if physical:
            parts.append(f"{subject} is {physical}")
        else:
            parts.append(subject)
        if clothing:
            parts.append(f"wearing {clothing}")
        if expression:
            parts.append(f"with a {expression} expression")
        if action:
            parts.append(f"and {action}")
        return " ".join(parts)

    char_block = " ".join([format_char(c, i) for i, c in enumerate(characters)]) if characters else ""
    tech_bits = []
    if tech.get("style"):
        tech_bits.append(f"style {sanitize_input(tech.get('style'))}")
    if tech.get("lighting"):
        tech_bits.append(f"lighting {sanitize_input(tech.get('lighting'))}")
    if tech.get("camera"):
        tech_bits.append(f"camera {sanitize_input(tech.get('camera'))}")
    if tech.get("view"):
        tech_bits.append(f"view {sanitize_input(tech.get('view'))}")
    if tech.get("angle"):
        tech_bits.append(f"angle {sanitize_input(tech.get('angle'))}")
    if tech.get("format"):
        tech_bits.append(f"format {sanitize_input(tech.get('format'))}")
    tech_block = " and ".join([b for b in tech_bits if b])

    segments: List[str] = []
    if idea:
        scene_text = sanitize_input(idea)
        if re.match(r"^(the|a|an|he|she|they|this|that|these|those)\\b", scene_text, re.IGNORECASE):
            segments.append(f"{scene_text}.")
        else:
            segments.append(f"The scene shows {scene_text}.")
    if char_block:
        segments.append(f"{char_block}.")
    if tech_block:
        segments.append(f"Technical direction {tech_block}.")
    rules = " ".join([shaving_rule, gaze_rule, text_rule, negative_rule, reference_rule]).strip()
    if rules:
        segments.append(rules)
    user_payload = " ".join(segments)

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create the final prompt: {user_payload}. Use a variation of: {random.choice(TECH_VOCABULARY)}"}
            ],
            temperature=0.4,
        )
        return sanitize_output(completion.choices[0].message.content.strip())
    except Exception as e:
        print(f"Error: {e}")
        return sanitize_output(f"{idea}. {SKIN_PROTOCOL}")

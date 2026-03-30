import random

# Excertos da sua Library (prompt_library.md) para dar contexto à IA
LIBRARY_EXAMPLES = """
- Fotografia Produto: "Use natural or cinematic lighting to enhance the product’s appeal. Softly blurred background with natural morning light, soft shadows, calm and focused. Ultra-HD, photorealistic."
- Retrato: "Porcelain skin, short jet-black bobbed hair, graceful figure. Captured in Canon EOS R5 clarity with vivid cinematic lighting. 8k resolution."
- Editorial: "Cinematic shot, volumetric lighting, 35mm lens. Ultra detailed, sharp focus, intricate details, masterpiece."
"""

SKIN_PROTOCOL = "detailed skin texture, visible pores, natural imperfections, no makeup look, shot on 35mm, hyper-realistic texture"
ANTI_PLASTIC = "wax skin, plastic skin, airbrushed, smooth skin, cartoonish, cgi face"

def refine_prompt_logic(client, raw_data, media_type):
    """
    Transforma a ideia bruta em um Prompt Cinematográfico Fluido.
    Aplica o Protocolo de Pele se houver personagens, removendo qualquer aspecto de lista ou colchete.
    """
    
    idea = raw_data.get("idea", "")
    style = raw_data.get("style", "Fotorrealista")
    tech = raw_data.get("technical", {})
    characters = raw_data.get("characters", [])
    
    # Detecção simples se tem personagem definido
    has_character = len(characters) > 0 and (characters[0].get("gender") or characters[0].get("age"))

    # 1. Montagem do Contexto de Personagens (Linguagem Natural Base)
    char_desc = ""
    if has_character:
        for i, c in enumerate(characters):
            # Limpamos os rótulos (como "body_type:") para evitar que a IA crie listas
            details = [
                f"a {c.get('age')}-year-old" if c.get('age') else "",
                c.get('ethnicity'),
                c.get('gender'),
                f"with a {c.get('body_type')} build" if c.get('body_type') else "",
                f"having {c.get('hair_style')} {c.get('hair_color')} hair" if c.get('hair_style') else "",
                f"wearing {c.get('clothing')}" if c.get('clothing') else "",
                f"showing a {c.get('expression')} expression" if c.get('expression') else "",
                f"currently {c.get('action')}" if c.get('action') else ""
            ]
            clean_details = " ".join([d for d in details if d])
            char_desc += f"Character {i+1} is {clean_details}. "

    # 2. Configurações Técnicas
    tech_desc = f"Lighting: {tech.get('lighting', 'Cinematic')}. Camera: {tech.get('camera', '35mm')}. Angle: {tech.get('angle', 'Eye Level')}."
    if media_type == 'video':
        tech_desc += f" Camera Movement: {tech.get('movement', 'Static')}."

    # 3. Definição do System Prompt (A Mágica da Linguagem Orgânica)
    if has_character:
        system_instructions = f"""
        YOU ARE AN EXPERT PROMPT ENGINEER FOR ADVANCED AI IMAGE GENERATORS (LIKE FLUX.1 AND VEO).
        YOUR TASK: Translate and weave the provided concepts into a SINGLE, FLUID, CINEMATIC PARAGRAPH in English.
        
        CRITICAL RULES:
        - DO NOT use lists, numbers, bullet points, brackets [], or braces {{}}.
        - DO NOT use labels like "Subject:", "Action:", or "Environment:".
        - Write a continuous, highly descriptive, and organic visual narrative.

        INGREDIENTS TO WEAVE TOGETHER ORGANICALLY:
        - Character(s): {char_desc}
        - Scene/Environment: {idea}
        - Technical Style: {tech_desc}, {style} style.
        
        MANDATORY SKIN PROTOCOL (Integrate this naturally into the character's description):
        "{SKIN_PROTOCOL}"
        
        NEGATIVE CONSTRAINTS: {ANTI_PLASTIC}
        
        OUTPUT FORMAT: A single, dense, high-quality English paragraph. Nothing else.
        """
    else:
        system_instructions = f"""
        YOU ARE AN EXPERT PROMPT ENGINEER FOR ADVANCED AI IMAGE GENERATORS (LIKE FLUX.1 AND VEO).
        YOUR TASK: Translate and weave the provided concepts into a SINGLE, FLUID, CINEMATIC PARAGRAPH in English.
        
        CRITICAL RULES:
        - DO NOT use lists, numbers, bullet points, brackets [], or braces {{}}.
        - DO NOT use labels like "Subject:", or "Environment:".
        - Write a continuous, highly descriptive, and organic visual narrative.

        INGREDIENTS TO WEAVE TOGETHER ORGANICALLY:
        - Main Subject & Scene: {idea}
        - Composition: {tech.get('view', 'centered')}, rule of thirds.
        - Technical Style: {tech_desc}, {style} style.
        
        Examples of cinematic flow:
        {LIBRARY_EXAMPLES}
        
        OUTPUT FORMAT: A single, dense, high-quality English paragraph. Nothing else.
        """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"Optimize this concept into a fluid prompt: {idea}"}
            ],
            # Aumentamos levemente a temperatura (0.7) para permitir que a IA 
            # conecte as frases de forma mais criativa e natural, sem ser robótica.
            temperature=0.7 
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro no refiner: {e}")
        return f"{idea}. {style}. {tech_desc}" # Fallback
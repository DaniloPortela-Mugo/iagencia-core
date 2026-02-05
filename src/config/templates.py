# Templates de Prompt e Configurações de Modo

TEMPLATES_PLATAFORMA = {
    # IMAGEM
    "Nano Banana (Imagen 3 / Gemini)": ["subject", "context", "lighting_atmosphere", "style_flag", "technical", "instructions"],
    "Midjourney (v6/v7)": ["reference", "subject", "context", "style_flag", "mj_params", "negative_mj"],
    "Seedream 4.5 (ByteDance / Doubao)": ["narrative", "context", "lighting_atmosphere", "style_flag", "technical", "instructions"],
    "Stable Diffusion": ["subject", "context", "instructions", "weight_char", "negative_sd", "sampler", "style_flag"],
    # VÍDEO
    "Veo 3 (Google)": ["cinematic_style", "scene", "camera_movement", "lighting_atmosphere", "subject_action", "style_flag", "format_video", "audio_block"],
    "Sora (OpenAI)": ["context", "subject_action", "physics_materials", "camera_movement", "style_flag", "format_video", "audio_block"],
    "Kling (Kling AI)": ["visual_dense", "subject_action", "motion_emphasis", "style_flag", "format_video", "audio_block"],
    "Runway": ["reference", "context", "subject_action", "camera_movement", "style_flag", "format_video", "audio_block"],
}

MODE_CONFIG = {
    "DA PRO (Publicidade)": {
        "show_advanced": True,
        "prompt_editable": True,
        "show_sampler": True,
        "show_negative": True,
        "prefer_reference": False,
    },
    "Social (Digital / Social Media)": {
        "show_advanced": False,
        "prompt_editable": False,
        "show_sampler": False,
        "prefer_reference": True,
    },
}
import time
import random

def production_simulation_node(state):
    """
    Simula a chamada de API (Agentes 6.1 e 6.2).
    Na versão real, aqui entra o requests.post para Midjourney/OpenAI.
    """
    print("--- [TOOL] Production Engine (Simulated) ---")
    
    final_prompt = state.final_prompt_en
    platform = state.request.target_platform
    
    print(f"🚀 ENVIANDO PARA {platform.upper()}...")
    print(f"📡 Payload: '{final_prompt}'")
    
    # Simula latência de rede
    time.sleep(1) 
    
    # Simula resposta da API
    mock_result = {
        "job_id": f"job_{random.randint(1000,9999)}",
        "status": "success",
        "media_url": "https://cdn.iagencia.ai/temp/result_01.png",
        "cost": 0.08
    }
    
    print("✅ Mídia Gerada com Sucesso.")
    
    return {"generation_result": mock_result, "status": "DONE"}
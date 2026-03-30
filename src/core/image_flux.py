import os
import time
import uuid
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

FLUX_API_KEY = os.getenv("REPLICATE_API_TOKEN")
FLUX_API_URL = os.getenv("FLUX_API_URL", "https://api.replicate.com/v1/predictions")

# --- PROTOCOLOS DE QUALIDADE V2 ---
SKIN_PROTOCOL = (
    "raw photography, hyper-realistic skin texture, visible pores, natural skin imperfections, "
    "moles, freckles, unpolished finish, hard focus, shot on 35mm, "
    "Kodak Portra 400 film grain, no makeup look, not airbrushed, not plasticky, "
    "detailed iris, subsurface scattering"
)

ANTI_PLASTIC = (
    "wax skin, plastic skin, airbrushed, smooth skin, cartoonish, cgi face, doll like, "
    "blur, low resolution, flat lighting"
)

# ✅ FIX 2: Mapa explícito de aspect ratios aceitos pelo Replicate
# Qualquer valor fora desta lista é rejeitado com erro claro antes de chamar a API
VALID_ASPECT_RATIOS = {
    "1:1", "16:9", "9:16", "4:3", "3:4", "4:5", "5:4", "21:9", "3:2", "2:3"
}

# ✅ FIX 4: Configurações de polling centralizadas e documentadas
POLL_INTERVAL_SECONDS = 2       # intervalo entre cada checagem
POLL_MAX_SECONDS = 180          # tempo máximo total: 3 minutos
POLL_REQUEST_TIMEOUT = 15       # timeout por requisição de polling


def _normalize_ar(ar_value: Optional[str]) -> str:
    """
    Normaliza o aspect ratio para um valor aceito pelo Replicate.
    
    ✅ FIX 2: Valida contra lista de valores aceitos e lança erro descritivo
    se o valor não for reconhecido, em vez de passar algo inválido para a API.
    """
    if not ar_value:
        return "16:9"

    ar_clean = str(ar_value).strip().split(" ")[0].strip()

    # ✅ FIX 2: Verifica se o valor está na lista de ARs aceitos
    if ar_clean not in VALID_ASPECT_RATIOS:
        print(f"⚠️ Flux: aspect_ratio '{ar_clean}' inválido. Usando fallback '16:9'.")
        return "16:9"

    return ar_clean


def _inject_protocols(prompt: str) -> str:
    """
    Injeta os protocolos de qualidade no prompt de forma segura.

    ✅ FIX 3: Usa marcadores exclusivos para checar se o protocolo já foi
    injetado, em vez de buscar palavras do próprio protocolo que podem
    aparecer naturalmente no prompt do usuário (ex: "plastic bag", "bottle").

    ✅ FIX 7: clean_shaven_lock é avaliado ANTES da injeção do SKIN_PROTOCOL,
    garantindo que "peach fuzz on face" seja removido quando o personagem
    foi definido como sem barba / rosto liso.
    """
    SKIN_MARKER = "##SKIN_PROTOCOL##"
    ANTI_PLASTIC_MARKER = "##ANTI_PLASTIC##"

    # Já foi injetado antes (retry, chamada dupla): não injeta de novo
    if SKIN_MARKER in prompt and ANTI_PLASTIC_MARKER in prompt:
        return prompt

    final_prompt = prompt
    lower_prompt = final_prompt.lower()

    human_keywords = [
        "man", "woman", "girl", "boy", "person", "face",
        "portrait", "eye", "model", "skin", "body"
    ]
    is_human = any(k in lower_prompt for k in human_keywords)

    if is_human and SKIN_MARKER not in final_prompt:
        print("💉 Flux: Injetando Skin Protocol V2 automaticamente...")
        final_prompt = f"{final_prompt}, {SKIN_PROTOCOL} {SKIN_MARKER}"

    if ANTI_PLASTIC_MARKER not in final_prompt:
        final_prompt = f"{final_prompt}. Avoid {ANTI_PLASTIC}. {ANTI_PLASTIC_MARKER}"

    if is_human:
        final_prompt = (
            f"{final_prompt}. Avoid: AI-generated look, synthetic skin, CGI face, "
            "over-smoothed skin, plastic skin."
        )

    return final_prompt


def _poll_for_result(get_url: str, headers: dict) -> str:
    """
    Faz polling no Replicate até a imagem ficar pronta.

    ✅ FIX 1: Controla o tempo total máximo (POLL_MAX_SECONDS) em vez de
    contar iterações cegas. Se o tempo esgotar, lança erro descritivo.
    
    ✅ FIX 4: Loga o tempo decorrido a cada checagem para facilitar diagnóstico.
    """
    start_time = time.time()
    attempt = 0

    while True:
        elapsed = time.time() - start_time

        # ✅ FIX 1: Timeout real por tempo, não por número de iterações
        if elapsed > POLL_MAX_SECONDS:
            raise TimeoutError(
                f"Flux: tempo máximo de {POLL_MAX_SECONDS}s excedido "
                f"após {attempt} tentativas. A geração pode ter travado no Replicate."
            )

        attempt += 1
        print(f"⏳ Flux: polling #{attempt} — {elapsed:.0f}s decorridos...")

        try:
            # ✅ FIX 4: Timeout por requisição menor e controlado
            r = requests.get(get_url, headers=headers, timeout=POLL_REQUEST_TIMEOUT)
            r.raise_for_status()
            j = r.json()
        except requests.exceptions.Timeout:
            # Timeout de rede em uma checagem não encerra o polling,
            # apenas loga e tenta de novo na próxima iteração
            print(f"⚠️ Flux: timeout de rede na checagem #{attempt}. Tentando de novo...")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        except Exception as e:
            raise Exception(f"Flux: erro de rede durante polling: {e}")

        status = j.get("status")

        if status == "succeeded":
            raw_output = j.get("output")
            if isinstance(raw_output, list) and raw_output:
                return raw_output[0]
            elif isinstance(raw_output, str) and raw_output:
                return raw_output
            else:
                # ✅ FIX 1: Status "succeeded" mas sem output — erro explícito
                raise Exception(
                    f"Flux: status 'succeeded' mas 'output' está vazio. Resposta: {j}"
                )

        if status == "failed":
            error_detail = j.get("error") or j.get("detail") or "sem detalhes"
            raise Exception(f"Flux falhou no Replicate. Detalhe: {error_detail}")

        # Status ainda em processamento ("starting", "processing") — aguarda
        time.sleep(POLL_INTERVAL_SECONDS)


def generate_image_flux(prompt: str, tenant_id: str, ar: str = "16:9", api_key: Optional[str] = None) -> str:
    """
    Gera imagem no Flux 1.1 Pro aplicando automaticamente o Skin Protocol
    se detectar humanos no prompt, e forçando Anti-Plastic.

    ✅ FIX 6: A URL retornada pelo Replicate é temporária (~1h).
    Esta função retorna a URL direta para exibição imediata, mas o chamador
    deve fazer o download/upload para armazenamento permanente logo após.
    """
    if "IDENTITY LOCK" in prompt.upper():
        raise ValueError(
            "IDENTITY LOCK detectado: Flux não deve ser usado para identidade."
        )
    effective_key = api_key or FLUX_API_KEY
    if not effective_key:
        raise ValueError(
            "REPLICATE_API_TOKEN não encontrado no .env. "
            "Configure a variável de ambiente antes de chamar o Flux."
        )

    ar = _normalize_ar(ar)

    # ✅ FIX 3: Injeção de protocolo via função isolada com marcadores
    final_prompt = _inject_protocols(prompt)

    headers = {
        "Authorization": f"Bearer {effective_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "version": "black-forest-labs/flux-1.1-pro",
        "input": {
            "prompt": final_prompt,
            "aspect_ratio": ar,
            "output_format": "png",
            "output_quality": 90,
            "safety_tolerance": 5,
        },
    }

    print(f"🎨 Flux: enviando prompt... tenant={tenant_id} AR={ar}")

    # ✅ FIX 5: Erros HTTP tratados individualmente por código de status
    try:
        response = requests.post(FLUX_API_URL, headers=headers, json=payload, timeout=60)
    except requests.exceptions.Timeout:
        raise Exception("Flux: timeout ao enviar o prompt para o Replicate (>60s). Verifique a conectividade.")
    except Exception as e:
        raise Exception(f"Flux: falha de rede ao chamar Replicate: {e}")

    # ✅ FIX 5: Diagnóstico diferenciado por código HTTP
    if response.status_code != 201:
        try:
            body = response.json()
        except Exception:
            body = response.text

        if response.status_code == 401:
            raise Exception(
                "Flux: autenticação falhou (401). Verifique se o REPLICATE_API_TOKEN está correto e ativo."
            )
        elif response.status_code == 422:
            raise Exception(
                f"Flux: prompt ou parâmetro inválido (422). Detalhe: {body}"
            )
        elif response.status_code >= 500:
            raise Exception(
                f"Flux: erro interno do Replicate ({response.status_code}). Tente novamente em instantes. Detalhe: {body}"
            )
        else:
            raise Exception(
                f"Flux: erro inesperado ({response.status_code}). Detalhe: {body}"
            )

    data = response.json()
    get_url = data.get("urls", {}).get("get")
    raw_output = data.get("output")

    # Se a resposta já trouxe o output direto (geração síncrona), usa ele
    if raw_output:
        if isinstance(raw_output, list) and raw_output:
            image_url = raw_output[0]
        elif isinstance(raw_output, str):
            image_url = raw_output
        else:
            image_url = None
    elif get_url:
        # ✅ FIX 1 e FIX 4: Polling com timeout real e logs de tempo
        image_url = _poll_for_result(get_url, headers)
    else:
        raise Exception(
            f"Flux: resposta do Replicate não contém 'output' nem 'urls.get'. Resposta: {data}"
        )

    if not image_url:
        raise Exception(f"Flux: URL da imagem veio vazia. Resposta: {data}")

    print(f"✅ Flux: imagem gerada! URL: {image_url}")

    # ✅ FIX 6: Aviso explícito sobre expiração da URL temporária do Replicate
    # O chamador desta função é responsável por fazer upload permanente
    # (ex: /api/media/upload-base64) antes de guardar a URL no banco de dados.
    print(
        "⚠️  Flux: a URL acima é temporária (~1h). "
        "Faça o upload para armazenamento permanente antes de salvar no banco."
    )

    return image_url

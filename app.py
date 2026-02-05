import os
import time
import uuid
from pathlib import Path
from typing import List, Optional

import requests
import streamlit as st
from dotenv import load_dotenv
from pydantic import BaseModel

# Se você realmente usa FastAPI decorators no mesmo arquivo:
from fastapi import FastAPI, HTTPException

load_dotenv()

from src.core.security import SecurityManager
from src.core.workflow import build_workflow
from src.core.state import UserContext, TaskRequest, CampaignState
from src.core.financial import FinancialManager


# =========================================================
# FASTAPI APP (rotas /chat)
# =========================================================
app = FastAPI()


# =========================================================
# REPLICATE (FLUX)
# =========================================================
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
REPLICATE_BASE_URL = "https://api.replicate.com/v1"

# Você pode passar:
# - slug do modelo (recomendado): black-forest-labs/flux-1.1-pro
# - OU version id (hash/uuid) diretamente
FLUX_MODEL = os.getenv("FLUX_MODEL", "black-forest-labs/flux-1.1-pro")

MEDIA_DIR = Path("media")
MEDIA_DIR.mkdir(exist_ok=True)


def replicate_headers() -> dict:
    if not REPLICATE_API_TOKEN:
        raise ValueError("REPLICATE_API_TOKEN não configurado no .env")
    return {
        "Authorization": f"Token {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }


def is_version_id(value: str) -> bool:
    """
    Heurística simples: version_id do Replicate geralmente é um hash longo (hex)
    ou uuid. Slug tem '/'.
    """
    if not value:
        return False
    if "/" in value:
        return False
    # hash hex longo
    if len(value) >= 20:
        return True
    return False


def get_latest_version_id(model_slug: str) -> str:
    """
    Busca latest_version.id no endpoint /models/{owner}/{name}
    """
    try:
        owner, name = model_slug.split("/", 1)
    except ValueError as exc:
        raise ValueError(
            f"FLUX_MODEL inválido: '{model_slug}'. Use formato 'owner/name'."
        ) from exc

    url = f"{REPLICATE_BASE_URL}/models/{owner}/{name}"
    r = requests.get(url, headers=replicate_headers(), timeout=60)
    r.raise_for_status()
    data = r.json()

    latest = data.get("latest_version")
    if not latest or not latest.get("id"):
        raise RuntimeError(f"Não encontrei latest_version.id para {model_slug}. Resposta: {data}")

    return latest["id"]


def create_prediction(version_id: str, prompt: str, width: int, height: int) -> dict:
    url = f"{REPLICATE_BASE_URL}/predictions"
    payload = {
        "version": version_id,
        "input": {
            "prompt": prompt,
            "width": width,
            "height": height,
            # Alguns modelos aceitam "num_outputs", "guidance_scale", "steps" etc.
            # Deixe comentado para não quebrar por parâmetro inválido:
            # "num_outputs": 1,
            # "guidance_scale": 7.5,
            # "num_inference_steps": 28,
        },
    }

    r = requests.post(url, headers=replicate_headers(), json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Erro Replicate create_prediction: {r.status_code} {r.text}")
    return r.json()


def poll_prediction(prediction: dict, timeout_s: int = 180, poll_s: float = 1.25) -> dict:
    """
    Polling via prediction['urls']['get'] (padrão Replicate)
    """
    get_url = prediction.get("urls", {}).get("get")
    if not get_url:
        raise RuntimeError(f"Prediction sem urls.get: {prediction}")

    t0 = time.time()
    while True:
        r = requests.get(get_url, headers=replicate_headers(), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Erro Replicate poll: {r.status_code} {r.text}")
        data = r.json()

        status = data.get("status")
        if status in ("succeeded", "failed", "canceled"):
            return data

        if time.time() - t0 > timeout_s:
            raise TimeoutError("Timeout aguardando Replicate finalizar.")

        time.sleep(poll_s)


def extract_image_url(final_data: dict) -> str:
    """
    Replicate pode retornar:
    - output: ["https://...png", ...]
    - output: "https://...png"
    - output: {...} (menos comum)
    """
    output = final_data.get("output")
    if isinstance(output, list) and output:
        if isinstance(output[0], str):
            return output[0]
    if isinstance(output, str):
        return output

    raise RuntimeError(f"Formato de output inesperado: {output}")


def save_image_from_url(image_url: str, tenant_id: str) -> str:
    img = requests.get(image_url, timeout=120)
    if img.status_code >= 400:
        raise RuntimeError(f"Falha ao baixar imagem: {img.status_code} {img.text}")

    tenant_dir = MEDIA_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.png"
    filepath = tenant_dir / filename
    filepath.write_bytes(img.content)
    return str(filepath)


def generate_image_flux_replicate(prompt: str, tenant_id: str, width: int = 1024, height: int = 1024) -> str:
    """
    Flux via Replicate:
    - aceita FLUX_MODEL como slug 'owner/name' OU version_id
    - busca latest_version.id automaticamente se necessário
    - gera prediction, poll, baixa e salva em /media/<tenant>/
    """
    model_value = FLUX_MODEL.strip()

    if is_version_id(model_value):
        version_id = model_value
    else:
        version_id = get_latest_version_id(model_value)

    pred = create_prediction(version_id, prompt, width, height)
    final = poll_prediction(pred)
    if final.get("status") != "succeeded":
        raise RuntimeError(f"Replicate falhou: {final.get('error') or final}")

    image_url = extract_image_url(final)
    return save_image_from_url(image_url, tenant_id)


# =========================================================
# --- MODELO DE DADOS CHAT
# =========================================================
class ChatMessage(BaseModel):
    contact_id: int
    sender: str  # 'me' ou 'them'
    content: str


# =========================================================
# --- ROTAS CHAT
# =========================================================
@app.get("/chat/{contact_id}")
def get_chat_history(contact_id: int):
    try:
        response = (
            SecurityManager.db.table("chat_messages")
            .select("*")
            .eq("contact_id", contact_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data
    except Exception as e:
        print(f"Erro ao buscar chat: {e}")
        return []


@app.post("/chat")
def send_message(msg: ChatMessage):
    try:
        SecurityManager.db.table("chat_messages").insert(
            {"contact_id": msg.contact_id, "sender": msg.sender, "content": msg.content}
        ).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# STREAMLIT UI
# =========================================================
st.set_page_config(page_title="IAgência", page_icon="🔴", layout="wide")

st.markdown(
    """
<style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { background-color: #E50914; color: white; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #B20710; }
    .card-user { padding: 10px; border: 1px solid #333; border-radius: 5px; background: #161b22; margin-bottom: 10px; }
</style>
""",
    unsafe_allow_html=True,
)

# Sessão
if "user" not in st.session_state:
    st.session_state.user = None
if "workflow_state" not in st.session_state:
    st.session_state.workflow_state = "IDLE"
if "current_thread_id" not in st.session_state:
    st.session_state.current_thread_id = None

# Estado de imagem
if "tenant_id" not in st.session_state:
    st.session_state.tenant_id = "agencia_mugo"
if "generated_image_path" not in st.session_state:
    st.session_state.generated_image_path = None
if "final_prompt_en" not in st.session_state:
    st.session_state.final_prompt_en = None


def run_graph_step(input_state, thread_id):
    flow = build_workflow()
    config = {"configurable": {"thread_id": thread_id}}
    container = st.container()

    with container:
        iterator = flow.stream(input_state, config) if input_state else flow.stream(None, config)
        for event in iterator:
            for node, output in event.items():
                if node == "guardian":
                    if not output.get("financial_approved", True):
                        st.error(f"🛑 BLOQUEADO: {output.get('kanban_status')}")
                        if "financial_reason" in output:
                            st.caption(output["financial_reason"])
                        st.session_state.workflow_state = "DONE"
                        return

                with st.expander(f"🤖 {node.upper()}", expanded=True):
                    if "draft_prompt_pt" in output or "prompt_draft_pt" in output:
                        text = output.get("prompt_draft_pt") or output.get("draft_prompt_pt")
                        st.info(f"📝 Rascunho: {text}")

                    elif "final_prompt_en" in output:
                        final_prompt = output["final_prompt_en"]
                        st.session_state.final_prompt_en = final_prompt
                        st.success(f"🇺🇸 Prompt Final: {final_prompt}")

                        # ✅ Gera imagem com Flux/Replicate
                        with st.spinner("🎨 Gerando imagem com FLUX (Replicate)..."):
                            try:
                                image_path = generate_image_flux_replicate(
                                    prompt=final_prompt,
                                    tenant_id=st.session_state.tenant_id,
                                    width=1024,
                                    height=1024,
                                )
                                st.session_state.generated_image_path = image_path
                                st.success("🖼️ Imagem gerada e salva com sucesso!")
                                st.caption(f"Arquivo: {image_path}")
                            except Exception as e:
                                st.error("Falha ao gerar imagem via Replicate/Flux.")
                                st.code(str(e))

                    elif "financial_approved" in output:
                        st.success(f"💰 Aprovado. Custo: ${output.get('current_cost')}")

    snapshot = flow.get_state(config)
    if snapshot.next:
        st.session_state.workflow_state = "APPROVAL_WAIT"
    else:
        st.session_state.workflow_state = "DONE"


def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔴 IAgência Login")
        st.markdown("Selecione um usuário cadastrado em `internal_users.json`:")

        users_list = SecurityManager.get_all_users_for_ui()
        user_options = {f"{u['name']} ({u['role']})": u for u in users_list}

        if not users_list:
            st.error("Nenhum usuário encontrado em `data/system/internal_users.json`.")
            return

        selected_label = st.selectbox("Usuário", list(user_options.keys()))
        selected_user_data = user_options[selected_label]

        st.caption(
            f"E-mail: {selected_user_data['email']} | Acesso: {selected_user_data.get('client_access')}"
        )

        password = st.text_input("Senha", type="password", value="123")

        if st.button("Entrar"):
            user = SecurityManager.authenticate(selected_user_data["email"], password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Erro ao autenticar.")


def main_app():
    user = st.session_state.user

    with st.sidebar:
        st.markdown(f"## 👤 {user['name']}")
        st.caption(f"Cargo: {user['role']}")

        available_clients = user.get("client_access", []) or []

        if "*" in available_clients:
            try:
                clients_path = os.path.join("data", "tenants", "agencia_mugo", "clients")
                available_clients = (
                    os.listdir(clients_path) if os.path.exists(clients_path) else ["varejo", "moda"]
                )
            except Exception:
                available_clients = ["varejo", "moda"]

        selected_client_id = st.selectbox("Cliente", available_clients)

        if isinstance(selected_client_id, list):
            selected_client_id = selected_client_id[0]

        tenant_id = user.get("tenant_id", "agencia_mugo")
        if isinstance(tenant_id, list):
            tenant_id = tenant_id[0]

        st.session_state.tenant_id = tenant_id

        client_config = SecurityManager.get_client_config(tenant_id, selected_client_id)

        st.divider()
        st.metric("Carteira", f"${client_config.get('wallet_balance', 0)}")
        st.caption(f"Voz: {client_config.get('tone_of_voice', 'Padrão')}")

        # Debug útil (pra ver se env está carregando)
        with st.expander("Diagnóstico Flux/Replicate", expanded=False):
            st.write("FLUX_MODEL:", FLUX_MODEL)
            st.write("Token configurado:", bool(REPLICATE_API_TOKEN))

        if st.button("Sair"):
            st.session_state.user = None
            st.session_state.generated_image_path = None
            st.session_state.final_prompt_en = None
            st.rerun()

    st.header(f"Painel: {client_config.get('brand_name', selected_client_id)}")

    tab1, tab2 = st.tabs(["🚀 Nova Tarefa", "✅ Aprovações"])

    with tab1:
        with st.form("task_form"):
            c1, c2 = st.columns(2)
            campaign = c1.text_input("Campanha", "Verão 2026")
            task_name = c2.text_input("Peça", "Post Instagram")

            st.markdown("**Departamentos:**")
            cc1, cc2, cc3, cc4 = st.columns(4)
            d_plan = cc1.checkbox("Planejamento")
            d_create = cc2.checkbox("Criação", value=True)
            d_media = cc3.checkbox("Mídia")
            d_prod = cc4.checkbox("Produção", value=True)

            deliverables = st.multiselect(
                "Entregáveis",
                [
                    "image_feed",
                    "video_short",
                    "copy_deck",
                    "pack_criativo",
                    "avatar_video",
                    "media_plan",
                    "audio_locucao",
                    "audio_trilha",
                ],
                ["image_feed"],
            )

            desc = st.text_area("Briefing", "Imagem vibrante do produto na praia...")
            submitted = st.form_submit_button("Iniciar Job")

            if submitted:
                st.session_state.generated_image_path = None
                st.session_state.final_prompt_en = None

                user_ctx = UserContext(
                    user_id=user["id"],
                    email=user["email"],
                    role=user["role"],
                    tenant_id=tenant_id,
                    client_id=selected_client_id,
                )

                deps = []
                if d_plan:
                    deps.append("planejamento")
                if d_create:
                    deps.append("criacao")
                if d_media:
                    deps.append("midia")
                if d_prod:
                    deps.append("producao")

                req = TaskRequest(
                    campaign_name=campaign,
                    task_name=task_name,
                    description=desc,
                    departments_involved=deps,
                    deliverables=deliverables,
                )

                st.session_state.current_thread_id = f"job_{int(time.time())}"
                st.session_state.workflow_state = "RUNNING"

                initial_state = CampaignState(user=user_ctx, request=req)
                run_graph_step(initial_state, st.session_state.current_thread_id)
                st.rerun()

        # Área de visualização
        if st.session_state.generated_image_path:
            st.divider()
            st.subheader("🖼️ Visualização da Imagem (Flux/Replicate)")
            st.image(st.session_state.generated_image_path, use_container_width=True)

            try:
                with open(st.session_state.generated_image_path, "rb") as f:
                    st.download_button(
                        "⬇️ Baixar imagem",
                        f,
                        file_name=os.path.basename(st.session_state.generated_image_path),
                        mime="image/png",
                    )
            except Exception as e:
                st.error(f"Erro ao preparar download: {e}")

    with tab2:
        if st.session_state.workflow_state == "APPROVAL_WAIT":
            st.warning("Aguardando sua aprovação.")

            flow = build_workflow()
            cfg = {"configurable": {"thread_id": st.session_state.current_thread_id}}
            snapshot = flow.get_state(cfg)

            vals = snapshot.values
            draft = vals.get("prompt_draft_pt") or vals.get("draft_prompt_pt", "")

            edited = st.text_area("Editar Prompt", value=draft, height=150)

            if st.button("Aprovar"):
                flow.update_state(cfg, {"prompt_draft_pt": edited})
                run_graph_step(None, st.session_state.current_thread_id)
                st.rerun()

        elif st.session_state.workflow_state == "DONE":
            st.success("Job Finalizado.")
            if st.session_state.generated_image_path:
                st.image(st.session_state.generated_image_path, use_container_width=True)


if st.session_state.user is None:
    login_screen()
else:
    main_app()

import streamlit as st
import time
import os
from dotenv import load_dotenv

load_dotenv()

from src.core.security import SecurityManager
from src.core.workflow import build_workflow
from src.core.state import UserContext, TaskRequest, CampaignState
from src.core.financial import FinancialManager

from pydantic import BaseModel
from typing import List


# --- MODELO DE DADOS ---
class ChatMessage(BaseModel):
    contact_id: int
    sender: str  # 'me' ou 'them'
    content: str

# --- ROTA: PEGAR HISTÓRICO ---
@app.get("/chat/{contact_id}")
def get_chat_history(contact_id: int):
    try:
        # Busca mensagens ordenadas por data (mais antigas primeiro)
        response = SecurityManager.db.table("chat_messages")\
            .select("*")\
            .eq("contact_id", contact_id)\
            .order("created_at", desc=False)\
            .execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar chat: {e}")
        return []

# --- ROTA: ENVIAR MENSAGEM ---
@app.post("/chat")
def send_message(msg: ChatMessage):
    try:
        SecurityManager.db.table("chat_messages").insert({
            "contact_id": msg.contact_id,
            "sender": msg.sender,
            "content": msg.content
        }).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

st.set_page_config(page_title="IAgência", page_icon="🔴", layout="wide")

# CSS Estilo Netflix/Dark
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button { background-color: #E50914; color: white; border: none; font-weight: bold; }
    .stButton>button:hover { background-color: #B20710; }
    .card-user { padding: 10px; border: 1px solid #333; border-radius: 5px; background: #161b22; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# Sessão
if "user" not in st.session_state: st.session_state.user = None
if "workflow_state" not in st.session_state: st.session_state.workflow_state = "IDLE"
if "current_thread_id" not in st.session_state: st.session_state.current_thread_id = None

# --- LÓGICA DE GRAFO (IGUAL AO ANTERIOR) ---
def run_graph_step(input_state, thread_id):
    app = build_workflow()
    config = {"configurable": {"thread_id": thread_id}}
    container = st.container()
    
    with container:
        iterator = app.stream(input_state, config) if input_state else app.stream(None, config)
        for event in iterator:
            for node, output in event.items():
                if node == "guardian":
                    if not output.get("financial_approved", True):
                        st.error(f"🛑 BLOQUEADO: {output.get('kanban_status')}")
                        if "financial_reason" in output: st.caption(output['financial_reason'])
                        st.session_state.workflow_state = "DONE"
                        return

                with st.expander(f"🤖 {node.upper()}", expanded=True):
                    # st.json(output) # Debug JSON
                    if "draft_prompt_pt" in output: # Mudou para draft_prompt_pt no visual.py corrigido?
                        # O visual.py atual usa prompt_draft_pt (verifique se seus arquivos batem)
                        # Vamos suportar ambos para garantir:
                        text = output.get("prompt_draft_pt") or output.get("draft_prompt_pt")
                        st.info(f"📝 Rascunho: {text}")
                    elif "final_prompt_en" in output:
                        st.success(f"🇺🇸 Prompt Final: {output['final_prompt_en']}")
                    elif "financial_approved" in output:
                        st.success(f"💰 Aprovado. Custo: ${output.get('current_cost')}")

    snapshot = app.get_state(config)
    if snapshot.next:
        st.session_state.workflow_state = "APPROVAL_WAIT"
    else:
        st.session_state.workflow_state = "DONE"

# --- TELA DE LOGIN ATUALIZADA ---
def login_screen():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔴 IAgência Login")
        st.markdown("Selecione um usuário cadastrado em `internal_users.json`:")
        
        # 1. Carrega usuários do JSON
        users_list = SecurityManager.get_all_users_for_ui()
        
        # 2. Cria opções para o selectbox
        # Formato: "Nome (Role) - Email"
        user_options = {f"{u['name']} ({u['role']})": u for u in users_list}
        
        if not users_list:
            st.error("Nenhum usuário encontrado em `data/system/internal_users.json`.")
            return

        selected_label = st.selectbox("Usuário", list(user_options.keys()))
        selected_user_data = user_options[selected_label]

        # Mostra detalhes (Debug)
        st.caption(f"E-mail: {selected_user_data['email']} | Acesso: {selected_user_data.get('client_access')}")
        
        # Senha (Simulada, apenas para preencher)
        password = st.text_input("Senha", type="password", value="123")
        
        if st.button("Entrar"):
            # Autentica usando o e-mail selecionado
            user = SecurityManager.authenticate(selected_user_data['email'], password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Erro ao autenticar.")

# --- APP PRINCIPAL ---
def main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"## 👤 {user['name']}")
        st.caption(f"Cargo: {user['role']}")
        
        # --- LÓGICA DE CLIENTES ---
        available_clients = user.get("client_access", [])
        
        if not available_clients: 
            available_clients = []
            
        if "*" in available_clients:
            try:
                clients_path = os.path.join("data", "tenants", "agencia_mugo", "clients")
                available_clients = os.listdir(clients_path) if os.path.exists(clients_path) else ["varejo", "moda"]
            except:
                available_clients = ["varejo", "moda"]

        selected_client_id = st.selectbox("Cliente", available_clients)
        
        # Blindagem de tipos
        if isinstance(selected_client_id, list): selected_client_id = selected_client_id[0]
        tenant_id = user.get("tenant_id", "agencia_mugo")
        if isinstance(tenant_id, list): tenant_id = tenant_id[0]

        client_config = SecurityManager.get_client_config(tenant_id, selected_client_id)
        
        st.divider()
        st.metric("Carteira", f"${client_config.get('wallet_balance', 0)}")
        st.caption(f"Voz: {client_config.get('tone_of_voice', 'Padrão')}")
        
        if st.button("Sair"):
            st.session_state.user = None
            st.rerun()

    st.header(f"Painel: {client_config.get('brand_name', selected_client_id)}")
    
    tab1, tab2 = st.tabs(["🚀 Nova Tarefa", "✅ Aprovações"])
    
    # --- ABA 1: FORMULÁRIO (ONDE ESTAVA O ERRO) ---
    with tab1:
        # O 'with st.form' inicia o bloco
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
            
            # Atualizei a lista de entregáveis conforme seu security.py novo
            deliverables = st.multiselect(
                "Entregáveis", 
                ["image_feed", "video_short", "copy_deck", "pack_criativo", "avatar_video", "media_plan", "audio_locucao", "audio_trilha"], 
                ["image_feed"]
            )
            
            desc = st.text_area("Briefing", "Imagem vibrante do produto na praia...")
            
            # --- IMPORTANTE: ESTA LINHA TEM QUE ESTAR INDENTADA DENTRO DO WITH ST.FORM ---
            submitted = st.form_submit_button("Iniciar Job")
            
            if submitted:
                user_ctx = UserContext(
                    user_id=user["id"], email=user["email"], role=user["role"],
                    tenant_id=tenant_id, client_id=selected_client_id
                )
                
                deps = []
                if d_plan: deps.append("planejamento")
                if d_create: deps.append("criacao")
                if d_media: deps.append("midia")
                if d_prod: deps.append("producao")

                req = TaskRequest(
                    campaign_name=campaign, task_name=task_name, description=desc,
                    departments_involved=deps, deliverables=deliverables
                )
                
                st.session_state.current_thread_id = f"job_{int(time.time())}"
                st.session_state.workflow_state = "RUNNING"
                
                initial_state = CampaignState(user=user_ctx, request=req)
                run_graph_step(initial_state, st.session_state.current_thread_id)
                st.rerun()

    # --- ABA 2: APROVAÇÕES ---
    with tab2:
        if st.session_state.workflow_state == "APPROVAL_WAIT":
            st.warning("Aguardando sua aprovação.")
            
            app = build_workflow()
            cfg = {"configurable": {"thread_id": st.session_state.current_thread_id}}
            snapshot = app.get_state(cfg)
            
            vals = snapshot.values
            draft = vals.get("prompt_draft_pt") or vals.get("draft_prompt_pt", "")
            
            edited = st.text_area("Editar Prompt", value=draft, height=150)
            
            if st.button("Aprovar"):
                app.update_state(cfg, {"prompt_draft_pt": edited})
                run_graph_step(None, st.session_state.current_thread_id)
                st.rerun()

        elif st.session_state.workflow_state == "DONE":
            st.success("Job Finalizado.")

if st.session_state.user is None:
    login_screen()
else:
    main_app()
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.core.state import CampaignState

# Importação dos Agentes
from src.agents.governance import guardian_node
from src.agents.orchestrator import router_node
from src.agents.strategy import strategist_node
from src.agents.copywriting import copywriter_node
from src.agents.visual import art_director_node, prompt_drafter_node, prompt_translator_node
from src.tools.production import production_simulation_node

# --- Novo Nó: Brainstorm (Chat Interativo - Pág 8) ---
def brainstorm_node(state: CampaignState):
    """
    Simula o chat 'Brain' onde o criativo conversa com os dados do cliente.
    """
    print("--- [NODE] Brainstorm (Chat) ---")
    # Em produção, aqui chamaria o histórico de chat + RAG do cliente
    return {"brain_history": state.brain_history + ["Brain: Contexto do cliente analisado."]}

# --- Lógica de Decisão ---
def route_manager(state: CampaignState):
    """Decide para onde ir baseado no Router"""
    step = state.next_step
    
    if step == "strategist": return "strategist"
    if step == "copywriter": return "copywriter"
    if step == "art_director": return "art_director"
    if step == "production": return "production"
    if step == "approval_check": return "human_approval" # Vai para Pausa
    return END

def build_workflow():
    workflow = StateGraph(CampaignState)

    # 1. Nós (Atores)
    workflow.add_node("guardian", guardian_node)        # Checa Grana/Permissão
    workflow.add_node("router", router_node)            # Lê Checkboxes
    workflow.add_node("brainstorm", brainstorm_node)    # Chat (Pág 8)
    
    workflow.add_node("strategist", strategist_node)    # Planejamento
    workflow.add_node("copywriter", copywriter_node)    # Redator
    
    # Fluxo Visual (DA)
    workflow.add_node("art_director", art_director_node)
    workflow.add_node("prompt_drafter", prompt_drafter_node)
    workflow.add_node("prompt_translator", prompt_translator_node)
    
    workflow.add_node("production", production_simulation_node)

    # 2. Definição do Fluxo
    workflow.set_entry_point("guardian")
    
    # Se aprovado financeiramente, vai para o Router
    workflow.add_conditional_edges(
        "guardian",
        lambda x: "router" if x.financial_approved else END,
        {"router": "router", END: END}
    )

    # Do Router para os departamentos
    workflow.add_conditional_edges(
        "router",
        route_manager,
        {
            "strategist": "strategist",
            "copywriter": "copywriter",
            "art_director": "art_director",
            "production": "production",
            "human_approval": END # Aqui o grafo para e devolve para UI
        }
    )

    # Retornos para o Router (Loop de verificação)
    workflow.add_edge("strategist", "router")
    workflow.add_edge("copywriter", "router")
    
    # Sub-fluxo Visual
    workflow.add_edge("art_director", "prompt_drafter")
    # Drafter -> Pausa (Edição UI Pág 10) -> Translator
    workflow.add_edge("prompt_drafter", "prompt_translator") 
    workflow.add_edge("prompt_translator", "router") # Volta pro router decidir se produz
    
    workflow.add_edge("production", END)

    memory = MemorySaver()
    
    app = workflow.compile(
        checkpointer=memory,
        # Interrupções para UI (Pausas Humanas)
        interrupt_before=["prompt_translator", "production"]
    )
    
    return app
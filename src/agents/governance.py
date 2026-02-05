from src.core.state import CampaignState
from src.core.financial import FinancialManager
from src.core.security import SecurityManager

def guardian_node(state: CampaignState):
    """
    NÓ 0: Gatekeeper Financeiro e de Segurança.
    Agora lida com múltiplos entregáveis (Lista) em vez de um único tipo.
    """
    print(f"\n🛡️ [GUARDIAN] Analisando acesso de: {state.user.email} ({state.user.role})")
    
    # --- CORREÇÃO DO ERRO ---
    # Acessamos a lista de deliverables diretamente do objeto Pydantic
    deliverables = state.request.deliverables
    
    # Se a lista estiver vazia (apenas brainstorm/chat), definimos um custo base
    if not deliverables:
        deliverables = ["brainstorm"]
        print("   ℹ️ Nenhum entregável físico. Cobrando apenas sessão de Brainstorm.")

    # 1. Calculadora de Custo Total
    total_cost = 0.0
    for item in deliverables:
        cost = FinancialManager.estimate_cost(item)
        total_cost += cost
    
    # 2. Check de Segurança (RBAC) para CADA item pedido
    # Se o usuário pedir Imagem e Video, precisa ter permissão para ambos.
    for item in deliverables:
        if not SecurityManager.can_execute(state.user.role, item):
            print(f"🚫 ACESSO NEGADO. Role '{state.user.role}' não pode executar '{item}'.")
            return {
                "financial_approved": False,
                "kanban_status": "BLOCKED"
            }
    
    # 3. Check Financeiro (Ledger)
    check = FinancialManager.check_funds(state.user.client_id, total_cost)
    
    if not check["allowed"]:
        print(f"💸 FALHA FINANCEIRA: {check['reason']}")
        return {
            "financial_approved": False,
            "kanban_status": "BLOCKED_FUNDS"
        }

    # 4. Efetivar Cobrança (Loop de cobrança item a item)
    for item in deliverables:
        FinancialManager.charge_wallet(state.user.client_id, item, state.user.email)

    # 5. Carregar Contexto do Cliente
    client_conf = SecurityManager.get_client_config(state.user.client_id)
    print(f"✅ APROVADO. Custo Total: ${total_cost}. Cliente: {client_conf['brand_name']}")

    return {
        "financial_approved": True,
        "current_cost": total_cost,
        "client_config": client_conf
    }
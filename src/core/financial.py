from datetime import datetime
from typing import Dict, Optional

# --- 1. Tabela de Preços Atualizada ---
PRICING_TABLE = {
    "brainstorm": 0.50,
    
    # Texto / Planejamento
    "copy_deck": 2.00,          # <--- ADICIONADO (Era copy_simple antes)
    "media_plan": 10.00,        # <--- ADICIONADO
    "planning_monthly": 15.00,

    # Visual
    "image_feed": 0.25,
    "pack_criativo": 6.00,
    
    # Vídeo / Audio
    "video_short": 3.50,
    "avatar_video": 4.00,
    "audio_locucao": 1.00,
    "audio_trilha": 1.20
}

# --- 2. Ledger (Simulação) ---
TENANT_LIMITS = {
    "agencia_mugo": {"total": 1000, "used": 120}, # "Agência Mugô" do PDF
}

CLIENT_WALLETS = {
    "cliente_varejo": {"tenant_id": "agencia_mugo", "limit": 200, "balance": 180.50},
    "cliente_moda":   {"tenant_id": "agencia_mugo", "limit": 300, "balance": 50.00},
}

LEDGER_HISTORY = []

class FinancialManager:
    @staticmethod
    def estimate_cost(product_type: str) -> float:
        return PRICING_TABLE.get(product_type, 0.0)

    @staticmethod
    def check_funds(client_id: str, cost: float) -> Dict:
        wallet = CLIENT_WALLETS.get(client_id)
        if not wallet:
            return {"allowed": False, "reason": "Cliente não encontrado"}
            
        tenant_id = wallet["tenant_id"]
        tenant_stats = TENANT_LIMITS.get(tenant_id)

        if (tenant_stats["used"] + cost) > tenant_stats["total"]:
            return {"allowed": False, "reason": "Limite da Agência excedido."}

        if wallet["balance"] < cost:
            return {"allowed": False, "reason": f"Saldo insuficiente. Necessário: ${cost}"}

        return {"allowed": True}

    @staticmethod
    def charge_wallet(client_id: str, product_type: str, user_email: str):
        cost = FinancialManager.estimate_cost(product_type)
        wallet = CLIENT_WALLETS[client_id]
        tenant = TENANT_LIMITS[wallet["tenant_id"]]
        
        wallet["balance"] -= cost
        tenant["used"] += cost
        
        transaction = {
            "timestamp": datetime.now().isoformat(),
            "client_id": client_id,
            "user": user_email,
            "product": product_type,
            "cost": cost,
            "new_balance": wallet["balance"]
        }
        LEDGER_HISTORY.append(transaction)
        print(f"💰 [FINOPS] Cobrado ${cost} de {client_id}. Novo Saldo: ${wallet['balance']}")
        return transaction
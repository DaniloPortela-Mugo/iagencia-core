import os
from supabase import create_client, Client

class SecurityManager:
    url: str = os.getenv("SUPABASE_URL", "")
    key: str = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY", "")

    db: Client = None

    if url and key:
        try:
            db = create_client(url, key)
            print(f"✅ Supabase conectado.")
        except Exception as e:
            print(f"❌ Erro ao conectar no Supabase: {e}")
            db = None
    else:
        print("❌ ERRO: SUPABASE_URL ou SUPABASE_ANON_KEY não definidos no ambiente.")

    @staticmethod
    def get_client_config(tenant_slug: str, client_slug: str):
        """
        Busca configurações do cliente (saldo, branding, etc)
        """
        if not SecurityManager.db:
            return {
                "tenant": tenant_slug,
                "client": client_slug,
                "wallet_balance": 0.0,
                "brand_name": client_slug.capitalize() + " (Sem Banco)"
            }

        try:
            # Busca tenant
            tenant_res = SecurityManager.db.table("tenants").select("id").eq("slug", tenant_slug).execute()
            if not tenant_res.data:
                return {"error": "Tenant não encontrado"}
            tenant_id = tenant_res.data[0]["id"]

            # Busca cliente
            client_res = SecurityManager.db.table("clients").select("*").eq("slug", client_slug).eq("tenant_id", tenant_id).execute()
            
            if client_res.data:
                client = client_res.data[0]
                return {
                    "tenant": tenant_slug,
                    "client": client["name"],
                    "wallet_balance": client.get("wallet_balance", 0.0),
                    "brand_name": client["name"]
                }
            return {"error": "Cliente não encontrado"}
            
        except Exception as e:
            print(f"Erro ao buscar config: {e}")
            return {"error": "Erro interno"}
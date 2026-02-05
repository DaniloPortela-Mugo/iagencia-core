import os
from supabase import create_client, Client

class SecurityManager:
    # --- CREDENCIAIS HARDCODED (Para destravar o Login) ---
    url: str = "https://tcvqsiwgkazwskdsbgqi.supabase.co"
    
    # COLE SUA CHAVE INTEIRA AQUI DENTRO DAS ASPAS:
    key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRjdnFzaXdna2F6d3NrZHNiZ3FpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjkxMDg1MjUsImV4cCI6MjA4NDY4NDUyNX0.71cU33-Ha7Iz19rQB6UhHSLHawhZ5en7WXWKUI-k988" 
    
    # -----------------------------------------------------

    db: Client = None

    # Tenta conectar com as credenciais acima
    if url and key:
        try:
            db = create_client(url, key)
            print(f"✅ Conexão Direta com Supabase realizada! URL: {url}")
        except Exception as e:
            print(f"❌ Erro ao conectar no Supabase: {e}")
            db = None
    else:
        print("❌ ERRO: URL ou KEY estão vazias no código.")

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
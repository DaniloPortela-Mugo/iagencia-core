-- ============================================================
-- Migração 003: políticas RLS para INSERT/UPDATE/DELETE em briefing_history
-- Execute no SQL Editor do Supabase APÓS a migração 002.
-- ============================================================

-- Permite que usuários autenticados insiram briefings no próprio tenant
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'briefing_history' AND policyname = 'users_insert_own_tenant'
  ) THEN
    CREATE POLICY "users_insert_own_tenant" ON briefing_history
      FOR INSERT TO authenticated
      WITH CHECK (
        tenant_slug IN (
          SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- Permite que usuários autenticados atualizem briefings do próprio tenant
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'briefing_history' AND policyname = 'users_update_own_tenant'
  ) THEN
    CREATE POLICY "users_update_own_tenant" ON briefing_history
      FOR UPDATE TO authenticated
      USING (
        tenant_slug IN (
          SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
        )
      )
      WITH CHECK (
        tenant_slug IN (
          SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- Permite que usuários autenticados deletem briefings do próprio tenant
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'briefing_history' AND policyname = 'users_delete_own_tenant'
  ) THEN
    CREATE POLICY "users_delete_own_tenant" ON briefing_history
      FOR DELETE TO authenticated
      USING (
        tenant_slug IN (
          SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
        )
      );
  END IF;
END $$;

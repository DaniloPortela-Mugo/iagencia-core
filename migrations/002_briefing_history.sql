-- ============================================================
-- Migração 002: histórico de briefings gerados pelo agente
-- Execute no SQL Editor do Supabase.
-- ============================================================

CREATE TABLE IF NOT EXISTS briefing_history (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug  TEXT        NOT NULL,
  task_id      INT,                          -- vínculo opcional com tasks.id
  title        TEXT        NOT NULL,
  client       TEXT,
  created_by   UUID,                         -- profiles.id do autor
  version      INT         NOT NULL DEFAULT 1,
  briefing_data JSONB      NOT NULL,         -- snapshot completo do briefingResult
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_briefing_history_tenant  ON briefing_history (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_briefing_history_task    ON briefing_history (task_id);
CREATE INDEX IF NOT EXISTS idx_briefing_history_created ON briefing_history (created_at DESC);

ALTER TABLE briefing_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON briefing_history FOR ALL TO service_role USING (true);
CREATE POLICY "users_own_tenant" ON briefing_history FOR SELECT TO authenticated
  USING (tenant_slug IN (
    SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
  ));

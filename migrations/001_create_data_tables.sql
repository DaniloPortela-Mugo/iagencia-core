-- ============================================================
-- Migração 001: tabelas persistentes para dados que estavam
-- em memória (TICKETS_DB, ASSETS_DB, APPROVALS_DB)
-- Execute no SQL Editor do Supabase.
-- ============================================================

-- 1. Biblioteca de assets (imagens, vídeos)
CREATE TABLE IF NOT EXISTS library_assets (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug TEXT        NOT NULL,
  title       TEXT        NOT NULL,
  type        TEXT        NOT NULL DEFAULT 'image',
  url         TEXT        NOT NULL,
  client      TEXT,
  campaign    TEXT,
  tags        TEXT[]      DEFAULT '{}',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_library_assets_tenant ON library_assets (tenant_slug);

-- RLS: agência vê todos; usuários comuns veem apenas o seu tenant
ALTER TABLE library_assets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON library_assets FOR ALL TO service_role USING (true);

-- 2. Fila de aprovação de artes
CREATE TABLE IF NOT EXISTS approval_jobs (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug   TEXT        NOT NULL,
  client        TEXT        NOT NULL,
  task_id       INT,
  campaign      TEXT,
  type          TEXT        DEFAULT 'image',
  platform      TEXT,
  title         TEXT        NOT NULL,
  version       TEXT        DEFAULT 'V1',
  date          TEXT,
  content_url   TEXT,
  versions      TEXT[]      DEFAULT ARRAY['V1'],
  status        TEXT        DEFAULT 'pending',
  general_notes JSONB       DEFAULT '[]',
  audit_log     JSONB       DEFAULT '[]',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_jobs_tenant  ON approval_jobs (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_approval_jobs_status  ON approval_jobs (status);

ALTER TABLE approval_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON approval_jobs FOR ALL TO service_role USING (true);

-- 3. Tickets de atendimento
CREATE TABLE IF NOT EXISTS atendimento_tickets (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug TEXT        NOT NULL,
  client      TEXT,
  title       TEXT        NOT NULL,
  status      TEXT        DEFAULT 'todo',
  priority    TEXT        DEFAULT 'normal',
  briefing    TEXT,
  created_at  TEXT                               -- mantido como TEXT para compatibilidade
);

CREATE INDEX IF NOT EXISTS idx_tickets_tenant ON atendimento_tickets (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON atendimento_tickets (status);

ALTER TABLE atendimento_tickets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON atendimento_tickets FOR ALL TO service_role USING (true);

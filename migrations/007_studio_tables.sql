-- ============================================================
-- Migração 007: tabelas dos estúdios de imagem/vídeo
-- Execute no SQL Editor do Supabase.
-- ============================================================

-- 1. Biblioteca de mídia gerada
CREATE TABLE IF NOT EXISTS library (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug  TEXT        NOT NULL,
  url          TEXT        NOT NULL,
  type         TEXT        NOT NULL DEFAULT 'image',
  task_id      INT,
  title        TEXT,
  provider     TEXT        DEFAULT 'internal',
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_library_tenant ON library (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_library_type   ON library (type);
CREATE INDEX IF NOT EXISTS idx_library_task   ON library (task_id);

ALTER TABLE library ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all"       ON library;
DROP POLICY IF EXISTS "users_read_own_tenant"  ON library;
DROP POLICY IF EXISTS "users_write_own_tenant" ON library;
CREATE POLICY "service_role_all"       ON library FOR ALL TO service_role USING (true);
CREATE POLICY "users_read_own_tenant"  ON library FOR SELECT TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));
CREATE POLICY "users_write_own_tenant" ON library FOR ALL TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()))
  WITH CHECK (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));

-- 2. Fila de aprovação
CREATE TABLE IF NOT EXISTS approvals (
  id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug    TEXT        NOT NULL,
  task_id        INT,
  type           TEXT        NOT NULL DEFAULT 'image',
  image_url      TEXT,
  video_url      TEXT,
  status         TEXT        NOT NULL DEFAULT 'pending',
  draft_payload  JSONB,
  general_notes  JSONB       DEFAULT '[]',
  pins           JSONB       DEFAULT '[]',
  metadata       JSONB       DEFAULT '{}',
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approvals_tenant ON approvals (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_approvals_task   ON approvals (task_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status);

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all"       ON approvals;
DROP POLICY IF EXISTS "users_read_own_tenant"  ON approvals;
DROP POLICY IF EXISTS "users_write_own_tenant" ON approvals;
CREATE POLICY "service_role_all"       ON approvals FOR ALL TO service_role USING (true);
CREATE POLICY "users_read_own_tenant"  ON approvals FOR SELECT TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));
CREATE POLICY "users_write_own_tenant" ON approvals FOR ALL TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()))
  WITH CHECK (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));

-- 3. Estado persistente dos estúdios
CREATE TABLE IF NOT EXISTS studio_states (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug  TEXT        NOT NULL,
  task_id      INT         NOT NULL,
  studio_type  TEXT        NOT NULL,
  state        JSONB       DEFAULT '{}',
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID,
  UNIQUE (tenant_slug, task_id, studio_type)
);

CREATE INDEX IF NOT EXISTS idx_studio_states_tenant ON studio_states (tenant_slug);

ALTER TABLE studio_states ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all"   ON studio_states;
DROP POLICY IF EXISTS "users_rw_own_tenant" ON studio_states;
CREATE POLICY "service_role_all"    ON studio_states FOR ALL TO service_role USING (true);
CREATE POLICY "users_rw_own_tenant" ON studio_states FOR ALL TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()))
  WITH CHECK (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));

-- 4. Rascunhos de tasks por departamento
CREATE TABLE IF NOT EXISTS task_drafts (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug  TEXT        NOT NULL,
  task_id      INT         NOT NULL,
  department   TEXT        NOT NULL,
  state        JSONB       DEFAULT '{}',
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  created_by   UUID,
  UNIQUE (tenant_slug, task_id, department)
);

CREATE INDEX IF NOT EXISTS idx_task_drafts_tenant ON task_drafts (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_task_drafts_task   ON task_drafts (task_id);

ALTER TABLE task_drafts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all"    ON task_drafts;
DROP POLICY IF EXISTS "users_rw_own_tenant" ON task_drafts;
CREATE POLICY "service_role_all"    ON task_drafts FOR ALL TO service_role USING (true);
CREATE POLICY "users_rw_own_tenant" ON task_drafts FOR ALL TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()))
  WITH CHECK (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));

-- 5. Rascunhos de arte (StudioEditor)
CREATE TABLE IF NOT EXISTS art_drafts (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id          INT         NOT NULL UNIQUE,
  tenant_slug      TEXT        NOT NULL,
  elements         JSONB       DEFAULT '[]',
  bg_color         TEXT        DEFAULT '#ffffff',
  canvas_format_id TEXT,
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_art_drafts_tenant ON art_drafts (tenant_slug);

ALTER TABLE art_drafts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all"    ON art_drafts;
DROP POLICY IF EXISTS "users_rw_own_tenant" ON art_drafts;
CREATE POLICY "service_role_all"    ON art_drafts FOR ALL TO service_role USING (true);
CREATE POLICY "users_rw_own_tenant" ON art_drafts FOR ALL TO authenticated
  USING (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()))
  WITH CHECK (tenant_slug IN (SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()));

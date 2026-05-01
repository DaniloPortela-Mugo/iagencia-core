-- ============================================================
-- Migração 004: configuração de plataformas de IA por tenant
-- Execute no SQL Editor do Supabase.
-- ============================================================

CREATE TABLE IF NOT EXISTS tenant_platform_configs (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_slug  TEXT        NOT NULL,
  platform_id  TEXT        NOT NULL,        -- ex: "flux", "midjourney", "kling", "veo"
  platform_type TEXT       NOT NULL,        -- "image" | "video"
  is_enabled   BOOLEAN     NOT NULL DEFAULT true,
  api_key_enc  TEXT,                        -- chave criptografada (opcional, para APIs externas)
  custom_endpoint TEXT,                     -- endpoint customizado (override)
  extra_params JSONB       DEFAULT '{}',    -- params extras por plataforma
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (tenant_slug, platform_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_platform_tenant ON tenant_platform_configs (tenant_slug);
CREATE INDEX IF NOT EXISTS idx_tenant_platform_type   ON tenant_platform_configs (platform_type);

ALTER TABLE tenant_platform_configs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON tenant_platform_configs
  FOR ALL TO service_role USING (true);

CREATE POLICY "users_read_own_tenant" ON tenant_platform_configs
  FOR SELECT TO authenticated
  USING (tenant_slug IN (
    SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
  ));

CREATE POLICY "users_write_own_tenant" ON tenant_platform_configs
  FOR ALL TO authenticated
  USING (tenant_slug IN (
    SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
      AND role IN ('admin', 'atendimento')
  ))
  WITH CHECK (tenant_slug IN (
    SELECT tenant_slug FROM user_tenants WHERE user_id = auth.uid()
      AND role IN ('admin', 'atendimento')
  ));

-- Seed padrão: todas as plataformas ativas para todos os tenants existentes
INSERT INTO tenant_platform_configs (tenant_slug, platform_id, platform_type, is_enabled)
SELECT t.slug, p.platform_id, p.platform_type, true
FROM tenants t
CROSS JOIN (VALUES
  ('flux',              'image'),
  ('midjourney',        'image'),
  ('dalle3',            'image'),
  ('gemini_imagen',     'image'),
  ('stable_diffusion',  'image'),
  ('nano_banana',       'image'),
  ('kling',             'video'),
  ('veo',               'video'),
  ('runway',            'video'),
  ('sora',              'video')
) AS p(platform_id, platform_type)
WHERE t.is_active = true
ON CONFLICT (tenant_slug, platform_id) DO NOTHING;

-- ============================================================
-- Migração 005: adiciona coluna config JSONB em tenant_storage_config
-- Execute no SQL Editor do Supabase.
-- ============================================================

ALTER TABLE tenant_storage_config
  ADD COLUMN IF NOT EXISTS config JSONB DEFAULT '{}';

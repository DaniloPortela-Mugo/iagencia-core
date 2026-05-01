-- Migration 008: garante que admins internos têm acesso a todos os tenants
-- Danilo: 36026e4f-d53c-422a-ae79-313f25eda530
-- Julia:  48e96bd4-03b5-488e-91fb-c4e4a27d1d81
-- Kleber: a9c2011e-9d12-4289-9d27-9bf9d5096333
-- Bruno:  85215631-6fa6-497d-b176-c61c4e005b24

DO $$
DECLARE
  admin_ids UUID[] := ARRAY[
    '36026e4f-d53c-422a-ae79-313f25eda530',
    '48e96bd4-03b5-488e-91fb-c4e4a27d1d81',
    'a9c2011e-9d12-4289-9d27-9bf9d5096333',
    '85215631-6fa6-497d-b176-c61c4e005b24'
  ];
  all_modules TEXT[] := ARRAY[
    'dashboard','atendimento','planning','social_media','copy',
    'image_studio','video_studio','production','media','media_offline',
    'library','approvals','cadastro','suppliers'
  ];
  v_slug TEXT;
  admin_id UUID;
BEGIN
  -- Insere/atualiza acesso para todos os tenants existentes
  FOR v_slug IN SELECT slug FROM tenants LOOP
    FOREACH admin_id IN ARRAY admin_ids LOOP
      INSERT INTO user_tenants (user_id, tenant_slug, role, allowed_modules)
      VALUES (admin_id, v_slug, 'admin', all_modules)
      ON CONFLICT (user_id, tenant_slug)
      DO UPDATE SET role = 'admin', allowed_modules = all_modules;
    END LOOP;
  END LOOP;
END;
$$;

-- Trigger: ao criar novo tenant, adiciona os admins internos automaticamente
CREATE OR REPLACE FUNCTION fn_add_internal_admins_to_tenant()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  admin_ids UUID[] := ARRAY[
    '36026e4f-d53c-422a-ae79-313f25eda530',
    '48e96bd4-03b5-488e-91fb-c4e4a27d1d81',
    'a9c2011e-9d12-4289-9d27-9bf9d5096333',
    '85215631-6fa6-497d-b176-c61c4e005b24'
  ];
  all_modules TEXT[] := ARRAY[
    'dashboard','atendimento','planning','social_media','copy',
    'image_studio','video_studio','production','media','media_offline',
    'library','approvals','cadastro','suppliers'
  ];
  admin_id UUID;
BEGIN
  FOREACH admin_id IN ARRAY admin_ids LOOP
    INSERT INTO user_tenants (user_id, tenant_slug, role, allowed_modules)
    VALUES (admin_id, NEW.slug, 'admin', all_modules)
    ON CONFLICT (user_id, tenant_slug)
    DO UPDATE SET role = 'admin', allowed_modules = all_modules;
  END LOOP;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_add_internal_admins ON tenants;
CREATE TRIGGER trg_add_internal_admins
  AFTER INSERT ON tenants
  FOR EACH ROW EXECUTE FUNCTION fn_add_internal_admins_to_tenant();

-- ============================================================
-- Migração 006: políticas RLS para o bucket "library" no Supabase Storage
-- Execute no SQL Editor do Supabase.
-- ============================================================

-- 1. Garante que o bucket "library" existe e é público
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'library',
  'library',
  true,                         -- público: URLs diretas funcionam sem signed URL
  5368709120,                   -- 5 GB (bytes) por arquivo
  ARRAY[
    'image/jpeg','image/png','image/webp','image/gif','image/svg+xml',
    'video/mp4','video/quicktime','video/webm','video/x-m4v',
    'application/pdf','text/plain'
  ]
)
ON CONFLICT (id) DO UPDATE SET
  public           = EXCLUDED.public,
  file_size_limit  = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- 2. Habilita RLS no storage.objects (já está habilitado por padrão no Supabase)
-- ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY; -- só se necessário

-- 3. Políticas de acesso para usuários autenticados

-- INSERT: usuário autenticado pode fazer upload no bucket library
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'library_insert_authenticated'
  ) THEN
    CREATE POLICY "library_insert_authenticated"
      ON storage.objects FOR INSERT TO authenticated
      WITH CHECK (bucket_id = 'library');
  END IF;
END $$;

-- SELECT: usuário autenticado pode listar/ler arquivos do bucket library
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'library_select_authenticated'
  ) THEN
    CREATE POLICY "library_select_authenticated"
      ON storage.objects FOR SELECT TO authenticated
      USING (bucket_id = 'library');
  END IF;
END $$;

-- DELETE: usuário autenticado pode deletar arquivos do bucket library
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'library_delete_authenticated'
  ) THEN
    CREATE POLICY "library_delete_authenticated"
      ON storage.objects FOR DELETE TO authenticated
      USING (bucket_id = 'library');
  END IF;
END $$;

-- UPDATE: usuário autenticado pode atualizar (upsert) arquivos
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'library_update_authenticated'
  ) THEN
    CREATE POLICY "library_update_authenticated"
      ON storage.objects FOR UPDATE TO authenticated
      USING (bucket_id = 'library');
  END IF;
END $$;

-- 4. Acesso público de leitura (para URLs públicas funcionarem sem autenticação)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage' AND tablename = 'objects'
      AND policyname = 'library_select_public'
  ) THEN
    CREATE POLICY "library_select_public"
      ON storage.objects FOR SELECT TO anon
      USING (bucket_id = 'library');
  END IF;
END $$;

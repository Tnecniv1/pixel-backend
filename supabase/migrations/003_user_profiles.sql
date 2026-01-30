-- ============================================
-- MIGRATION: Systeme de Profils avec Photos
-- Date: 2026-01-29
-- Description: Ajoute display_name, avatar_url et configure Storage
-- ============================================

-- ============================================
-- 1. MODIFICATION DE users_map
-- ============================================

-- Ajouter la colonne display_name (pseudo unique)
ALTER TABLE users_map
ADD COLUMN IF NOT EXISTS display_name text UNIQUE;

-- Ajouter la colonne avatar_url
ALTER TABLE users_map
ADD COLUMN IF NOT EXISTS avatar_url text;

-- Index pour recherche rapide par display_name
CREATE INDEX IF NOT EXISTS idx_users_map_display_name
ON users_map (display_name)
WHERE display_name IS NOT NULL;

-- Commentaires
COMMENT ON COLUMN users_map.display_name IS 'Pseudo unique personnalise par l utilisateur';
COMMENT ON COLUMN users_map.avatar_url IS 'URL de l avatar dans Supabase Storage';

-- ============================================
-- 2. POLICY RLS SUR users_map POUR UPDATE
-- ============================================

-- Activer RLS si pas deja fait
ALTER TABLE users_map ENABLE ROW LEVEL SECURITY;

-- Policy SELECT : tout le monde peut lire (pour afficher les profils)
DROP POLICY IF EXISTS "users_map_select_authenticated" ON users_map;
CREATE POLICY "users_map_select_authenticated" ON users_map
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy UPDATE : utilisateur peut modifier son propre profil uniquement
DROP POLICY IF EXISTS "users_map_update_own_profile" ON users_map;
CREATE POLICY "users_map_update_own_profile" ON users_map
    FOR UPDATE
    TO authenticated
    USING (auth_uid = auth.uid())
    WITH CHECK (auth_uid = auth.uid());

-- ============================================
-- 3. CREER LE BUCKET STORAGE "avatars"
-- ============================================

-- Note: La creation de bucket se fait via l'API Storage ou le Dashboard
-- Voici le SQL pour inserer directement dans storage.buckets

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'avatars',
    'avatars',
    true,  -- Public pour lecture
    5242880,  -- 5MB max
    ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']
)
ON CONFLICT (id) DO UPDATE SET
    public = true,
    file_size_limit = 5242880,
    allowed_mime_types = ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

-- ============================================
-- 4. POLICIES STORAGE POUR LE BUCKET "avatars"
-- ============================================

-- Supprimer les anciennes policies si elles existent
DROP POLICY IF EXISTS "avatars_select_public" ON storage.objects;
DROP POLICY IF EXISTS "avatars_insert_own" ON storage.objects;
DROP POLICY IF EXISTS "avatars_update_own" ON storage.objects;
DROP POLICY IF EXISTS "avatars_delete_own" ON storage.objects;

-- Policy SELECT : tout le monde peut lire les avatars (bucket public)
CREATE POLICY "avatars_select_public" ON storage.objects
    FOR SELECT
    TO public
    USING (bucket_id = 'avatars');

-- Policy INSERT : utilisateur peut uploader son propre avatar
-- Le nom du fichier doit commencer par son user_id
CREATE POLICY "avatars_insert_own" ON storage.objects
    FOR INSERT
    TO authenticated
    WITH CHECK (
        bucket_id = 'avatars'
        AND (
            -- Le fichier doit commencer par le user_id de l'utilisateur
            (storage.foldername(name))[1] = (
                SELECT user_id::text
                FROM users_map
                WHERE auth_uid = auth.uid()
            )
            OR
            -- Ou le nom du fichier commence par user_id_
            name ~ ('^' || (
                SELECT user_id::text
                FROM users_map
                WHERE auth_uid = auth.uid()
            ) || '_')
        )
    );

-- Policy UPDATE : utilisateur peut modifier son propre avatar
CREATE POLICY "avatars_update_own" ON storage.objects
    FOR UPDATE
    TO authenticated
    USING (
        bucket_id = 'avatars'
        AND name ~ ('^' || (
            SELECT user_id::text
            FROM users_map
            WHERE auth_uid = auth.uid()
        ) || '_')
    )
    WITH CHECK (
        bucket_id = 'avatars'
        AND name ~ ('^' || (
            SELECT user_id::text
            FROM users_map
            WHERE auth_uid = auth.uid()
        ) || '_')
    );

-- Policy DELETE : utilisateur peut supprimer son propre avatar
CREATE POLICY "avatars_delete_own" ON storage.objects
    FOR DELETE
    TO authenticated
    USING (
        bucket_id = 'avatars'
        AND name ~ ('^' || (
            SELECT user_id::text
            FROM users_map
            WHERE auth_uid = auth.uid()
        ) || '_')
    );

-- ============================================
-- 5. FONCTION HELPER POUR OBTENIR L'URL PUBLIQUE
-- ============================================

-- Cette fonction retourne l'URL publique d'un avatar
CREATE OR REPLACE FUNCTION get_avatar_public_url(file_path text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT
        CASE
            WHEN file_path IS NULL OR file_path = '' THEN NULL
            ELSE concat(
                current_setting('app.settings.supabase_url', true),
                '/storage/v1/object/public/avatars/',
                file_path
            )
        END;
$$;

-- ============================================
-- 6. FONCTION POUR VERIFIER UNICITE DU PSEUDO
-- ============================================

CREATE OR REPLACE FUNCTION check_display_name_available(p_display_name text, p_exclude_user_id int DEFAULT NULL)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Verifier si le display_name est deja pris par un autre utilisateur
    RETURN NOT EXISTS (
        SELECT 1
        FROM users_map
        WHERE LOWER(display_name) = LOWER(p_display_name)
        AND (p_exclude_user_id IS NULL OR user_id != p_exclude_user_id)
    );
END;
$$;

-- Donner acces a la fonction aux utilisateurs authentifies
GRANT EXECUTE ON FUNCTION check_display_name_available TO authenticated;

-- ============================================
-- 7. MISE A JOUR DE LA TABLE messages
-- ============================================

-- Ajouter avatar_url aux messages pour denormalisation (optionnel mais performant)
ALTER TABLE messages
ADD COLUMN IF NOT EXISTS avatar_url text;

COMMENT ON COLUMN messages.avatar_url IS 'URL avatar denormalisee depuis users_map';

-- ============================================
-- FIN DE LA MIGRATION
-- ============================================

-- VERIFICATION :
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'users_map'
-- ORDER BY ordinal_position;

-- VERIFICATION BUCKET :
-- SELECT * FROM storage.buckets WHERE id = 'avatars';

-- VERIFICATION POLICIES :
-- SELECT * FROM pg_policies WHERE tablename = 'objects' AND policyname LIKE 'avatars%';

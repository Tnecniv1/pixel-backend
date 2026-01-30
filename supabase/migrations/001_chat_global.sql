-- ============================================
-- MIGRATION: Chat Global Public
-- Date: 2026-01-29
-- Description: Tables et policies pour le chat global
-- ============================================

-- ============================================
-- 1. MODIFICATION DE users_map
-- ============================================

-- Ajouter la colonne is_admin
ALTER TABLE users_map
ADD COLUMN IF NOT EXISTS is_admin boolean DEFAULT false;

-- ============================================
-- 2. TABLE messages
-- ============================================

CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_id int NOT NULL,
    sender_name text NOT NULL,
    content text NOT NULL CHECK (length(content) > 0 AND length(content) <= 500),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Index pour le tri chronologique (messages les plus recents en premier)
CREATE INDEX IF NOT EXISTS idx_messages_created_at_desc
ON messages (created_at DESC);

-- Index pour filtrer par sender (utile pour la moderation)
CREATE INDEX IF NOT EXISTS idx_messages_sender_id
ON messages (sender_id);

-- ============================================
-- 3. TABLE banned_users
-- ============================================

CREATE TABLE IF NOT EXISTS banned_users (
    user_id int PRIMARY KEY,
    banned_at timestamptz NOT NULL DEFAULT now(),
    reason text
);

-- ============================================
-- 4. ACTIVER RLS
-- ============================================

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE banned_users ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 5. POLICIES RLS - TABLE messages
-- ============================================

-- Policy SELECT: Tout utilisateur authentifie peut lire
DROP POLICY IF EXISTS "messages_select_authenticated" ON messages;
CREATE POLICY "messages_select_authenticated" ON messages
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy INSERT: Peut envoyer si authentifie, sender_id correct, et non banni
DROP POLICY IF EXISTS "messages_insert_if_not_banned" ON messages;
CREATE POLICY "messages_insert_if_not_banned" ON messages
    FOR INSERT
    TO authenticated
    WITH CHECK (
        -- Le sender_id doit correspondre au user_id de l'utilisateur connecte
        sender_id = (
            SELECT user_id
            FROM users_map
            WHERE auth_uid = auth.uid()
        )
        -- Et l'utilisateur ne doit pas etre banni
        AND NOT EXISTS (
            SELECT 1
            FROM banned_users
            WHERE banned_users.user_id = sender_id
        )
    );

-- ============================================
-- 6. POLICIES RLS - TABLE banned_users
-- ============================================

-- Policy SELECT: Tout utilisateur authentifie peut voir qui est banni
-- (permet au frontend de verifier si l'utilisateur courant est banni)
DROP POLICY IF EXISTS "banned_users_select_authenticated" ON banned_users;
CREATE POLICY "banned_users_select_authenticated" ON banned_users
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy INSERT: Seuls les admins peuvent bannir
DROP POLICY IF EXISTS "banned_users_insert_admin_only" ON banned_users;
CREATE POLICY "banned_users_insert_admin_only" ON banned_users
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1
            FROM users_map
            WHERE auth_uid = auth.uid()
            AND is_admin = true
        )
    );

-- Policy DELETE: Seuls les admins peuvent debannir
DROP POLICY IF EXISTS "banned_users_delete_admin_only" ON banned_users;
CREATE POLICY "banned_users_delete_admin_only" ON banned_users
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM users_map
            WHERE auth_uid = auth.uid()
            AND is_admin = true
        )
    );

-- ============================================
-- 7. ACTIVER REALTIME SUR messages
-- ============================================

-- Note: Cette commande doit etre executee separement dans le dashboard Supabase
-- ou via la CLI Supabase. La syntaxe depend de votre version.
--
-- Option A - Via Dashboard:
--   Database > Replication > Ajouter "messages" aux tables repliquees
--
-- Option B - Via SQL (Supabase moderne):
ALTER PUBLICATION supabase_realtime ADD TABLE messages;

-- ============================================
-- 8. COMMENTAIRES SUR LES TABLES
-- ============================================

COMMENT ON TABLE messages IS 'Messages du chat global public';
COMMENT ON COLUMN messages.sender_name IS 'Nom denormalise depuis Users pour eviter les JOINs';

COMMENT ON TABLE banned_users IS 'Utilisateurs bannis du chat';
COMMENT ON COLUMN banned_users.reason IS 'Raison du bannissement (optionnel)';

COMMENT ON COLUMN users_map.is_admin IS 'True si l utilisateur est administrateur du chat';

-- ============================================
-- FIN DE LA MIGRATION
-- ============================================

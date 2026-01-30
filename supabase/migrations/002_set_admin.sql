-- ============================================
-- CONFIGURATION ADMIN
-- A executer APRES 001_chat_global.sql
-- ============================================

-- IMPORTANT: Remplace 'TON_AUTH_UID_ICI' par ton auth_uid Supabase
-- Tu peux le trouver dans:
--   - Supabase Dashboard > Authentication > Users > copier l'UID
--   - Ou dans la table users_map si tu connais ton user_id

-- Option 1: Par auth_uid (recommande)
UPDATE users_map
SET is_admin = true
WHERE auth_uid = 'TON_AUTH_UID_ICI';

-- Option 2: Par user_id si tu le connais
-- UPDATE users_map
-- SET is_admin = true
-- WHERE user_id = 1;  -- Remplace 1 par ton user_id

-- Option 3: Par email (via jointure avec Users)
-- UPDATE users_map
-- SET is_admin = true
-- WHERE user_id = (
--     SELECT id FROM "Users" WHERE email = 'ton.email@example.com'
-- );

-- ============================================
-- VERIFICATION
-- ============================================

-- Verifie que l'admin est bien configure:
SELECT
    um.auth_uid,
    um.user_id,
    um.is_admin,
    u.email,
    u.name
FROM users_map um
JOIN "Users" u ON u.id = um.user_id
WHERE um.is_admin = true;

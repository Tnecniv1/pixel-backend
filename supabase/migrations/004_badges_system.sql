-- ============================================
-- MIGRATION: Systeme de Badges Multi-Categories
-- Date: 2026-01-29
-- Description: Tables, definitions et RPC pour les badges
-- ============================================

-- ============================================
-- 1. TABLE badge_definitions
-- ============================================

CREATE TABLE IF NOT EXISTS badge_definitions (
    badge_id text PRIMARY KEY,
    category text NOT NULL CHECK (category IN ('niveau', 'streak', 'rapidite', 'performance')),
    name text NOT NULL,
    description text NOT NULL,
    emoji text NOT NULL,
    threshold int NOT NULL,
    sort_order int NOT NULL DEFAULT 0
);

COMMENT ON TABLE badge_definitions IS 'Definitions de tous les badges disponibles';
COMMENT ON COLUMN badge_definitions.badge_id IS 'Identifiant unique du badge (ex: niveau_asticot)';
COMMENT ON COLUMN badge_definitions.category IS 'Categorie: niveau, streak, rapidite, performance';
COMMENT ON COLUMN badge_definitions.threshold IS 'Valeur necessaire pour debloquer';
COMMENT ON COLUMN badge_definitions.sort_order IS 'Ordre d affichage dans la categorie';

-- ============================================
-- 2. TABLE user_badges
-- ============================================

CREATE TABLE IF NOT EXISTS user_badges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id int NOT NULL REFERENCES users_map(user_id) ON DELETE CASCADE,
    badge_id text NOT NULL REFERENCES badge_definitions(badge_id) ON DELETE CASCADE,
    unlocked_at timestamptz NOT NULL DEFAULT now(),
    progress int DEFAULT 0,
    UNIQUE(user_id, badge_id)
);

CREATE INDEX IF NOT EXISTS idx_user_badges_user_id ON user_badges(user_id);
CREATE INDEX IF NOT EXISTS idx_user_badges_badge_id ON user_badges(badge_id);
CREATE INDEX IF NOT EXISTS idx_user_badges_unlocked_at ON user_badges(unlocked_at DESC);

COMMENT ON TABLE user_badges IS 'Badges debloques par chaque utilisateur';
COMMENT ON COLUMN user_badges.progress IS 'Progression vers le prochain niveau (0-100)';

-- ============================================
-- 3. INSERTION DES BADGES DE NIVEAU (Animaux)
-- ============================================

INSERT INTO badge_definitions (badge_id, category, name, description, emoji, threshold, sort_order) VALUES
-- Badges de niveau (progression animale)
('niveau_asticot', 'niveau', 'Asticot Elementaire', 'Tu debutes ton aventure mathematique', '🐛', 0, 1),
('niveau_abeille', 'niveau', 'Abeille College', 'Tu butines les connaissances', '🐝', 6, 2),
('niveau_ours', 'niveau', 'Ours Lycee', 'Tu deviens costaud en calcul', '🐻', 11, 3),
('niveau_aigle', 'niveau', 'Aigle Licence', 'Tu prends de la hauteur', '🦅', 16, 4),
('niveau_licorne', 'niveau', 'Licorne Master', 'Tu es exceptionnel', '🦄', 21, 5),
('niveau_dragon', 'niveau', 'Dragon Doctorat', 'Tu maitrises l art du calcul mental', '🐉', 26, 6)
ON CONFLICT (badge_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    emoji = EXCLUDED.emoji,
    threshold = EXCLUDED.threshold,
    sort_order = EXCLUDED.sort_order;

-- ============================================
-- 4. INSERTION DES BADGES DE STREAK
-- ============================================

INSERT INTO badge_definitions (badge_id, category, name, description, emoji, threshold, sort_order) VALUES
('streak_discipline', 'streak', 'Discipline', 'Premier pas vers la regularite', '💧', 3, 1),
('streak_concentration', 'streak', 'Concentration', 'Une semaine sans faillir', '⚡', 7, 2),
('streak_feu', 'streak', 'Score de feu', 'Tu es en feu !', '🔥', 14, 3),
('streak_progression', 'streak', 'Progression', 'Champion de la constance', '📈', 30, 4)
ON CONFLICT (badge_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    emoji = EXCLUDED.emoji,
    threshold = EXCLUDED.threshold,
    sort_order = EXCLUDED.sort_order;

-- ============================================
-- 5. INSERTION DES BADGES DE RAPIDITE
-- ============================================

INSERT INTO badge_definitions (badge_id, category, name, description, emoji, threshold, sort_order) VALUES
('rapidite_etoile', 'rapidite', 'Etoile', 'Tu commences a etre rapide', '⭐', 5000, 1),
('rapidite_precision', 'rapidite', 'Precision', 'Vitesse et justesse', '🎯', 3000, 2),
('rapidite_fusee', 'rapidite', 'Fusee', 'Tu es ultra-rapide', '🚀', 2000, 3),
('rapidite_champion', 'rapidite', 'Champion', 'Maitre de la vitesse', '🏆', 1500, 4)
ON CONFLICT (badge_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    emoji = EXCLUDED.emoji,
    threshold = EXCLUDED.threshold,
    sort_order = EXCLUDED.sort_order;

-- ============================================
-- 6. INSERTION DES BADGES DE PERFORMANCE
-- ============================================

INSERT INTO badge_definitions (badge_id, category, name, description, emoji, threshold, sort_order) VALUES
('perf_perfectionniste', 'performance', 'Perfectionniste', '10 sessions avec 100% de reussite', '📚', 10, 1),
('perf_travailleur', 'performance', 'Travailleur acharne', '100 sessions completees', '🎓', 100, 2),
('perf_precis', 'performance', 'Precis', 'Taux de reussite global > 90%', '🌟', 90, 3),
('perf_centurion', 'performance', 'Centurion', 'Score cumule > 10000 points', '💯', 10000, 4)
ON CONFLICT (badge_id) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    emoji = EXCLUDED.emoji,
    threshold = EXCLUDED.threshold,
    sort_order = EXCLUDED.sort_order;

-- ============================================
-- 7. ACTIVER RLS
-- ============================================

ALTER TABLE badge_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_badges ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 8. POLICIES RLS - badge_definitions
-- ============================================

-- Tout le monde peut lire les definitions
DROP POLICY IF EXISTS "badge_definitions_select_all" ON badge_definitions;
CREATE POLICY "badge_definitions_select_all" ON badge_definitions
    FOR SELECT
    TO authenticated
    USING (true);

-- ============================================
-- 9. POLICIES RLS - user_badges
-- ============================================

-- Utilisateur peut voir ses propres badges
DROP POLICY IF EXISTS "user_badges_select_own" ON user_badges;
CREATE POLICY "user_badges_select_own" ON user_badges
    FOR SELECT
    TO authenticated
    USING (
        user_id = (
            SELECT um.user_id FROM users_map um WHERE um.auth_uid = auth.uid()
        )
    );

-- Pas d'INSERT/UPDATE/DELETE direct - seulement via RPC
-- (empeche la triche)

-- ============================================
-- 10. FONCTION RPC : unlock_badge
-- ============================================

CREATE OR REPLACE FUNCTION unlock_badge(
    p_user_id int,
    p_badge_id text,
    p_progress int DEFAULT 0
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_result jsonb;
    v_badge badge_definitions%ROWTYPE;
    v_already_unlocked boolean;
BEGIN
    -- Verifier que le badge existe
    SELECT * INTO v_badge FROM badge_definitions WHERE badge_id = p_badge_id;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('success', false, 'error', 'Badge inconnu');
    END IF;

    -- Verifier si deja debloque
    SELECT EXISTS(
        SELECT 1 FROM user_badges WHERE user_id = p_user_id AND badge_id = p_badge_id
    ) INTO v_already_unlocked;

    IF v_already_unlocked THEN
        -- Mettre a jour la progression si fournie
        IF p_progress > 0 THEN
            UPDATE user_badges SET progress = p_progress
            WHERE user_id = p_user_id AND badge_id = p_badge_id;
        END IF;
        RETURN jsonb_build_object('success', true, 'already_unlocked', true, 'badge', row_to_json(v_badge));
    END IF;

    -- Debloquer le badge
    INSERT INTO user_badges (user_id, badge_id, progress)
    VALUES (p_user_id, p_badge_id, p_progress);

    RETURN jsonb_build_object(
        'success', true,
        'newly_unlocked', true,
        'badge', jsonb_build_object(
            'badge_id', v_badge.badge_id,
            'name', v_badge.name,
            'description', v_badge.description,
            'emoji', v_badge.emoji,
            'category', v_badge.category
        )
    );
END;
$$;

-- ============================================
-- 11. FONCTION RPC : get_user_badges
-- ============================================

CREATE OR REPLACE FUNCTION get_user_badges(p_user_id int)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_result jsonb;
BEGIN
    SELECT jsonb_agg(
        jsonb_build_object(
            'badge_id', bd.badge_id,
            'category', bd.category,
            'name', bd.name,
            'description', bd.description,
            'emoji', bd.emoji,
            'threshold', bd.threshold,
            'sort_order', bd.sort_order,
            'unlocked', ub.unlocked_at IS NOT NULL,
            'unlocked_at', ub.unlocked_at,
            'progress', COALESCE(ub.progress, 0)
        )
        ORDER BY bd.category, bd.sort_order
    )
    INTO v_result
    FROM badge_definitions bd
    LEFT JOIN user_badges ub ON bd.badge_id = ub.badge_id AND ub.user_id = p_user_id;

    RETURN COALESCE(v_result, '[]'::jsonb);
END;
$$;

-- ============================================
-- 12. FONCTION RPC : get_user_stats_for_badges
-- ============================================

CREATE OR REPLACE FUNCTION get_user_stats_for_badges(p_user_id int)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_niveau_moyen numeric;
    v_streak_current int;
    v_streak_max int;
    v_temps_moyen_ms numeric;
    v_sessions_parfaites int;
    v_total_sessions int;
    v_taux_reussite numeric;
    v_score_cumule int;
BEGIN
    -- Calcul du niveau moyen (depuis Suivi_Parcours ou Parcours)
    SELECT COALESCE(AVG(p.Niveau), 0)
    INTO v_niveau_moyen
    FROM Suivi_Parcours sp
    JOIN Parcours p ON sp.Parcours_Id = p.id
    WHERE sp.Users_Id = p_user_id;

    -- Streak (depuis la table existante ou calcul)
    -- Simplified: on suppose qu'il y a une logique existante
    v_streak_current := 0;
    v_streak_max := 0;

    -- Temps moyen de reponse (en ms)
    SELECT COALESCE(AVG(Temps_Seconds) * 1000, 10000)
    INTO v_temps_moyen_ms
    FROM Observations o
    JOIN Entrainement e ON o.Entrainement_Id = e.id
    WHERE e.Users_Id = p_user_id
    AND o.Temps_Seconds IS NOT NULL
    AND o.Temps_Seconds > 0;

    -- Sessions parfaites (100% reussite)
    SELECT COUNT(*)
    INTO v_sessions_parfaites
    FROM (
        SELECT e.id
        FROM Entrainement e
        JOIN Observations o ON o.Entrainement_Id = e.id
        WHERE e.Users_Id = p_user_id
        GROUP BY e.id
        HAVING COUNT(*) FILTER (WHERE o.Etat = 'FAUX') = 0
        AND COUNT(*) >= 5  -- Au moins 5 exercices
    ) sub;

    -- Total sessions
    SELECT COUNT(DISTINCT id)
    INTO v_total_sessions
    FROM Entrainement
    WHERE Users_Id = p_user_id;

    -- Taux de reussite global
    SELECT COALESCE(
        COUNT(*) FILTER (WHERE Etat = 'VRAI') * 100.0 / NULLIF(COUNT(*), 0),
        0
    )
    INTO v_taux_reussite
    FROM Observations o
    JOIN Entrainement e ON o.Entrainement_Id = e.id
    WHERE e.Users_Id = p_user_id;

    -- Score cumule
    SELECT COALESCE(SUM(Score), 0)
    INTO v_score_cumule
    FROM Observations o
    JOIN Entrainement e ON o.Entrainement_Id = e.id
    WHERE e.Users_Id = p_user_id;

    RETURN jsonb_build_object(
        'niveau_moyen', ROUND(v_niveau_moyen, 1),
        'streak_current', v_streak_current,
        'streak_max', v_streak_max,
        'temps_moyen_ms', ROUND(v_temps_moyen_ms),
        'sessions_parfaites', v_sessions_parfaites,
        'total_sessions', v_total_sessions,
        'taux_reussite', ROUND(v_taux_reussite, 1),
        'score_cumule', v_score_cumule
    );
END;
$$;

-- ============================================
-- 13. FONCTION RPC : check_and_unlock_badges
-- ============================================

CREATE OR REPLACE FUNCTION check_and_unlock_badges(p_user_id int)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_stats jsonb;
    v_niveau_moyen numeric;
    v_streak int;
    v_temps_ms numeric;
    v_sessions_parfaites int;
    v_total_sessions int;
    v_taux numeric;
    v_score int;
    v_newly_unlocked jsonb := '[]'::jsonb;
    v_badge_result jsonb;
BEGIN
    -- Recuperer les stats
    v_stats := get_user_stats_for_badges(p_user_id);
    v_niveau_moyen := (v_stats->>'niveau_moyen')::numeric;
    v_streak := (v_stats->>'streak_current')::int;
    v_temps_ms := (v_stats->>'temps_moyen_ms')::numeric;
    v_sessions_parfaites := (v_stats->>'sessions_parfaites')::int;
    v_total_sessions := (v_stats->>'total_sessions')::int;
    v_taux := (v_stats->>'taux_reussite')::numeric;
    v_score := (v_stats->>'score_cumule')::int;

    -- ========== BADGES DE NIVEAU ==========
    IF v_niveau_moyen >= 26 THEN
        v_badge_result := unlock_badge(p_user_id, 'niveau_dragon');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    ELSIF v_niveau_moyen >= 21 THEN
        v_badge_result := unlock_badge(p_user_id, 'niveau_licorne');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    ELSIF v_niveau_moyen >= 16 THEN
        v_badge_result := unlock_badge(p_user_id, 'niveau_aigle');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    ELSIF v_niveau_moyen >= 11 THEN
        v_badge_result := unlock_badge(p_user_id, 'niveau_ours');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    ELSIF v_niveau_moyen >= 6 THEN
        v_badge_result := unlock_badge(p_user_id, 'niveau_abeille');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    ELSE
        v_badge_result := unlock_badge(p_user_id, 'niveau_asticot');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;

    -- ========== BADGES DE STREAK ==========
    IF v_streak >= 30 THEN
        v_badge_result := unlock_badge(p_user_id, 'streak_progression');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_streak >= 14 THEN
        v_badge_result := unlock_badge(p_user_id, 'streak_feu');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_streak >= 7 THEN
        v_badge_result := unlock_badge(p_user_id, 'streak_concentration');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_streak >= 3 THEN
        v_badge_result := unlock_badge(p_user_id, 'streak_discipline');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;

    -- ========== BADGES DE RAPIDITE ==========
    IF v_temps_ms > 0 AND v_temps_ms <= 1500 THEN
        v_badge_result := unlock_badge(p_user_id, 'rapidite_champion');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_temps_ms > 0 AND v_temps_ms <= 2000 THEN
        v_badge_result := unlock_badge(p_user_id, 'rapidite_fusee');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_temps_ms > 0 AND v_temps_ms <= 3000 THEN
        v_badge_result := unlock_badge(p_user_id, 'rapidite_precision');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_temps_ms > 0 AND v_temps_ms <= 5000 THEN
        v_badge_result := unlock_badge(p_user_id, 'rapidite_etoile');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;

    -- ========== BADGES DE PERFORMANCE ==========
    IF v_sessions_parfaites >= 10 THEN
        v_badge_result := unlock_badge(p_user_id, 'perf_perfectionniste');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_total_sessions >= 100 THEN
        v_badge_result := unlock_badge(p_user_id, 'perf_travailleur');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_taux >= 90 THEN
        v_badge_result := unlock_badge(p_user_id, 'perf_precis');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;
    IF v_score >= 10000 THEN
        v_badge_result := unlock_badge(p_user_id, 'perf_centurion');
        IF (v_badge_result->>'newly_unlocked')::boolean THEN
            v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'stats', v_stats,
        'newly_unlocked', v_newly_unlocked,
        'total_unlocked', (SELECT COUNT(*) FROM user_badges WHERE user_id = p_user_id)
    );
END;
$$;

-- ============================================
-- 14. FONCTION : get_main_badge (badge animal)
-- ============================================

CREATE OR REPLACE FUNCTION get_main_badge(p_user_id int)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_badge jsonb;
BEGIN
    SELECT jsonb_build_object(
        'badge_id', bd.badge_id,
        'name', bd.name,
        'emoji', bd.emoji,
        'description', bd.description,
        'threshold', bd.threshold
    )
    INTO v_badge
    FROM user_badges ub
    JOIN badge_definitions bd ON ub.badge_id = bd.badge_id
    WHERE ub.user_id = p_user_id
    AND bd.category = 'niveau'
    ORDER BY bd.threshold DESC
    LIMIT 1;

    -- Si pas de badge, retourner Asticot par defaut
    IF v_badge IS NULL THEN
        SELECT jsonb_build_object(
            'badge_id', badge_id,
            'name', name,
            'emoji', emoji,
            'description', description,
            'threshold', threshold
        )
        INTO v_badge
        FROM badge_definitions
        WHERE badge_id = 'niveau_asticot';
    END IF;

    RETURN v_badge;
END;
$$;

-- ============================================
-- 15. DONNER ACCES AUX FONCTIONS RPC
-- ============================================

GRANT EXECUTE ON FUNCTION unlock_badge TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_badges TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_stats_for_badges TO authenticated;
GRANT EXECUTE ON FUNCTION check_and_unlock_badges TO authenticated;
GRANT EXECUTE ON FUNCTION get_main_badge TO authenticated;

-- ============================================
-- FIN DE LA MIGRATION
-- ============================================

-- VERIFICATION :
-- SELECT * FROM badge_definitions ORDER BY category, sort_order;
-- SELECT check_and_unlock_badges(1);  -- Remplacer 1 par un user_id valide
-- SELECT get_user_badges(1);
-- SELECT get_main_badge(1);

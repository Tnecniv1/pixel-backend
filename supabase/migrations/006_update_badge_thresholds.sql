-- ============================================
-- MIGRATION: Mise à jour des seuils de badges de niveau
-- Date: 2026-01-29
-- Description:
--   1. Nouveaux seuils adaptés aux 92 niveaux du parcours
--   2. Calcul du niveau moyen basé sur les vrais niveaux Parcours
--   3. Possibilité de retirer un badge si critère non rempli
-- ============================================

-- ============================================
-- 1. MISE À JOUR DES SEUILS DE BADGES DE NIVEAU
-- ============================================

-- Asticot: niveau 0 (débutant)
UPDATE badge_definitions
SET threshold = 0, description = 'Tu debutes ton aventure mathematique (niveau 0+)'
WHERE badge_id = 'niveau_asticot';

-- Abeille: niveau 10 (bases acquises, opérations simples)
UPDATE badge_definitions
SET threshold = 10, description = 'Tu maitrises les bases du calcul (niveau 10+)'
WHERE badge_id = 'niveau_abeille';

-- Ours: niveau 25 (intermédiaire, nombres à 2-3 chiffres)
UPDATE badge_definitions
SET threshold = 25, description = 'Tu es solide en calcul mental (niveau 25+)'
WHERE badge_id = 'niveau_ours';

-- Aigle: niveau 45 (avancé, grands nombres)
UPDATE badge_definitions
SET threshold = 45, description = 'Tu domines les grands nombres (niveau 45+)'
WHERE badge_id = 'niveau_aigle';

-- Licorne: niveau 65 (expert)
UPDATE badge_definitions
SET threshold = 65, description = 'Tu es un expert du calcul mental (niveau 65+)'
WHERE badge_id = 'niveau_licorne';

-- Dragon: niveau 85 (maître absolu)
UPDATE badge_definitions
SET threshold = 85, description = 'Tu as atteint la maitrise supreme (niveau 85+)'
WHERE badge_id = 'niveau_dragon';

-- ============================================
-- 2. MISE À JOUR DE get_user_stats_for_badges
--    Calcul du niveau moyen basé sur les vrais niveaux Parcours
-- ============================================

DROP FUNCTION IF EXISTS get_user_stats_for_badges(int);

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
    -- Calcul du niveau moyen RÉEL basé sur les niveaux du Parcours
    -- On prend la moyenne des niveaux des exercices réussis
    SELECT COALESCE(
        (SELECT ROUND(AVG(p."Niveau"), 1)
         FROM "Observations" o
         JOIN "Entrainement" e ON o."Entrainement_Id" = e.id
         JOIN "Parcours" p ON o."Parcours_Id" = p.id
         WHERE e."Users_Id" = p_user_id
         AND o."Etat" = 'VRAI'
        ), 0)
    INTO v_niveau_moyen;

    -- Streak actuel: jours consécutifs jusqu'à aujourd'hui
    WITH dates AS (
        SELECT DISTINCT DATE("Date" AT TIME ZONE 'Europe/Paris') as d
        FROM "Entrainement"
        WHERE "Users_Id" = p_user_id
        AND "Date" IS NOT NULL
        ORDER BY d DESC
    ),
    numbered AS (
        SELECT d, ROW_NUMBER() OVER (ORDER BY d DESC) as rn
        FROM dates
    )
    SELECT COALESCE(
        (SELECT COUNT(*)::int
         FROM numbered
         WHERE d = CURRENT_DATE - (rn - 1)::int
        ), 0)
    INTO v_streak_current;

    -- Streak max: plus longue série de jours consécutifs
    WITH dates AS (
        SELECT DISTINCT DATE("Date" AT TIME ZONE 'Europe/Paris') as d
        FROM "Entrainement"
        WHERE "Users_Id" = p_user_id
        AND "Date" IS NOT NULL
        ORDER BY d
    ),
    with_prev AS (
        SELECT d,
               LAG(d) OVER (ORDER BY d) as prev_d
        FROM dates
    ),
    streaks AS (
        SELECT d,
               CASE WHEN prev_d IS NULL OR d - prev_d > 1 THEN 1 ELSE 0 END as new_streak
        FROM with_prev
    ),
    streak_groups AS (
        SELECT d, SUM(new_streak) OVER (ORDER BY d) as grp
        FROM streaks
    )
    SELECT COALESCE(MAX(cnt), 0)
    INTO v_streak_max
    FROM (
        SELECT COUNT(*)::int as cnt
        FROM streak_groups
        GROUP BY grp
    ) sub;

    -- Temps moyen de réponse (en ms)
    SELECT COALESCE(AVG("Temps_Seconds") * 1000, 10000)
    INTO v_temps_moyen_ms
    FROM "Observations" o
    JOIN "Entrainement" e ON o."Entrainement_Id" = e.id
    WHERE e."Users_Id" = p_user_id
    AND o."Temps_Seconds" IS NOT NULL
    AND o."Temps_Seconds" > 0;

    -- Sessions parfaites (100% réussite, au moins 5 exercices)
    SELECT COUNT(*)
    INTO v_sessions_parfaites
    FROM (
        SELECT e.id
        FROM "Entrainement" e
        JOIN "Observations" o ON o."Entrainement_Id" = e.id
        WHERE e."Users_Id" = p_user_id
        GROUP BY e.id
        HAVING COUNT(*) FILTER (WHERE o."Etat" = 'FAUX') = 0
        AND COUNT(*) >= 5
    ) sub;

    -- Total sessions
    SELECT COUNT(DISTINCT id)
    INTO v_total_sessions
    FROM "Entrainement"
    WHERE "Users_Id" = p_user_id;

    -- Taux de réussite global (%)
    SELECT COALESCE(
        COUNT(*) FILTER (WHERE "Etat" = 'VRAI') * 100.0 / NULLIF(COUNT(*), 0),
        0
    )
    INTO v_taux_reussite
    FROM "Observations" o
    JOIN "Entrainement" e ON o."Entrainement_Id" = e.id
    WHERE e."Users_Id" = p_user_id;

    -- Score cumulé total
    SELECT COALESCE(SUM("Score"), 0)
    INTO v_score_cumule
    FROM "Observations" o
    JOIN "Entrainement" e ON o."Entrainement_Id" = e.id
    WHERE e."Users_Id" = p_user_id;

    RETURN jsonb_build_object(
        'niveau_moyen', COALESCE(v_niveau_moyen, 0),
        'streak_current', COALESCE(v_streak_current, 0),
        'streak_max', COALESCE(v_streak_max, 0),
        'temps_moyen_ms', ROUND(COALESCE(v_temps_moyen_ms, 10000)),
        'sessions_parfaites', COALESCE(v_sessions_parfaites, 0),
        'total_sessions', COALESCE(v_total_sessions, 0),
        'taux_reussite', ROUND(COALESCE(v_taux_reussite, 0), 1),
        'score_cumule', COALESCE(v_score_cumule, 0)
    );
END;
$$;

-- ============================================
-- 3. MISE À JOUR DE check_and_unlock_badges
--    Avec gestion du retrait des badges de niveau
-- ============================================

DROP FUNCTION IF EXISTS check_and_unlock_badges(int);

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
    v_correct_niveau_badge text;
BEGIN
    -- Récupérer les stats
    v_stats := get_user_stats_for_badges(p_user_id);
    v_niveau_moyen := (v_stats->>'niveau_moyen')::numeric;
    v_streak := (v_stats->>'streak_current')::int;
    v_temps_ms := (v_stats->>'temps_moyen_ms')::numeric;
    v_sessions_parfaites := (v_stats->>'sessions_parfaites')::int;
    v_total_sessions := (v_stats->>'total_sessions')::int;
    v_taux := (v_stats->>'taux_reussite')::numeric;
    v_score := (v_stats->>'score_cumule')::int;

    -- ========== BADGES DE NIVEAU (avec retrait possible) ==========
    -- Déterminer le badge de niveau correct
    IF v_niveau_moyen >= 85 THEN
        v_correct_niveau_badge := 'niveau_dragon';
    ELSIF v_niveau_moyen >= 65 THEN
        v_correct_niveau_badge := 'niveau_licorne';
    ELSIF v_niveau_moyen >= 45 THEN
        v_correct_niveau_badge := 'niveau_aigle';
    ELSIF v_niveau_moyen >= 25 THEN
        v_correct_niveau_badge := 'niveau_ours';
    ELSIF v_niveau_moyen >= 10 THEN
        v_correct_niveau_badge := 'niveau_abeille';
    ELSE
        v_correct_niveau_badge := 'niveau_asticot';
    END IF;

    -- Supprimer tous les badges de niveau existants
    DELETE FROM user_badges
    WHERE user_id = p_user_id
    AND badge_id IN ('niveau_asticot', 'niveau_abeille', 'niveau_ours', 'niveau_aigle', 'niveau_licorne', 'niveau_dragon');

    -- Attribuer le badge correct
    v_badge_result := unlock_badge(p_user_id, v_correct_niveau_badge);
    IF (v_badge_result->>'newly_unlocked')::boolean THEN
        v_newly_unlocked := v_newly_unlocked || v_badge_result->'badge';
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

    -- ========== BADGES DE RAPIDITÉ ==========
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
-- 4. PERMISSIONS
-- ============================================

GRANT EXECUTE ON FUNCTION get_user_stats_for_badges TO authenticated;
GRANT EXECUTE ON FUNCTION check_and_unlock_badges TO authenticated;

-- ============================================
-- FIN DE LA MIGRATION
-- ============================================

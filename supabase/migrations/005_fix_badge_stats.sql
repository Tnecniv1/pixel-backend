-- ============================================
-- MIGRATION: Fix get_user_stats_for_badges
-- Date: 2026-01-29
-- Description: Corrige la fonction qui référençait Suivi_Parcours (inexistant)
-- IMPORTANT: Utilise "Date" au lieu de created_at pour Entrainement
-- ============================================

-- Supprimer l'ancienne fonction
DROP FUNCTION IF EXISTS get_user_stats_for_badges(int);

-- Recréer la fonction avec les bons noms de tables/colonnes
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
    -- Calcul du niveau moyen basé sur le score moyen par session
    SELECT COALESCE(
        LEAST(30, GREATEST(0,
            (SELECT AVG(session_score) FROM (
                SELECT SUM(CASE WHEN o."Etat" = 'VRAI' THEN 1 ELSE 0 END) as session_score
                FROM "Entrainement" e
                JOIN "Observations" o ON o."Entrainement_Id" = e.id
                WHERE e."Users_Id" = p_user_id
                GROUP BY e.id
                HAVING COUNT(*) >= 5
            ) sub) / 2
        )), 0)
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
        'niveau_moyen', ROUND(COALESCE(v_niveau_moyen, 0), 1),
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

-- Redonner les permissions
GRANT EXECUTE ON FUNCTION get_user_stats_for_badges TO authenticated;

-- ============================================
-- FIN DE LA MIGRATION
-- ============================================

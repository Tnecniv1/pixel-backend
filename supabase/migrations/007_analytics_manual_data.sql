-- ============================================
-- MIGRATION: Table analytics_manual_data
-- Date: 2026-02-13
-- Description: Stockage des données manuelles (impressions/downloads)
--              pour le funnel de conversion du dashboard admin
-- ============================================

CREATE TABLE IF NOT EXISTS analytics_manual_data (
    date DATE PRIMARY KEY,
    impressions INT NOT NULL DEFAULT 0,
    downloads INT NOT NULL DEFAULT 0
);

-- Pas de RLS : accessible uniquement via service_client (service role key)
-- Les endpoints admin.py vérifient is_admin côté application

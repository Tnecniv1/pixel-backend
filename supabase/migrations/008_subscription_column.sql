-- ============================================
-- MIGRATION: Colonne is_subscribed pour suivi abonnements
-- Date: 2026-02-16
-- Description: Ajoute is_subscribed dans users_map, synchronisé via webhook RevenueCat
-- ============================================

ALTER TABLE users_map
ADD COLUMN IF NOT EXISTS is_subscribed boolean DEFAULT false;

COMMENT ON COLUMN users_map.is_subscribed IS 'Statut abonnement synchronisé depuis RevenueCat';

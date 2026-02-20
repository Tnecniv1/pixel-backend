-- MIGRATION 009 : Nouveau système de scoring
-- Toutes les modifications sont ADDITIVES (aucune colonne existante modifiée)

-- Nouvelles colonnes dans Observations (Score existe déjà comme score de base)
ALTER TABLE "Observations"
ADD COLUMN IF NOT EXISTS bonus_vitesse FLOAT,
ADD COLUMN IF NOT EXISTS bonus_marge FLOAT,
ADD COLUMN IF NOT EXISTS score_global INTEGER;

-- Nouvelles colonnes dans users_map
ALTER TABLE users_map
ADD COLUMN IF NOT EXISTS last_training_date DATE,
ADD COLUMN IF NOT EXISTS score_total INTEGER DEFAULT 0;

// src/config.ts
import Constants from "expo-constants";

// ——— Debug (tu peux enlever quand tout est OK)
console.log("[config] mark = v3-API_URL-alias");

// Récupère les extra définis dans app.json / app.config
const extra: any =
  (Constants?.expoConfig?.extra as any) ??
  (Constants as any)?.manifest2?.extra ??
  (Constants as any)?.manifest?.extra ??
  {};

// Candidats possibles à l’URL d’API (ordre de priorité)
const candidates = {
  API_BASE_URL: extra?.API_BASE_URL,
  API_BASE: extra?.API_BASE,
  EXPO_PUBLIC_API_BASE_URL: process.env.EXPO_PUBLIC_API_BASE_URL,
};

// ⚠️ Mets ici TON IP locale en dernier recours (pour tests sur appareil physique)
const FALLBACK = "http://192.168.1.16:8000";

// Choix final (priorité : extra.API_BASE_URL → extra.API_BASE → env → fallback)
const pick =
  candidates.API_BASE_URL ||
  candidates.API_BASE ||
  candidates.EXPO_PUBLIC_API_BASE_URL ||
  FALLBACK;

// ——— Exports compatibles partout
export const API_BASE: string = pick;   // gardé pour compat ascendante
export const API_URL: string = API_BASE; // alias officiel utilisé par les appels

// Export par défaut (facilite d’autres styles d’import)
const cfg = { API_BASE, API_URL };
export default cfg;

// ——— Logs de contrôle (tu peux commenter après vérif)
console.log("[config] API_BASE =", API_BASE);
console.log("[config] API_URL  =", API_URL);
console.log("[config] extra keys =", Object.keys(extra || {}));

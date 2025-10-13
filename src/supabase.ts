// supabase.ts
import { createClient, SupabaseClient } from "@supabase/supabase-js";
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

// 1) Lit d'abord les variables d'env (EXPO_PUBLIC_*), puis fallback sur expo.extra
const SUPABASE_URL =
  process.env.EXPO_PUBLIC_SUPABASE_URL ||
  (Constants.expoConfig?.extra as any)?.SUPABASE_URL ||
  (Constants.manifestExtra as any)?.SUPABASE_URL;

const SUPABASE_ANON_KEY =
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ||
  (Constants.expoConfig?.extra as any)?.SUPABASE_ANON_KEY ||
  (Constants.manifestExtra as any)?.SUPABASE_ANON_KEY;

// 2) Crée un singleton (utile en dev hot-reload)
declare global {
  // eslint-disable-next-line no-var
  var __supabase__: SupabaseClient | undefined;
}

if (!global.__supabase__) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    console.warn(
      "[supabase] Missing SUPABASE_URL / SUPABASE_ANON_KEY. " +
        "Configure EXPO_PUBLIC_* env vars ou expo.extra."
    );
  }

  global.__supabase__ = createClient(SUPABASE_URL ?? "", SUPABASE_ANON_KEY ?? "", {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      storage: AsyncStorage, // indispensable en React Native
      detectSessionInUrl: false, // RN : pas d’URL callback
    },
  });
}

// 3) Exporte le client unique
export const supabase = global.__supabase__!;
export default supabase;

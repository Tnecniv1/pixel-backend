// src/supabase.ts
import { createClient } from "@supabase/supabase-js";
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

// Expo peut exposer extra différemment selon le contexte/canal → on tente plusieurs emplacements
const extra =
  (Constants?.expoConfig?.extra as any) ??
  (Constants?.manifest2 as any)?.extra ??
  (Constants?.manifest as any)?.extra ??
  {};

const SUPABASE_URL: string | undefined = extra.SUPABASE_URL;
const SUPABASE_ANON_KEY: string | undefined = extra.SUPABASE_ANON_KEY;

// DEBUG TEMP: vérifie ce que l’app lit
// (à retirer quand OK)
console.log("SUPABASE_URL:", SUPABASE_URL);
console.log("ANON len:", SUPABASE_ANON_KEY ? SUPABASE_ANON_KEY.length : 0);

export const supabase = createClient(SUPABASE_URL!, SUPABASE_ANON_KEY!, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

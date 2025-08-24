// src/auth.tsx
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import Constants from "expo-constants";
import { createClient } from "@supabase/supabase-js";
import AsyncStorage from "@react-native-async-storage/async-storage";

// --- Supabase client (Expo, storage natif) ---
const expoExtra: any = Constants.expoConfig?.extra ?? Constants.manifest?.extra ?? {};
const SUPABASE_URL = expoExtra.SUPABASE_URL;
const SUPABASE_ANON_KEY = expoExtra.SUPABASE_ANON_KEY;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: { persistSession: true, storage: AsyncStorage as any },
});

type AuthCtx = {
  loading: boolean;
  authUid: string | null;
  email: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authUid, setAuthUid] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  // Bootstrap + abonnement aux changements d’auth
  useEffect(() => {
    let mounted = true;

    (async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (mounted) {
        setAuthUid(session?.user?.id ?? null);
        setEmail(session?.user?.email ?? null);
        setLoading(false);
      }
    })();

    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthUid(session?.user?.id ?? null);
      setEmail(session?.user?.email ?? null);
    });

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  async function signIn(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    // onAuthStateChange se chargera de mettre authUid/email à jour
  }

  async function signUp(email: string, password: string) {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  }

  async function signOut() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  }

  const value = useMemo(() => ({ loading, authUid, email, signIn, signUp, signOut }), [loading, authUid, email]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

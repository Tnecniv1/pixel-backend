// src/auth.tsx
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { supabase } from "./supabase"; // ✅ Utiliser le client unique de supabase.ts

// Page de redirection après confirmation e-mail
const EMAIL_CONFIRMED_URL = "https://pixel-calcul-mental.onrender.com/email-confirmed";

type AuthCtx = {
  loading: boolean;
  authUid: string | null;
  email: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, name?: string) => Promise<void>;
  signOut: () => Promise<void>;
  getAccessToken: () => Promise<string>;
};

const Ctx = createContext<AuthCtx | null>(null);

// ✅ On exporte aussi 'supabase' pour compatibilité avec le code existant
export { supabase };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authUid, setAuthUid] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

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
  }

  async function signUp(email: string, password: string, name?: string) {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        // on stocke le nom en métadonnées s'il est fourni
        ...(name ? { data: { name } } : {}),
        // URL de redirection après clic sur "Confirmer mon e-mail"
        emailRedirectTo: EMAIL_CONFIRMED_URL,
      },
    });
    if (error) throw error;
  }

  async function signOut() {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  }

  async function getAccessToken(): Promise<string> {
    const { data, error } = await supabase.auth.getSession();
    if (error) throw error;
    const token = data.session?.access_token;
    if (!token) throw new Error("Session introuvable. Veuillez vous reconnecter.");
    return token;
  }

  const value = useMemo(
    () => ({ loading, authUid, email, signIn, signUp, signOut, getAccessToken }),
    [loading, authUid, email]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
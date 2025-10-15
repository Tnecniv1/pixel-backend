import React, { useCallback, useState } from "react";
import { View, Button, Alert } from "react-native";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import { supabase } from "../supabase";

WebBrowser.maybeCompleteAuthSession();

// Retour dans l'app (exp:// en Expo Go, pixelcalc:// en build)
const appReturnUrl = AuthSession.makeRedirectUri({
  scheme: "pixelcalc",
  path: "auth-callback",
});

// 🔒 Proxy Expo : mets TON couple @owner/slug EXACT
const EXPO_PROXY = "https://auth.expo.io/@vcent.1/pixel-mobile";

console.log("appReturnUrl =", appReturnUrl);
console.log("expoProxyRedirect =", EXPO_PROXY);

export default function SocialAuthButtons() {
  const [busy, setBusy] = useState<null | "google" | "apple">(null);

  const runOAuth = useCallback(async (provider: "google" | "apple") => {
    try {
      setBusy(provider);

      // 1) Demander l’URL d’auth à Supabase (peu importe ce qu’il met en redirect_to)
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: EXPO_PROXY }, // hint (on va REFORCER derrière)
      });
      if (error) throw error;

      // 2) Forcer redirect_to = EXPO_PROXY dans l’URL retournée
      const url = new URL(String(data?.url));
      console.log("[OAuth] AUTH URL (raw) =", url.toString());
      console.log("[OAuth] redirect_to (raw) =", url.searchParams.get("redirect_to"));

      url.searchParams.set("redirect_to", EXPO_PROXY);
      const authUrlForced = url.toString();

      console.log("[OAuth] AUTH URL (forced) =", authUrlForced);
      console.log("[OAuth] redirect_to (forced) =", new URL(authUrlForced).searchParams.get("redirect_to"));

      // 3) Ouvrir le navigateur et attendre le retour dans l’app (exp://…)
      const res = await WebBrowser.openAuthSessionAsync(authUrlForced, appReturnUrl);

      // 4) Vérifier la session
      if (res.type === "success") {
        const { data: s } = await supabase.auth.getSession();
        if (s.session) {
          Alert.alert("Bienvenue 👋", `Connexion ${provider} réussie`);
        } else {
          Alert.alert("Connexion incomplète", "Aucune session active détectée.");
        }
      } else if (res.type !== "dismiss") {
        Alert.alert("Annulé", "La connexion a été interrompue.");
      }
    } catch (e: any) {
      console.log("[OAuth] ERROR:", e);
      Alert.alert("Erreur OAuth", e?.message ?? String(e));
    } finally {
      setBusy(null);
    }
  }, []);

  return (
    <View style={{ gap: 8 }}>
      <Button
        title={busy === "google" ? "Connexion Google…" : "Continuer avec Google"}
        onPress={() => runOAuth("google")}
        disabled={!!busy}
      />
      <Button
        title={busy === "apple" ? "Connexion Apple…" : "Continuer avec Apple"}
        onPress={() => runOAuth("apple")}
        disabled={!!busy}
      />
    </View>
  );
}

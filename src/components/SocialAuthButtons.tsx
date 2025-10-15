import React, { useCallback, useState } from "react";
import { View, Button, Alert } from "react-native";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import { supabase } from "../supabase";

WebBrowser.maybeCompleteAuthSession();

// Retour dans l'app
const appReturnUrl = AuthSession.makeRedirectUri({
  scheme: "pixelcalc",
  path: "auth-callback",
});

console.log("appReturnUrl =", appReturnUrl);

export default function SocialAuthButtons() {
  const [busy, setBusy] = useState<null | "google" | "apple">(null);

  const runOAuth = useCallback(async (provider: "google" | "apple") => {
    try {
      setBusy(provider);

      // 1) Demander l'URL d'auth à Supabase avec callback DIRECT
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { 
          redirectTo: appReturnUrl,  // ✅ Callback direct vers l'app
          skipBrowserRedirect: false
        },
      });
      if (error) throw error;

      const authUrl = String(data?.url);
      console.log("[OAuth] AUTH URL =", authUrl);

      // 2) Ouvrir le navigateur et attendre le retour dans l'app
      const res = await WebBrowser.openAuthSessionAsync(authUrl, appReturnUrl);

      console.log("[OAuth] Result =", res);

      // 3) Vérifier la session
      if (res.type === "success") {
        // Attendre un peu que Supabase traite le callback
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const { data: s, error: sessionError } = await supabase.auth.getSession();
        
        if (sessionError) {
          console.error("[OAuth] Session error:", sessionError);
          Alert.alert("Erreur", sessionError.message);
        } else if (s.session) {
          Alert.alert("Bienvenue 👋", `Connexion ${provider} réussie`);
        } else {
          Alert.alert("Connexion incomplète", "Aucune session active détectée.");
        }
      } else if (res.type === "cancel") {
        Alert.alert("Annulé", "La connexion a été annulée.");
      }
    } catch (e: any) {
      console.error("[OAuth] ERROR:", e);
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
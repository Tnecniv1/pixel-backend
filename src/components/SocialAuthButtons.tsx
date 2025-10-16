import React, { useCallback, useState } from "react";
import { View, Button, Alert } from "react-native";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import { supabase } from "../supabase";

WebBrowser.maybeCompleteAuthSession();

// URL de retour dans l'app (deep link)
const appReturnUrl = AuthSession.makeRedirectUri({
  scheme: "pixelcalc",
  path: "auth-callback",
});

// URL de callback sur votre serveur web
const serverCallbackUrl = "https://pixel-calcul-mental.onrender.com/auth-callback";

console.log("=== Configuration OAuth ===");
console.log("App Return URL:", appReturnUrl);
console.log("Server Callback URL:", serverCallbackUrl);
console.log("==========================");

export default function SocialAuthButtons() {
  const [busy, setBusy] = useState<null | "google" | "apple">(null);

  const runOAuth = useCallback(async (provider: "google" | "apple") => {
    try {
      setBusy(provider);

      console.log(`\n[${provider.toUpperCase()}] === DÉBUT AUTHENTIFICATION ===`);

      // Étape 1 : Obtenir l'URL d'authentification depuis Supabase
      console.log(`[${provider.toUpperCase()}] Demande de l'URL d'authentification...`);
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { 
          redirectTo: serverCallbackUrl,
          skipBrowserRedirect: false
        },
      });
      
      if (error) {
        console.error(`[${provider.toUpperCase()}] Erreur lors de la récupération de l'URL:`, error);
        throw error;
      }

      const authUrl = String(data?.url);
      console.log(`[${provider.toUpperCase()}] URL d'authentification obtenue`);
      console.log(`[${provider.toUpperCase()}] URL:`, authUrl);

      // Étape 2 : Ouvrir le navigateur pour l'authentification
      console.log(`[${provider.toUpperCase()}] Ouverture du navigateur...`);
      const res = await WebBrowser.openAuthSessionAsync(authUrl, appReturnUrl);

      console.log(`[${provider.toUpperCase()}] Résultat du navigateur:`, res.type);

      // Étape 3 : Traiter le résultat
      if (res.type === "success") {
        console.log(`[${provider.toUpperCase()}] ✅ Navigateur fermé avec succès`);
        console.log(`[${provider.toUpperCase()}] URL de retour:`, res.url);
        
        // Extraire les tokens de l'URL
        const url = new URL(res.url);
        const accessToken = url.searchParams.get('access_token');
        const refreshToken = url.searchParams.get('refresh_token');
        const expiresAt = url.searchParams.get('expires_at');
        const expiresIn = url.searchParams.get('expires_in');
        const tokenType = url.searchParams.get('token_type');

        console.log(`[${provider.toUpperCase()}] Tokens extraits:`);
        console.log(`  - Access Token: ${accessToken ? '✅ Présent (' + accessToken.substring(0, 20) + '...)' : '❌ MANQUANT'}`);
        console.log(`  - Refresh Token: ${refreshToken ? '✅ Présent (' + refreshToken.substring(0, 20) + '...)' : '❌ MANQUANT'}`);
        console.log(`  - Expires At: ${expiresAt || 'Non fourni'}`);
        console.log(`  - Expires In: ${expiresIn || 'Non fourni'}`);
        console.log(`  - Token Type: ${tokenType || 'Non fourni'}`);

        if (!accessToken || !refreshToken) {
          console.error(`[${provider.toUpperCase()}] ❌ Tokens manquants dans l'URL de retour`);
          console.error(`[${provider.toUpperCase()}] URL complète:`, res.url);
          throw new Error("Tokens d'authentification manquants dans la réponse");
        }

        // Étape 4 : Définir la session dans Supabase
        console.log(`[${provider.toUpperCase()}] Configuration de la session Supabase...`);
        const { data: sessionData, error: sessionError } = await supabase.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });

        if (sessionError) {
          console.error(`[${provider.toUpperCase()}] Erreur lors de la configuration de la session:`, sessionError);
          throw sessionError;
        }
        
        if (!sessionData.session) {
          console.error(`[${provider.toUpperCase()}] Session non créée`);
          throw new Error("La session n'a pas pu être créée");
        }

        const userEmail = sessionData.session.user?.email || "utilisateur";
        const userId = sessionData.session.user?.id;
        
        console.log(`[${provider.toUpperCase()}] ✅ Session établie avec succès`);
        console.log(`[${provider.toUpperCase()}] Email: ${userEmail}`);
        console.log(`[${provider.toUpperCase()}] User ID: ${userId}`);
        console.log(`[${provider.toUpperCase()}] === FIN AUTHENTIFICATION ===\n`);
        
        Alert.alert(
          "Bienvenue 👋", 
          `Connexion ${provider === 'google' ? 'Google' : 'Apple'} réussie !\n\n${userEmail}`
        );
        
      } else if (res.type === "cancel") {
        console.log(`[${provider.toUpperCase()}] ⚠️ Authentification annulée par l'utilisateur`);
        Alert.alert("Annulé", "La connexion a été annulée.");
        
      } else if (res.type === "dismiss") {
        console.log(`[${provider.toUpperCase()}] ⚠️ Navigateur fermé sans authentification`);
        Alert.alert("Fermé", "Le navigateur a été fermé.");
        
      } else {
        console.warn(`[${provider.toUpperCase()}] ⚠️ Type de résultat inattendu:`, res.type);
        throw new Error(`Résultat inattendu du navigateur: ${res.type}`);
      }
      
    } catch (e: any) {
      console.error(`[${provider.toUpperCase()}] ❌ ERREUR GLOBALE:`, e);
      console.error(`[${provider.toUpperCase()}] Message:`, e?.message);
      console.error(`[${provider.toUpperCase()}] Stack:`, e?.stack);
      
      Alert.alert(
        "Erreur de connexion", 
        e?.message || "Une erreur s'est produite lors de la connexion. Veuillez réessayer."
      );
    } finally {
      setBusy(null);
      console.log(`[${provider.toUpperCase()}] Nettoyage terminé\n`);
    }
  }, []);

  return (
    <View style={{ gap: 8 }}>
      <Button
        title={busy === "google" ? "Connexion Google…" : "Continuer avec Google"}
        onPress={() => runOAuth("google")}
        disabled={!!busy}
        color="#4285F4"
      />
      <Button
        title={busy === "apple" ? "Connexion Apple…" : "Continuer avec Apple"}
        onPress={() => runOAuth("apple")}
        disabled={!!busy}
        color="#000000"
      />
    </View>
  );
}
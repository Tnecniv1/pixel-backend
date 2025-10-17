import React, { useCallback, useState } from "react";
import { View, Alert, Platform, StyleSheet, TouchableOpacity, Text } from "react-native";
import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import * as AppleAuthentication from 'expo-apple-authentication';
import { supabase } from "../supabase";

WebBrowser.maybeCompleteAuthSession();

const appReturnUrl = AuthSession.makeRedirectUri({
  scheme: "pixelcalc",
  path: "auth-callback",
});

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
      console.log(`[${provider.toUpperCase()}] Demande de l'URL d'authentification...`);
      
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { 
          redirectTo: serverCallbackUrl,
          skipBrowserRedirect: false
        },
      });
      
      if (error) throw error;

      const authUrl = String(data?.url);
      console.log(`[${provider.toUpperCase()}] URL d'authentification obtenue`);
      console.log(`[${provider.toUpperCase()}] Ouverture du navigateur...`);
      
      const res = await WebBrowser.openAuthSessionAsync(authUrl, appReturnUrl);
      console.log(`[${provider.toUpperCase()}] Résultat du navigateur:`, res.type);

      if (res.type === "success" && res.url) {
        console.log(`[${provider.toUpperCase()}] ✅ Succès`);
        
        const url = new URL(res.url);
        const accessToken = url.searchParams.get('access_token');
        const refreshToken = url.searchParams.get('refresh_token');

        console.log(`[${provider.toUpperCase()}] Tokens: ${accessToken ? '✅' : '❌'} / ${refreshToken ? '✅' : '❌'}`);

        if (!accessToken || !refreshToken) {
          throw new Error("Tokens d'authentification manquants");
        }

        const { data: sessionData, error: sessionError } = await supabase.auth.setSession({
          access_token: accessToken,
          refresh_token: refreshToken,
        });

        if (sessionError) throw sessionError;
        if (!sessionData.session) throw new Error("Session non créée");

        const userEmail = sessionData.session.user?.email || "utilisateur";
        console.log(`[${provider.toUpperCase()}] ✅ Session établie: ${userEmail}`);
        
        Alert.alert("Bienvenue 👋", `Connexion ${provider} réussie !\n\n${userEmail}`);
        
      } else if (res.type === "cancel") {
        console.log(`[${provider.toUpperCase()}] ⚠️ Annulé`);
        Alert.alert("Annulé", "La connexion a été annulée.");
      }
      
    } catch (e: any) {
      console.error(`[${provider.toUpperCase()}] ❌ ERREUR:`, e?.message);
      Alert.alert("Erreur de connexion", e?.message || "Une erreur s'est produite");
    } finally {
      setBusy(null);
    }
  }, []);

  return (
    <View style={styles.container}>
      {/* Bouton Google */}
      <TouchableOpacity
        style={[styles.googleButton, busy === "google" && styles.buttonDisabled]}
        onPress={() => runOAuth("google")}
        disabled={!!busy}
        activeOpacity={0.8}
      >
        <View style={styles.googleIconContainer}>
          <Text style={styles.googleG}>G</Text>
        </View>
        <Text style={styles.googleText}>
          {busy === "google" ? "Connexion Google…" : "Continuer avec Google"}
        </Text>
      </TouchableOpacity>

      {/* Bouton Apple officiel */}
      {Platform.OS === 'ios' && (
        <AppleAuthentication.AppleAuthenticationButton
          buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
          buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
          cornerRadius={8}
          style={styles.appleButton}
          onPress={() => runOAuth("apple")}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: 12,
    width: '100%',
  },
  googleButton: {
    height: 44,
    backgroundColor: '#4285F4',
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  googleIconContainer: {
    width: 32,
    height: 32,
    backgroundColor: 'white',
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  googleG: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#4285F4',
  },
  googleText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
    flex: 1,
    textAlign: 'center',
  },
  appleButton: {
    width: '100%',
    height: 44,
  },
});
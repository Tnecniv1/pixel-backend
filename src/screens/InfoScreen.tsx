// src/screens/InfoScreen.tsx
import React from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  Linking,
  Alert,
  ActivityIndicator,
} from "react-native";
import Constants from "expo-constants";
import Purchases from "react-native-purchases";
import { useAuth } from "../auth";
import { useNavigation } from "@react-navigation/native";

// === URLs légales ===
const PRIVACY_URL =
  "https://swamp-path-616.notion.site/Politique-de-Confidentialit-Pixel-2645249ea1cc80f8a656c31cffc46ca2";
const TERMS_URL =
  "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/";

// Supabase (en-tête apikey requis pour /functions/v1)
const extra: any =
  (Constants as any).expoConfig?.extra ??
  (Constants as any).manifest?.extra ?? {};
const SUPABASE_ANON_KEY = extra.SUPABASE_ANON_KEY;
const DELETE_FUNCTION_URL =
  "https://vbeatapbkphtjuitfspb.supabase.co/functions/v1/delete-account";

const SUPPORT_EMAIL = "vincentlebarbey@gmail.com";

export default function InfoScreen() {
  const navigation = useNavigation<any>();
  const { authUid, getAccessToken, signOut } = (useAuth() as any) ?? {};
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [isRestoring, setIsRestoring] = React.useState(false);
  const [isSigningOut, setIsSigningOut] = React.useState(false);

  const version =
    (Constants as any).expoConfig?.version ??
    (Constants as any).manifest?.version ??
    "1.0.0";
  const build =
    (Constants as any).expoConfig?.ios?.buildNumber ??
    (Constants as any).manifest2?.extra?.eas?.buildNumber ??
    "";

  // ---------- RevenueCat ----------
  async function ensureRCConfigured() {
    if ((Constants as any).appOwnership === "expo") {
      throw new Error(
        "Les achats intégrés ne fonctionnent pas dans Expo Go. Utilisez un Dev Client (EAS) ou TestFlight."
      );
    }
    const rcKey =
      extra?.EXPO_PUBLIC_RC_IOS_SDK_KEY ||
      extra?.RC_API_KEY ||
      extra?.EXPO_PUBLIC_RC_API_KEY;
    if (!rcKey || !String(rcKey).startsWith("appl_")) {
      throw new Error(
        "Clé RevenueCat iOS manquante/incorrecte (EXPO_PUBLIC_RC_IOS_SDK_KEY)."
      );
    }
    await Purchases.configure({ apiKey: rcKey });
  }

  function pickPackages(pkgs: any[]) {
    const monthly = pkgs?.find((p) =>
      p?.identifier?.toLowerCase?.().includes("month")
    );
    const annual = pkgs?.find(
      (p) =>
        p?.identifier?.toLowerCase?.().includes("annual") ||
        p?.identifier?.toLowerCase?.().includes("year")
    );
    return { monthly, annual };
  }

  async function openPaywall() {
    try {
      await ensureRCConfigured();
      const offerings: any = await Purchases.getOfferings();
      const current = offerings?.current;
      if (!current || !current.availablePackages?.length) {
        throw new Error(
          "Aucune offre disponible. Vérifiez l’offering 'current' et ses packages dans RevenueCat."
        );
      }
      const { monthly, annual } = pickPackages(current.availablePackages);
      if (!monthly && !annual) {
        throw new Error(
          "Packages mensuel/annuel introuvables dans l’offering (identifiants 'monthly' / 'annual')."
        );
      }
      const monthlyLabel = monthly
        ? `${monthly.product?.priceString ?? "—"} · Mensuel`
        : null;
      const annualPrice = annual?.product?.price as number | undefined;
      const annualPerMonth = annualPrice ? (annualPrice / 12).toFixed(2) : null;
      const annualLabel = annual
        ? `${annual.product?.priceString ?? "—"} · Annuel${
            annualPerMonth ? ` (~${annualPerMonth}/mois)` : ""
          }`
        : null;

      Alert.alert(
        "Choisir un abonnement",
        "Sélectionnez une option",
        [
          annual && {
            text: annualLabel!,
            onPress: async () => {
              try {
                await Purchases.purchasePackage(annual as any);
                Alert.alert("Succès", "Abonnement annuel acheté (sandbox).");
              } catch (e: any) {
                if (!e?.userCancelled)
                  Alert.alert("Erreur", e?.message ?? "Achat impossible.");
              }
            },
          },
          monthly && {
            text: monthlyLabel!,
            onPress: async () => {
              try {
                await Purchases.purchasePackage(monthly as any);
                Alert.alert("Succès", "Abonnement mensuel acheté (sandbox).");
              } catch (e: any) {
                if (!e?.userCancelled)
                  Alert.alert("Erreur", e?.message ?? "Achat impossible.");
              }
            },
          },
          { text: "Annuler", style: "cancel" },
        ].filter(Boolean) as any
      );
    } catch (e: any) {
      Alert.alert("Erreur", e?.message ?? "Paywall indisponible.");
    }
  }

  // ---------- Restaurer achats ----------
  async function restorePurchases() {
    try {
      setIsRestoring(true);
      await ensureRCConfigured();
      const info: any = await Purchases.restorePurchases();
      const active = info?.entitlements?.active ?? {};
      if (Object.keys(active).length > 0) {
        Alert.alert("Achats restaurés", "Votre abonnement a été restauré.");
      } else {
        Alert.alert(
          "Aucun achat à restaurer",
          "Aucun abonnement actif n’a été trouvé pour ce compte."
        );
      }
    } catch (e: any) {
      Alert.alert("Erreur", e?.message ?? "Restauration impossible.");
    } finally {
      setIsRestoring(false);
    }
  }

  // ---------- Contact & gestion ----------
  function contactVincent() {
    try {
      const subject = encodeURIComponent("Pixel — Contact / Support");
      const body = encodeURIComponent(
        `Bonjour Vincent,

Je souhaite vous contacter à propos de Pixel.

—
Infos techniques :
Version: ${version}${build ? ` (iOS build ${build})` : ""}`
      );
      const url = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
      Linking.openURL(url).catch(() => {
        Alert.alert(
          "Info",
          `Aucune application e-mail configurée.\n\nAdresse : ${SUPPORT_EMAIL}`
        );
      });
    } catch {
      Alert.alert("Erreur", "Impossible d’ouvrir l’e-mail.");
    }
  }

  function openIOSSubscriptions() {
    const url = "itms-apps://apps.apple.com/account/subscriptions";
    Linking.openURL(url).catch(() => {
      Linking.openURL("https://apps.apple.com/account/subscriptions");
    });
  }

  // ---------- Déconnexion ----------
  async function onSignOut() {
    try {
      setIsSigningOut(true);
      if (typeof signOut === "function") {
        await signOut(); // nettoie la session supabase + état app (ton hook)
      }
      // Retour à l’écran d’auth
      navigation.reset({ index: 0, routes: [{ name: "Auth" }] });
    } catch (e: any) {
      Alert.alert("Impossible de se déconnecter", e?.message ?? String(e));
    } finally {
      setIsSigningOut(false);
    }
  }

  // ---------- Suppression de compte ----------
  async function performDelete() {
    try {
      setIsDeleting(true);
      const token = await getAccessToken();
      const resp = await fetch(DELETE_FUNCTION_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          apikey: SUPABASE_ANON_KEY,
        },
      });
      if (!resp.ok) {
        const body = await resp.text();
        throw new Error(`Suppression impossible (${resp.status}) — ${body}`);
      }
      try { await Purchases.logOut(); } catch {}
      try { if (typeof signOut === "function") await signOut(); } catch {}
      Alert.alert("Compte supprimé", "Votre compte et vos données ont été supprimés.");
      navigation.reset({ index: 0, routes: [{ name: "Auth" }] });
    } catch (e: any) {
      Alert.alert("Erreur", e?.message ?? "La suppression a échoué.");
    } finally {
      setIsDeleting(false);
    }
  }

  function confirmDeleteFlow() {
    Alert.alert(
      "Supprimer le compte ?",
      "Cette action est permanente et effacera vos données associées.\n\nLa suppression n’annule pas l’abonnement App Store.",
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Continuer",
          style: "destructive",
          onPress: () => {
            Alert.alert(
              "Confirmer la suppression",
              "Voulez-vous supprimer définitivement votre compte ?",
              [
                { text: "Annuler", style: "cancel" },
                { text: "Supprimer définitivement", style: "destructive", onPress: performDelete },
              ]
            );
          },
        },
      ]
    );
  }

  const openPrivacy = () => Linking.openURL(PRIVACY_URL);
  const openTerms = () => Linking.openURL(TERMS_URL);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Informations</Text>

      <Pressable style={styles.primaryBtn} onPress={openPaywall}>
        <Text style={styles.primaryBtnText}>S’abonner à Pixel</Text>
      </Pressable>

      {/* Restaurer achats */}
      <Pressable
        style={[styles.secondaryBtn, isRestoring && { opacity: 0.6 }]}
        onPress={restorePurchases}
        disabled={isRestoring}
      >
        {isRestoring ? <ActivityIndicator /> : <Text style={styles.secondaryBtnText}>Restaurer mes achats</Text>}
      </Pressable>

      {/* Contact */}
      <Pressable style={styles.secondaryBtn} onPress={contactVincent}>
        <Text style={styles.secondaryBtnText}>Contacter Vincent</Text>
      </Pressable>

      {/* Déconnexion */}
      <Pressable
        style={[styles.secondaryBtn, isSigningOut && { opacity: 0.6 }]}
        onPress={onSignOut}
        disabled={isSigningOut}
      >
        {isSigningOut ? <ActivityIndicator /> : <Text style={styles.secondaryBtnText}>Se déconnecter</Text>}
      </Pressable>

      <Text style={styles.notice}>
        La suppression n’annule pas l’abonnement App&nbsp;Store.
      </Text>
      <Pressable onPress={openIOSSubscriptions}>
        <Text style={styles.link}>Gérer mon abonnement</Text>
      </Pressable>

      {/* Liens légaux */}
      <View style={{ marginTop: 16, alignItems: "center" }}>
        <Pressable onPress={openPrivacy}>
          <Text style={styles.link}>Politique de confidentialité</Text>
        </Pressable>
        <Pressable onPress={openTerms} style={{ marginTop: 6 }}>
          <Text style={styles.link}>Conditions d’utilisation (CLUF)</Text>
        </Pressable>
      </View>

      {/* Suppression de compte */}
      <Pressable
        style={[styles.destructiveBtn, isDeleting && { opacity: 0.6 }]}
        disabled={isDeleting}
        onPress={confirmDeleteFlow}
      >
        {isDeleting ? <ActivityIndicator /> : <Text style={styles.destructiveBtnText}>Supprimer mon compte</Text>}
      </Pressable>

      <Text style={styles.version}>
        Version {version}
        {build ? ` (iOS build ${build})` : ""}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, paddingTop: 24, backgroundColor: "#0b0f17", alignItems: "center" },
  title: { fontSize: 24, color: "#fff", fontWeight: "800", marginBottom: 12 },
  primaryBtn: { width: "100%", backgroundColor: "#4c92f7", paddingVertical: 14, borderRadius: 14, alignItems: "center", marginTop: 8 },
  primaryBtnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  secondaryBtn: { width: "100%", backgroundColor: "#374151", paddingVertical: 14, borderRadius: 14, alignItems: "center", marginTop: 14 },
  secondaryBtnText: { color: "#fff", fontWeight: "700", fontSize: 18 },
  notice: { marginTop: 18, color: "#6b7280", textAlign: "center" },
  link: { textAlign: "center", textDecorationLine: "underline", color: "#4c92f7", fontWeight: "600" },
  destructiveBtn: { width: "100%", backgroundColor: "#ef4444", paddingVertical: 14, borderRadius: 14, alignItems: "center", marginTop: 22 },
  destructiveBtnText: { color: "#fff", fontWeight: "800", fontSize: 16 },
  version: { position: "absolute", bottom: 20, color: "#9aa0a6" },
});

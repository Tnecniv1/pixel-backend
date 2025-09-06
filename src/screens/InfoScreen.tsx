// src/screens/InfoScreen.tsx
import React from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  Linking,
  Alert,
} from "react-native";
import Constants from "expo-constants";
import Purchases from "react-native-purchases";
import { useAuth } from "../auth";

async function ensureRCConfigured(userId?: string) {
  try {
    // Si RC est déjà configuré, ceci passe
    await Purchases.getCustomerInfo();
  } catch {
    // Sinon on configure ici (clé depuis app.json -> extra.RC_API_KEY ou EXPO_PUBLIC_RC_API_KEY)
    const extra: any = Constants?.expoConfig?.extra ?? {};
    const apiKey = extra?.RC_API_KEY || extra?.EXPO_PUBLIC_RC_API_KEY;
    if (!apiKey) throw new Error("RC API key manquante");
    await Purchases.configure({ apiKey, appUserID: userId ?? null });
  }
}

export default function InfoScreen() {
  const { authUid } = useAuth();

  async function openPaywall() {
    try {
      // 1) s’assure que RevenueCat est prêt
      await ensureRCConfigured(authUid);

      // 2) récupération de l’offre par défaut
      const offerings = await Purchases.getOfferings();
      const pkg = offerings.current?.availablePackages?.[0];
      if (!pkg) throw new Error("Aucun produit disponible.");

      // 3) achat (affiche la feuille d’achat Apple)
      await Purchases.purchasePackage(pkg);
      Alert.alert("Paiement", "Merci 🙏 Votre abonnement est actif !");
    } catch (err: any) {
      // L’utilisateur peut annuler : on ne spam pas d’erreur dans ce cas
      const userCancelled = err?.userCancelled ?? err?.code === "PurchaseCancelledError";
      if (!userCancelled) {
        console.warn("Erreur ouverture paywall:", err);
        Alert.alert("Paiement", err?.message ?? "Impossible d’ouvrir le paywall.");
      }
    }
  }

  function contactVincent() {
    const subject = encodeURIComponent("Contact Pixel – Calcul Mental");
    const body = encodeURIComponent(
      `Bonjour Vincent,\n\nJe souhaite vous contacter à propos de l’application Pixel.\n\n(Expliquez ici votre demande)\n`
    );
    Linking.openURL(`mailto:vincentlebarbey@monstro.fr?subject=${subject}&body=${body}`);
  }

  const version = Constants.expoConfig?.version ?? "1.0.0";
  const build = Constants.expoConfig?.ios?.buildNumber ?? "";

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Informations</Text>

      <Text style={styles.subtitle}>
        Abonnez-vous à Pixel pour débloquer tout le contenu.{"\n"}
        <Text style={styles.bold}>3 jours gratuits</Text>, puis abonnement payant.
      </Text>

      <Pressable style={styles.primaryBtn} onPress={openPaywall}>
        <Text style={styles.primaryBtnText}>S’abonner à Pixel</Text>
      </Pressable>

      <Pressable style={styles.secondaryBtn} onPress={contactVincent}>
        <Text style={styles.secondaryBtnText}>Contacter Vincent</Text>
      </Pressable>

      <Text style={styles.version}>Version {version}{build ? ` (iOS build ${build})` : ""}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 32,
    alignItems: "center",
    backgroundColor: "#fff",
  },
  title: {
    fontSize: 26,
    fontWeight: "800",
    marginTop: 12,
    marginBottom: 12,
  },
  subtitle: {
    textAlign: "center",
    color: "#444",
    fontSize: 16,
    lineHeight: 22,
    marginBottom: 24,
  },
  bold: {
    fontWeight: "700",
    color: "#222",
  },
  primaryBtn: {
    width: "100%",
    backgroundColor: "#f7a24c",
    paddingVertical: 16,
    borderRadius: 14,
    alignItems: "center",
    marginTop: 8,
  },
  primaryBtnText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 18,
  },
  secondaryBtn: {
    width: "100%",
    backgroundColor: "#4c92f7",
    paddingVertical: 16,
    borderRadius: 14,
    alignItems: "center",
    marginTop: 14,
  },
  secondaryBtnText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 18,
  },
  version: {
    position: "absolute",
    bottom: 20,
    color: "#9aa0a6",
  },
});

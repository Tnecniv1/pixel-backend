import React from "react";
import { Alert, Pressable, StyleSheet, Text } from "react-native";
// ⬇️ adapte ce chemin si besoin: "../auth" ou "../lib/supabase"
import { supabase } from "../auth";

type Props = { style?: any };

export default function SignOutButton({ style }: Props) {
  const [busy, setBusy] = React.useState(false);

  const onPress = async () => {
    console.log("[signout] pressed");
    if (busy) return;
    setBusy(true);
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      Alert.alert("Déconnexion", "Tu es déconnecté.");
      // si tu as une navigation conditionnée à la session via AuthProvider,
      // l'app basculera toute seule. Sinon, tu peux forcer une nav ici.
    } catch (e: any) {
      console.error("[signout] error:", e);
      Alert.alert("Déconnexion", e?.message ?? "Erreur inconnue");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      style={[styles.btn, style]} // ← style optionnel passé par le header
    >
      <Text style={styles.txt}>D</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    // IMPORTANT: pas de position absolute dans la version header
    width: 28,
    height: 28,
    borderRadius: 6,
    backgroundColor: "#E8ECF1",
    borderWidth: 1,
    borderColor: "#C8D1DC",
    alignItems: "center",
    justifyContent: "center",
  },
  txt: { fontWeight: "700", fontSize: 14, color: "#1A1F36" },
});

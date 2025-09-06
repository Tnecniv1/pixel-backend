// src/screens/AuthScreen.tsx
import React, { useEffect, useState } from "react";
import { View, Text, TextInput, Button, Alert } from "react-native";
import { useAuth } from "../auth";

export default function AuthScreen({ navigation }: any) {
  const { authUid, loading, signIn, signUp } = useAuth();
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Si on se connecte avec succès → on bascule automatiquement vers Home
  useEffect(() => {
    if (authUid) {
      navigation.reset({ index: 0, routes: [{ name: "Home" }] });
    }
  }, [authUid]);

  if (loading) {
    return <View style={{ padding: 20 }}><Text>Chargement…</Text></View>;
  }

  async function onLogin() {
    try {
      setSubmitting(true);
      await signIn(email.trim(), pass);
      // pas besoin d'afficher "ok" : la redirection se fait via authUid
    } catch (e: any) {
      Alert.alert("Connexion échouée", e?.message ?? String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function onSignup() {
    try {
      setSubmitting(true);
      await signUp(email.trim(), pass);
      Alert.alert("Inscription", "Compte créé (vérifie tes emails si nécessaire).");
    } catch (e: any) {
      Alert.alert("Inscription échouée", e?.message ?? String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, gap: 12, justifyContent: "center" }}>
      <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 8 }}>Connexion</Text>

      <Text>Email</Text>
      <TextInput
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="you@example.com"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }}
      />

      <Text>Mot de passe</Text>
      <TextInput
        value={pass}
        onChangeText={setPass}
        secureTextEntry
        placeholder="••••••••"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }}
      />

      <Button title={submitting ? "Connexion…" : "Se connecter"} onPress={onLogin} disabled={submitting} />
      <Button
        title="Créer un compte"
        onPress={() => navigation.navigate("SignUp")}
        disabled={submitting}
      />
    </View>
  );
}

// src/screens/AuthScreen.tsx
import React, { useEffect, useState } from "react";
import { View, Text, TextInput, Button, Alert, TouchableOpacity } from "react-native";
import { useAuth } from "../auth";
import SocialAuthButtons from "../components/SocialAuthButtons";

export default function AuthScreen({ navigation }: any) {
  const { authUid, loading, signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (authUid) {
      navigation.reset({ index: 0, routes: [{ name: "Home" }] });
    }
  }, [authUid]);

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: "center", padding: 24 }}>
        <Text>Chargement…</Text>
      </View>
    );
  }

  async function onLogin() {
    try {
      setSubmitting(true);
      await signIn(email.trim(), pass);
    } catch (e: any) {
      Alert.alert("Connexion échouée", e?.message ?? String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: "center" }}>
      <Text style={{ fontSize: 24, fontWeight: "700", marginBottom: 12 }}>Connexion</Text>

      {/* --- Email / Mot de passe --- */}
      <View style={{ gap: 8 }}>
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

        {/* Lien 'Mot de passe oublié ?' */}
        <TouchableOpacity
          onPress={() => navigation.navigate("ForgotPassword", { presetEmail: email.trim() })}
          style={{ alignSelf: "flex-end", marginTop: 4 }}
          accessibilityRole="button"
          accessibilityLabel="Mot de passe oublié"
        >
          <Text style={{ textDecorationLine: "underline" }}>Mot de passe oublié ?</Text>
        </TouchableOpacity>

        <Button
          title={submitting ? "Connexion…" : "Se connecter"}
          onPress={onLogin}
          disabled={submitting}
        />
        <Button
          title="Créer un compte"
          onPress={() => navigation.navigate("SignUp")}
          disabled={submitting}
        />
      </View>

      {/* --- Séparateur --- */}
      <View style={{ alignItems: "center", marginVertical: 20 }}>
        <Text style={{ color: "#888" }}>— ou —</Text>
      </View>

      {/* --- Connexion sociale (Google / Apple) --- */}
      <SocialAuthButtons />
    </View>
  );
}

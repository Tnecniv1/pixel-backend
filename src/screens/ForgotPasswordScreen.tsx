// src/screens/ForgotPasswordScreen.tsx
import React, { useState, useEffect } from "react";
import { View, Text, TextInput, Button, Alert } from "react-native";
// ⬇️ adapte ce chemin à ton client Supabase (ex: "../lib/supabase")
import { supabase } from "../supabase";

export default function ForgotPasswordScreen({ route, navigation }: any) {
  const [email, setEmail] = useState("");

  useEffect(() => {
    if (route?.params?.presetEmail) setEmail(route.params.presetEmail);
  }, [route?.params?.presetEmail]);

  async function onSend() {
    const target = email.trim();
    if (!target) {
      Alert.alert("Adresse requise", "Entre ton e-mail pour recevoir le lien.");
      return;
    }
    try {
      await supabase.auth.resetPasswordForEmail(target, {
        redirectTo: "https://pixel-calcul-mental.onrender.com/reset-password",
      });
      Alert.alert(
        "E-mail envoyé",
        "Si un compte existe pour cette adresse, tu recevras un lien pour réinitialiser ton mot de passe."
      );
      navigation.goBack();
    } catch (e: any) {
      Alert.alert("Erreur", e?.message ?? String(e));
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, gap: 12, justifyContent: "center" }}>
      <Text style={{ fontSize: 20, fontWeight: "700" }}>Mot de passe oublié</Text>
      <Text>Saisis ton e-mail. Nous t’enverrons un lien de réinitialisation.</Text>

      <TextInput
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        placeholder="you@example.com"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }}
      />

      <Button title="Envoyer le lien" onPress={onSend} />
    </View>
  );
}

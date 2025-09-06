import React, { useState } from "react";
import { View, Text, TextInput, Button, Alert } from "react-native";
import { useAuth } from "../auth";

export default function SignUpScreen({ navigation }: any) {
  const { signUp } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [pass2, setPass2] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit() {
    if (!email || !pass || !pass2 || !name) {
      Alert.alert("Inscription", "Tous les champs sont requis.");
      return;
    }
    if (pass !== pass2) {
      Alert.alert("Inscription", "Les mots de passe ne correspondent pas.");
      return;
    }
    try {
      setSubmitting(true);
      await signUp(email.trim(), pass, name.trim());
      Alert.alert("Inscription", "Compte créé. Vérifie tes emails pour confirmer.", [
        { text: "OK", onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      Alert.alert("Inscription échouée", e?.message ?? String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 24, gap: 12, justifyContent: "center" }}>
      <Text style={{ fontSize: 22, fontWeight: "700", marginBottom: 8 }}>Créer un compte</Text>

      <Text>Nom et prénom</Text>
      <TextInput value={name} onChangeText={setName} placeholder="Jean Dupont"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }} />

      <Text>Email</Text>
      <TextInput value={email} onChangeText={setEmail} autoCapitalize="none"
        keyboardType="email-address" placeholder="you@example.com"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }} />

      <Text>Mot de passe</Text>
      <TextInput value={pass} onChangeText={setPass} secureTextEntry placeholder="••••••••"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }} />

      <Text>Confirmer le mot de passe</Text>
      <TextInput value={pass2} onChangeText={setPass2} secureTextEntry placeholder="••••••••"
        style={{ borderWidth: 1, padding: 10, borderRadius: 8 }} />

      <Button title={submitting ? "Création…" : "Créer mon compte"} onPress={onSubmit} disabled={submitting} />
    </View>
  );
}


// src/screens/HomeScreen.tsx
import React, { useState } from "react";
import { View, Text, Button, TextInput, Alert } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../App";
import { API_BASE } from "../config";
import { useAuth } from "../auth";

type Props = NativeStackScreenProps<RootStackParamList, "Home">;

export default function HomeScreen({ navigation }: Props) {
  const { authUid, email, loading, signIn, signUp, signOut } = useAuth();
  const [volume, setVolume] = useState("10");
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPass, setLoginPass] = useState("");

  if (loading) {
    return <View style={{ padding: 20 }}><Text>Chargement…</Text></View>;
  }

  return (
    <View style={{ padding: 20, gap: 12 }}>
      <Text style={{ fontSize: 18, fontWeight: "600" }}>Démarrer une session (mixte)</Text>

      <Text style={{ color: "#555" }}>API_BASE: {API_BASE}</Text>
      <Text style={{ color: "#555" }}>
        {authUid ? `Connecté: ${email}` : "Non connecté"}
      </Text>

      {!authUid && (
        <>
          <Text>Email</Text>
          <TextInput
            value={loginEmail}
            onChangeText={setLoginEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            style={{ borderWidth: 1, padding: 8, borderRadius: 6 }}
          />
          <Text>Mot de passe</Text>
          <TextInput
            value={loginPass}
            onChangeText={setLoginPass}
            secureTextEntry
            style={{ borderWidth: 1, padding: 8, borderRadius: 6 }}
          />
          <Button
            title="Se connecter"
            onPress={async () => {
              try { await signIn(loginEmail, loginPass); }
              catch (e: any) { Alert.alert("Login échoué", e?.message ?? String(e)); }
            }}
          />
          <Button
            title="Créer un compte"
            onPress={async () => {
              try { await signUp(loginEmail, loginPass); Alert.alert("Compte créé", "Vérifie tes emails si nécessaire."); }
              catch (e: any) { Alert.alert("Inscription échouée", e?.message ?? String(e)); }
            }}
          />
        </>
      )}

      {authUid && (
        <>
          <Text>Volume par type (ex: 10 ⇒ 30 exos)</Text>
          <TextInput
            value={volume}
            onChangeText={setVolume}
            keyboardType="numeric"
            style={{ borderWidth: 1, padding: 8, borderRadius: 6 }}
          />

          <Button
            title="Commencer"
            onPress={() => navigation.navigate("Train", { volume: Number(volume) })}
          />
          <Button title="Se déconnecter" onPress={() => signOut()} />
        </>
      )}
    </View>
  );
}


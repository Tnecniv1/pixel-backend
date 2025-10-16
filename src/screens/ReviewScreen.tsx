// src/screens/ReviewScreen.tsx
import React, { useEffect, useState, useCallback } from "react";
import { View, Text, TextInput, Button, Alert, ScrollView } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../App";
import { theme } from "../theme";
import { getLastReviewItems, verifyReview, recordCorrection } from "../api"; // ⬅️ corrige l'import

type Props = NativeStackScreenProps<RootStackParamList, "Review">;

type ReviewItemLoaded = {
  id: number; // id Observation
  Operation?: "Addition" | "Soustraction" | "Multiplication"; // nouveau nom côté DB
  Type?: "Addition" | "Soustraction" | "Multiplication";      // fallback legacy
  Operateur_Un: number;
  Operateur_Deux: number;
};

export default function ReviewScreen({ route, navigation }: Props) {
  const { entrainementId } = route.params;

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [items, setItems] = useState<ReviewItemLoaded[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [wrongSet, setWrongSet] = useState<Set<number>>(new Set());

  // Charge les items FAUX de cet entraînement
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setErrorMsg(null);

        const res = await getLastReviewItems(entrainementId);
        const arr: ReviewItemLoaded[] = Array.isArray(res?.items) ? res.items : [];
        setItems(arr);

        // init des champs réponses
        const init: Record<number, string> = {};
        for (const it of arr) init[it.id] = "";
        setAnswers(init);
      } catch (e: any) {
        setErrorMsg(e?.message ?? String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [entrainementId]);

  const onChangeAns = useCallback((id: number, txt: string) => {
    setAnswers((prev) => ({ ...prev, [id]: txt }));
    setWrongSet((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const handleValidateAndMark = useCallback(async () => {
    try {
      setSubmitting(true);
      setErrorMsg(null);

      // Construit tries = [{ id, reponse }]
      const tries = items.map((it) => {
        const v = Number(answers[it.id]);
        return { id: it.id, reponse: Number.isFinite(v) ? v : NaN };
      });

      // Bloque si au moins un champ est vide/non numérique
      const hasEmpty = tries.some((t) => !Number.isFinite(t.reponse));
      if (hasEmpty) {
        Alert.alert("Réponses incomplètes", "Merci de saisir une réponse pour chaque opération.");
        return;
      }

      const res = await verifyReview(entrainementId, tries);

      // Normalisation robuste des IDs erronés
      let wrongIds: number[] = [];

      if (Array.isArray((res as any)?.wrong_ids)) {
        wrongIds = (res as any).wrong_ids.map((x: any) => Number(x)).filter((n: any) => Number.isFinite(n));
      }
      if (wrongIds.length === 0 && Array.isArray((res as any)?.incorrect_sample)) {
        wrongIds = (res as any).incorrect_sample
          .map((x: any) => Number(x?.id))
          .filter((n: any) => Number.isFinite(n));
      }
      if (wrongIds.length === 0 && Array.isArray((res as any)?.missing_ids)) {
        wrongIds = (res as any).missing_ids.map((x: any) => Number(x)).filter((n: any) => Number.isFinite(n));
      }

      const incorrectCount = Number((res as any)?.incorrect ?? 0);
      const missingCount = Number((res as any)?.missing ?? 0);
      if (wrongIds.length === 0 && (incorrectCount > 0 || missingCount > 0)) {
        // dernier filet de sécurité
        wrongIds = items.map((it) => it.id);
      }

      console.log("[review] verify =", JSON.stringify(res), "| wrongIds =", wrongIds);

      if (wrongIds.length === 0) {
        // ✅ tout est correct → on enregistre la correction dans la table Corrections
        try {
          const r = await recordCorrection(entrainementId);
          const attempt = r?.attempt ?? r?.Tentative ?? 1;
          Alert.alert(
            "Bravo 🎉",
            `Toutes les erreurs ont été corrigées.\nTentative de correction n°${attempt}.`,
            [{ text: "OK", onPress: () => navigation.popToTop() }]
          );
        } catch (e: any) {
          // même si l’insert échoue, l’utilisateur a corrigé → on remonte l’info mais on ne bloque pas
          Alert.alert(
            "Corrigé",
            `Erreurs corrigées, mais l’enregistrement dans "Corrections" a échoué: ${e?.message ?? e}`,
            [{ text: "OK", onPress: () => navigation.popToTop() }]
          );
        }
        return;
      }

      // Sinon : met en évidence les items incorrects
      setWrongSet(new Set(wrongIds));
      Alert.alert(
        "Encore des erreurs",
        `${wrongIds.length} réponse${wrongIds.length > 1 ? "s" : ""} incorrecte${wrongIds.length > 1 ? "s" : ""}. Corrige-les pour valider.`
      );
    } catch (e: any) {
      setErrorMsg(e?.message ?? String(e));
    } finally {
      setSubmitting(false);
    }
  }, [items, answers, entrainementId, navigation]);

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg }}>
        <Text style={{ color: theme.colors.text }}>Chargement…</Text>
      </View>
    );
  }

  return (
    <ScrollView style={{ flex: 1, padding: 16, backgroundColor: theme.colors.bg }} contentContainerStyle={{ gap: 12 }}>
      <Text style={{ color: theme.colors.text, fontSize: 22, fontWeight: "800", marginBottom: 8 }}>
        Révision des erreurs
      </Text>

      {items.map((it) => {
        const opName = it.Operation || it.Type; // clé correcte affichage
        const label =
          opName === "Addition"
            ? `${it.Operateur_Un} + ${it.Operateur_Deux}`
            : opName === "Soustraction"
            ? `${it.Operateur_Un} - ${it.Operateur_Deux}`
            : `${it.Operateur_Un} × ${it.Operateur_Deux}`;

        const isWrong = wrongSet.has(it.id);

        return (
          <View
            key={it.id}
            style={{
              backgroundColor: theme.colors.card,
              borderRadius: 12,
              padding: 16,
              borderWidth: 1,
              borderColor: isWrong ? theme.colors.danger : theme.colors.border,
            }}
          >
            <Text style={{ color: theme.colors.text, fontWeight: "700", marginBottom: 6 }}>
              {opName ?? "Opération"}
            </Text>
            <Text style={{ color: theme.colors.text, fontSize: 18, marginBottom: 10 }}>{label}</Text>

            <TextInput
              value={answers[it.id]}
              onChangeText={(t) => onChangeAns(it.id, t)}
              keyboardType="numeric"
              placeholder="Ta réponse"
              placeholderTextColor={theme.colors.subtext}
              returnKeyType="done"
              style={{
                borderWidth: 1,
                borderColor: isWrong ? theme.colors.danger : theme.colors.border,
                color: theme.colors.text,
                borderRadius: 8,
                padding: 12,
              }}
            />
          </View>
        );
      })}

      {errorMsg && <Text style={{ color: theme.colors.danger }}>{errorMsg}</Text>}

      <Button
        title={submitting ? "Vérification…" : "Valider et marquer l'entraînement"}
        onPress={handleValidateAndMark}
        disabled={submitting || items.length === 0}
      />
    </ScrollView>
  );
}

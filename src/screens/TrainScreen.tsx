// src/screens/TrainScreen.tsx
import React, { useEffect, useRef, useState, useCallback } from "react";
import { View, Text, ActivityIndicator, Button } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList, ReviewItem } from "../../App";
import { useAuth } from "../auth";
import {
  startEntrainementMixte,
  genererExercicesMixte,
  postObservationsBatch,
  type ObservationIn,
} from "../api";
import Timer from "../components/Timer";
import { theme } from "../theme";
import Calculator from "../components/Calculator";

type Props = NativeStackScreenProps<RootStackParamList, "Train">;

export default function TrainScreen({ route, navigation }: Props) {
  const { volume } = route.params;

  const { authUid } = useAuth();
  const [state, setState] = useState<"loading" | "ready" | "posting">("loading");
  const [entrainementId, setEntrainementId] = useState<number | null>(null);
  const entrainementIdRef = useRef<number | null>(null);
  const [exos, setExos] = useState<any[]>([]);
  const [i, setI] = useState(0);
  const [answer, setAnswer] = useState("");
  const [score, setScore] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  const startRef = useRef<number>(Date.now());
  const nextTick = () => (startRef.current = Date.now());

  const obsBuf = useRef<ObservationIn[]>([]);
  const mistakesRef = useRef<ReviewItem[]>([]);

  useEffect(() => {
    (async () => {
      try {
        setErr(null);
        setState("loading");

        if (!authUid) {
          setErr("Vous n'êtes pas connecté.");
          setState("ready");
          return;
        }

        const start = await startEntrainementMixte(volume);
        const eid = start?.entrainement_id ?? null;
        entrainementIdRef.current = eid;
        setEntrainementId(eid);

        const g = await genererExercicesMixte(volume);
        setExos(Array.isArray(g?.exercices) ? g.exercices : []);
        nextTick();
      } catch (e: any) {
        setErr(e?.message ?? String(e));
      } finally {
        setState("ready");
      }
    })();
  }, [volume, authUid]);

  const validate = useCallback(() => {
    const cur = exos[i];
    const eid = entrainementIdRef.current;

    if (!cur) return;
    if (eid == null) {
      setErr("Identifiant d'entraînement indisponible. Réessaie.");
      return;
    }

    const elapsed = Math.max(0, Math.round((Date.now() - startRef.current) / 1000));
    const repNum = Number(answer);
    const rep = Number.isFinite(repNum) ? repNum : NaN;

    const solApi: number | undefined = (cur as any).Solution;
    const expected =
      solApi != null
        ? Number(solApi)
        : cur.Type === "Addition"
        ? Number(cur.Operateur_Un) + Number(cur.Operateur_Deux)
        : cur.Type === "Soustraction"
        ? Number(cur.Operateur_Un) - Number(cur.Operateur_Deux)
        : Number(cur.Operateur_Un) * Number(cur.Operateur_Deux);

    const correct = Number.isFinite(rep) && Number.isFinite(expected) && rep === expected;

    obsBuf.current.push({
      Entrainement_Id: eid,
      Parcours_Id: cur.Parcours_Id,
      Operateur_Un: cur.Operateur_Un,
      Operateur_Deux: cur.Operateur_Deux,
      Operation: cur.Type,
      Proposition: Number.isFinite(rep) ? rep : 0,
      Temps_Seconds: elapsed,
      Correction: "NON",
    });

    if (correct) {
      setScore((s) => s + 1);
    } else {
      mistakesRef.current.push({
        operation: cur.Operation,
        type: cur.Type,
        parcoursId: cur.Parcours_Id,
        expected,
        userAnswer: Number.isFinite(rep) ? rep : NaN,
        operateurUn: cur.Operateur_Un,
        operateurDeux: cur.Operateur_Deux,
      });
    }

    setAnswer("");

    if (i + 1 < exos.length) {
      setI((k) => k + 1);
      nextTick();
    } else {
      (async () => {
        try {
          setState("posting");
          await postObservationsBatch(obsBuf.current);
        } catch (e: any) {
          setErr(`Erreur envoi résultats: ${e?.message ?? e}`);
        } finally {
          setState("ready");
          navigation.replace("Result", {
            type: "Addition", // (non utilisé en mode mixte)
            entrainementId: eid!,
            parcoursId: 0,
            score,
            total: exos.length,
            mistakes: mistakesRef.current,
          });
        }
      })();
    }
  }, [i, exos, answer, score, navigation]);

  const current = exos[i];

  if (state === "loading") {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: theme.colors.bg }}>
        <ActivityIndicator />
        <Text style={{ color: theme.colors.text }}>Préparation de la session…</Text>
      </View>
    );
  }

  if (!exos.length) {
    return (
      <View style={{ flex: 1, padding: 16, gap: 8, backgroundColor: theme.colors.bg }}>
        <Text style={{ color: theme.colors.text }}>Aucun exercice chargé.</Text>
        {err && <Text style={{ color: theme.colors.danger }}>{err}</Text>}
        <Button title="Revenir" onPress={() => navigation.goBack()} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, padding: 16, gap: 16, backgroundColor: theme.colors.bg }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
        <Text style={{ color: theme.colors.text, fontSize: 18, fontWeight: "700" }}>
          Mixte — {i + 1}/{exos.length}
        </Text>
        <Timer keySeed={i} />
      </View>

      <View style={{ backgroundColor: theme.colors.card, borderRadius: 10, padding: 16, borderWidth: 1, borderColor: theme.colors.border }}>
        <Text style={{ color: theme.colors.text, fontSize: 14, textAlign: "center", opacity: 0.8, marginBottom: 6 }}>
          {current.Type}
        </Text>
        <Text style={{ color: theme.colors.text, fontSize: 32, textAlign: "center" }}>
          {current.Operation}
        </Text>
      </View>

      {/* 🔢 Calculette custom — occupe tout l'espace restant, validation via ✅ */}
      <Calculator
        style={{ flex: 1 }}
        value={answer}
        onChangeText={setAnswer}
        onSubmit={validate}
        disabled={state === "posting"}

        // ✅ Active les pièges + fournis l’index courant
        currentIndex={i}
        destabilizeEnabled={true}

        // (tes réglages)
        hideChance={0.20}
        hideRange={{ min: 1, max: 2 }}
        shuffleChance={0.33}
        shuffleRange={{ min: 1, max: 3 }}
      />


      {/* Bouton "Valider" supprimé */}
      {err && <Text style={{ color: theme.colors.danger }}>{err}</Text>}
    </View>
  );
}

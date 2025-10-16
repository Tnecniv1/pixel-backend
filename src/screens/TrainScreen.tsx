import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  View,
  Text,
  ActivityIndicator,
  Button,
  StyleSheet,
  Platform,
  Dimensions,
  Modal,
} from "react-native";
import Timer from "../components/Timer";
import Calculator from "../components/Calculator";
import { theme } from "../theme";
import { useAuth } from "../auth";
import {
  startEntrainementMixte,
  genererExercicesMixte,
  postObservationsBatch,
  getPixelState,          // ← on importe la même API que sur HomeScreen
  type ObservationIn,
} from "../api";
import BigPixel from "../components/BigPixel";

const { width: W, height: H } = Dimensions.get("window");

// Layout (inchangé)
const PAD_W = Math.min(W * 0.8, 350);
const PAD_H_MAX = Math.round(H * 0.52);

// Animation (lente et lisible)
const HEADSTART_MS = 90; // pause pour lire le score
const STEP_MS = 90;       // 200ms par pixel (±30 ≈ 6s)
const END_PAUSE_MS = 400;  // souffle avant redirection

export default function TrainScreen(props: any) {
  const volume: number = props?.route?.params?.volume ?? 30;

  const navigation = props?.navigation;
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
  const mistakesRef = useRef<
    {
      operation: string;
      type: string;
      parcoursId: number;
      expected: number;
      userAnswer: number;
      operateurUn: number;
      operateurDeux: number;
    }[]
  >([]);

  // Overlay d’animation
  const [overlayVisible, setOverlayVisible] = useState(false);
  const [overlayScoreLeft, setOverlayScoreLeft] = useState<number>(0);
  const [overlayLit, setOverlayLit] = useState<number>(0);
  const postPromiseRef = useRef<Promise<void> | null>(null);

  // INIT
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

  // VALIDATE
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

    if (correct) setScore((s) => s + 1);
    else {
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
      // Fin de session : post + récupération du lit actuel + overlay
      (async () => {
        try {
          setState("posting");
          postPromiseRef.current = postObservationsBatch(obsBuf.current);
        } catch (e: any) {
          setErr(`Erreur envoi résultats: ${e?.message ?? e}`);
        } finally {
          // 1) on lit le lit actuel (comme sur HomeScreen)
          let baseLit = 0;
          try {
            const data = await getPixelState();
            baseLit = Number(data?.lit) || 0;
          } catch {
            baseLit = 0;
          }

          // 2) on démarre l’overlay à partir de ce lit réel
          const delta = Math.max(-30, Math.min(30, Math.trunc(score)));
          setOverlayLit(baseLit);
          setOverlayScoreLeft(delta);
          setOverlayVisible(true);
        }
      })();
    }
  }, [i, exos, answer, score]);

  // Animation + redirection
  useEffect(() => {
    if (!overlayVisible) return;
    let cancelled = false;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

    const run = async () => {
      await sleep(HEADSTART_MS);

      let cur = overlayLit;
      let left = overlayScoreLeft;

      while (!cancelled && left !== 0) {
        const dir = left > 0 ? +1 : -1;
        cur = Math.max(0, cur + dir);
        left = left - dir;
        setOverlayLit(cur);
        setOverlayScoreLeft(left);
        await sleep(STEP_MS);
      }

      if (cancelled) return;

      await sleep(END_PAUSE_MS);
      try {
        await postPromiseRef.current;
      } catch {}
      setState("ready");
      setOverlayVisible(false);

      navigation?.replace("Result", {
        type: "Addition",
        entrainementId: entrainementIdRef.current!,
        parcoursId: 0,
        score,
        total: exos.length,
        mistakes: mistakesRef.current,
      });
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [overlayVisible, overlayLit, overlayScoreLeft, exos.length, navigation]);

  // UI
  const current = exos[i];

  if (state === "loading") {
    return (
      <View style={styles.loading}>
        <ActivityIndicator />
        <Text style={styles.loadingText}>Préparation de la session…</Text>
      </View>
    );
  }

  if (!exos.length) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyText}>Aucun exercice chargé.</Text>
        {err && <Text style={styles.errorText}>{err}</Text>}
        <Button title="Revenir" onPress={() => navigation?.goBack?.()} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* En-tête */}
      <View style={styles.header}>
        <Text style={styles.modeTitle}>Mixte — {i + 1}/{exos.length}</Text>
        <Timer keySeed={i} />
      </View>

      {/* Cadre opération */}
      <View style={styles.operationBox}>
        <Text style={styles.operationType}>{current?.Type}</Text>
        <Text style={styles.operationText}>{current?.Operation}</Text>
      </View>

      {/* Pavé calculatrice */}
      <View style={[styles.padWrapper, { width: PAD_W, maxHeight: PAD_H_MAX, marginTop: 24 }]}>
        <Calculator
          style={{ width: "100%", height: "100%", gap: 24 }}
          value={answer}
          onChangeText={setAnswer}
          onSubmit={validate}
          disabled={state === "posting"}
          currentIndex={i}
          destabilizeEnabled={true}
          hideChance={0.05}
          hideRange={{ min: 1, max: 5 }}
          shuffleChance={0.1}
          shuffleRange={{ min: 1, max: 3 }}
          verticalBias={0.85}
        />
      </View>

      {err && <Text style={styles.errorText}>{err}</Text>}

      {/* OVERLAY : score + BigPixel (mêmes proportions que Home) */}
      <Modal visible={overlayVisible} animationType="fade" transparent>
        <View style={styles.overlayBackdrop}>
          <View style={styles.overlayContainer}>
            <View
              style={[
                styles.scorePill,
                overlayScoreLeft >= 0 ? styles.pos : styles.neg,
              ]}
            >
              <Text style={styles.scoreText}>
                {overlayScoreLeft > 0 ? `+${overlayScoreLeft}` : `${overlayScoreLeft}`}
              </Text>
            </View>

            <BigPixel lit={overlayLit} cols={350} rows={350} size={350} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    gap: 16,
    backgroundColor: theme.colors.bg,
    paddingBottom: 20,
  },
  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.colors.bg,
  },
  loadingText: { color: theme.colors.text, marginTop: 8 },
  empty: { flex: 1, padding: 16, gap: 8, backgroundColor: theme.colors.bg },
  emptyText: { color: theme.colors.text },
  errorText: { color: theme.colors.danger, marginTop: 6 },

  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  modeTitle: { color: theme.colors.text, fontSize: 18, fontWeight: "700" },

  operationBox: {
    alignSelf: "center",
    width: Math.min(W * 0.92, 560),
    backgroundColor: theme.colors.card,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: theme.colors.accent,
    justifyContent: "center",
    alignItems: "center",
    paddingTop: 28,
    paddingBottom: 20,
    paddingHorizontal: 16,
    minHeight: 120,
  },
  operationType: {
    position: "absolute",
    top: 6,
    left: 0,
    right: 0,
    textAlign: "center",
    color: theme.colors.secondary,
    fontSize: 13,
    opacity: 0.85,
  },
  operationText: {
    color: theme.colors.text,
    fontSize: 36,
    fontWeight: "700",
    textAlign: "center",
    lineHeight: 40,
    fontFamily: Platform.select({
      ios: "Menlo",
      android: "monospace",
      default: "monospace",
    }),
  },

  padWrapper: {
    alignSelf: "center",
    borderRadius: 12,
    overflow: "hidden",
  },

  // Overlay
  overlayBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  overlayContainer: {
    width: "100%",
    maxWidth: 420,
    alignItems: "center",
  },
  scorePill: {
    position: "absolute",
    right: 8,
    top: 8,
    zIndex: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  scoreText: { color: "white", fontWeight: "800", fontSize: 18 },
  pos: { backgroundColor: "#16A34A" },
  neg: { backgroundColor: "#DC2626" },
});

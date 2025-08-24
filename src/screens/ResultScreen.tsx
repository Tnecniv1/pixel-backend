// src/screens/ResultScreen.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  ActivityIndicator,
  Alert,
  ScrollView,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../App";
import { theme } from "../theme";
import Constants from "expo-constants";
import { supabase } from "../supabase";

/* =========================================================================
   Config
   ========================================================================= */
const API_BASE: string =
  // @ts-ignore — suivant Expo SDK
  (Constants?.expoConfig?.extra?.API_BASE_URL as string) ||
  // @ts-ignore — fallback anciens SDK
  (Constants?.manifest?.extra?.API_BASE_URL as string) ||
  "http://192.168.1.16:8000";

/* =========================================================================
   Types
   ========================================================================= */
type Props = NativeStackScreenProps<RootStackParamList, "Result">;

type OperationKey = "Addition" | "Soustraction" | "Multiplication";

type OperationMetrics = {
  successRate: number;  // 0..100
  avgTimeSec: number;   // secondes
  errorMargin: number;  // moyenne (ex: % ou valeur brute selon ton modèle)
  count: number;
  barTime?: number;     // 0..1 (pour la jauge "Temps")
};

type MetricsResponse = Record<OperationKey, OperationMetrics>;

/** Schéma **réel** des colonnes Observations (confirmé côté backend) */
type ObsRow = {
  Operation: string | null;          // "Addition" | "Soustraction" | "Multiplication" | mixte...
  Etat: string | null;               // "VRAI" | "FAUX"
  Proposition: number | string | null;
  Solution: number | string | null;
  Temps_Seconds: number | string | null;
  Marge_Erreur: number | string | null;
  Score: number | string | null;     // ±1
  Entrainement_Id?: number | string | null;
};

/* =========================================================================
   Helpers
   ========================================================================= */
const toNum = (v: any): number | null => {
  if (v === null || v === undefined) return null;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : null;
};

const normOp = (raw: unknown): OperationKey | null => {
  const o = String(raw ?? "").trim().toLowerCase();
  if (!o) return null;
  if (o.startsWith("add")) return "Addition";
  if (o.startsWith("sou") || o.startsWith("sub")) return "Soustraction";
  if (o.startsWith("mul")) return "Multiplication";
  return null;
};

const isCorrect = (r: ObsRow): boolean => {
  const etat = String(r.Etat ?? "").trim().toUpperCase();
  if (etat === "VRAI") return true;
  if (etat === "FAUX") return false;
  // filet de sécurité si Etat est vide : compare propositions/solutions
  return String(r.Proposition ?? "") === String(r.Solution ?? "!!__MISS__");
};

const sumSessionScore = (rows: ObsRow[]): number =>
  rows.reduce((acc, r) => acc + (toNum(r.Score) ?? 0), 0);

const computeMetrics = (rows: ObsRow[]): MetricsResponse => {
  const buckets: Record<OperationKey, ObsRow[]> = {
    Addition: [],
    Soustraction: [],
    Multiplication: [],
  };
  for (const r of rows) {
    const k = normOp(r.Operation);
    if (!k) continue;
    buckets[k].push(r);
  }

  const computeOne = (items: ObsRow[]): OperationMetrics => {
    const total = items.length;
    if (!total) return { successRate: 0, avgTimeSec: 0, errorMargin: 0, count: 0 };

    const ok = items.reduce((acc, it) => acc + (isCorrect(it) ? 1 : 0), 0);

    const times = items
      .map((x) => toNum(x.Temps_Seconds))
      .filter((n): n is number => n !== null);

    const errs = items
      .map((x) => toNum(x.Marge_Erreur))
      .filter((n): n is number => n !== null);

    const successRate = Math.round((ok / total) * 100);
    const avgTimeSec = times.length ? times.reduce((a, b) => a + b, 0) / times.length : 0;
    const errorMargin = errs.length ? errs.reduce((a, b) => a + b, 0) / errs.length : 0;

    return { successRate, avgTimeSec, errorMargin, count: total };
  };

  const m: MetricsResponse = {
    Addition: computeOne(buckets.Addition),
    Soustraction: computeOne(buckets.Soustraction),
    Multiplication: computeOne(buckets.Multiplication),
  };

  // Normalisation de la barre "Temps" (0..1)
  const maxAvg = Math.max(
    m.Addition.avgTimeSec,
    m.Soustraction.avgTimeSec,
    m.Multiplication.avgTimeSec,
    1
  );
  m.Addition.barTime = m.Addition.avgTimeSec / maxAvg;
  m.Soustraction.barTime = m.Soustraction.avgTimeSec / maxAvg;
  m.Multiplication.barTime = m.Multiplication.avgTimeSec / maxAvg;

  return m;
};

const normalizeBarTimes = (m: MetricsResponse): MetricsResponse => {
  const maxAvg = Math.max(
    m.Addition.avgTimeSec,
    m.Soustraction.avgTimeSec,
    m.Multiplication.avgTimeSec,
    1
  );
  return {
    Addition: { ...m.Addition, barTime: m.Addition.avgTimeSec / maxAvg },
    Soustraction: { ...m.Soustraction, barTime: m.Soustraction.avgTimeSec / maxAvg },
    Multiplication: { ...m.Multiplication, barTime: m.Multiplication.avgTimeSec / maxAvg },
  };
};

const makeEmptyMetrics = (): MetricsResponse => ({
  Addition: { successRate: 0, avgTimeSec: 0, errorMargin: 0, count: 0, barTime: 0 },
  Soustraction: { successRate: 0, avgTimeSec: 0, errorMargin: 0, count: 0, barTime: 0 },
  Multiplication: { successRate: 0, avgTimeSec: 0, errorMargin: 0, count: 0, barTime: 0 },
});

/* =========================================================================
   UI Components
   ========================================================================= */
const MetricBar = ({
  label,
  valueText,
  progress = 0.5,
}: {
  label: string;
  valueText: string;
  progress?: number; // 0..1
}) => {
  const pct = Math.max(0, Math.min(1, progress));
  return (
    <View style={styles.metricRow}>
      <View style={styles.metricLabelPill}>
        <Text style={styles.metricLabelText}>{label}</Text>
      </View>
      <View style={styles.metricBarContainer}>
        <View style={[styles.metricBarFill, { width: `${pct * 100}%` }]} />
        <View style={styles.metricValuePill}>
          <Text
            style={[
              styles.metricValueText,
              label === "Taux de Réussite" || label === "Marge Erreur"
                ? styles.valueOrange
                : undefined,
            ]}
          >
            {valueText}
          </Text>
        </View>
      </View>
    </View>
  );
};

const OperationCard = ({ title, data }: { title: OperationKey; data: OperationMetrics }) => (
  <View style={styles.card}>
    <Text style={styles.cardTitle}>{title}</Text>

    <MetricBar
      label="Taux de Réussite"
      valueText={`${Math.round(data.successRate)} %`}
      progress={data.successRate / 100}
    />
    <MetricBar
      label="Temps"
      valueText={`${Number(data.avgTimeSec || 0).toFixed(2)} sec`}
      progress={data.barTime ?? 0.5}
    />
    <MetricBar
      label="Marge Erreur"
      valueText={`${Math.round(data.errorMargin || 0)} %`}
      progress={Math.min(1, (data.errorMargin || 0) / 100)}
    />
  </View>
);

/* =========================================================================
   Screen
   ========================================================================= */
export default function ResultScreen({ route, navigation }: Props) {
  const { type, entrainementId, parcoursId, score, total } = route.params;
  const ratio = total > 0 ? Math.round((score / total) * 100) : 0;
  const fallbackSessionScoreText = score >= 0 ? `+${score}` : `${score}`;

  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionScore, setSessionScore] = useState<number | null>(null);

  const ui = useMemo(
    () => (metrics ? normalizeBarTimes(metrics) : makeEmptyMetrics()),
    [metrics]
  );

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);

      // 🔒 Lecture directe Supabase — en ne sélectionnant QUE les colonnes réelles
      const { data, error } = await supabase
        .from("Observations")
        .select(`
          Operation,
          Etat, Proposition, Solution,
          Temps_Seconds, Marge_Erreur,
          Score
        `)
        .eq("Entrainement_Id", entrainementId);

      if (!alive) return;

      if (error) {
        console.log("[ResultScreen] Supabase error", error.message);
        setLoading(false);
        setError("Aucune donnée pour cet entraînement.");
        setMetrics(null);
        setSessionScore(null);
        return;
      }

      const rows = Array.isArray(data) ? (data as ObsRow[]) : [];
      setMetrics(computeMetrics(rows));
      setSessionScore(sumSessionScore(rows)); // somme des ±1 de CET entraînement
      setLoading(false);
    })();

    return () => {
      alive = false;
    };
  }, [entrainementId]);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Score pill */}
        <View style={styles.scorePill}>
          <View style={styles.scoreLeft}>
            <Text style={styles.scoreLeftText}>Score</Text>
          </View>
          <View style={styles.scoreRight}>
            <Text
              style={[
                styles.scoreRightText,
                typeof sessionScore === "number"
                  ? { color: sessionScore >= 0 ? "#16a34a" : "#dc2626" }
                  : null,
              ]}
            >
              {typeof sessionScore === "number"
                ? sessionScore >= 0
                  ? `+${sessionScore}`
                  : `${sessionScore}`
                : fallbackSessionScoreText}
            </Text>
          </View>
        </View>

        {/* Mini résumé session */}
        <View style={styles.sessionCard}>
          <Text style={styles.sessionText}>
            {score} / {total} ({ratio}%)
          </Text>
          <Text style={styles.sessionSub}>
            Parcours #{parcoursId} — Entraînement #{entrainementId} — {type}
          </Text>
        </View>

        {/* Datas */}
        {loading ? (
          <View style={{ alignItems: "center", paddingVertical: 12 }}>
            <ActivityIndicator />
            <Text style={{ color: theme.colors.subtext, marginTop: 6 }}>
              Chargement des métriques…
            </Text>
          </View>
        ) : error ? (
          <TouchableOpacity
            onPress={() => Alert.alert("Erreur", error)}
            style={[styles.card, { alignItems: "center" }]}
            activeOpacity={0.8}
          >
            <Text style={{ color: theme.colors.text }}>{error}</Text>
          </TouchableOpacity>
        ) : (
          <View>
            <View style={styles.opCard}>
              <OperationCard title="Addition" data={ui.Addition} />
            </View>

            <View style={styles.opCard}>
              <OperationCard title="Soustraction" data={ui.Soustraction} />
            </View>

            {/* pas de marge après la dernière carte */}
            <OperationCard title="Multiplication" data={ui.Multiplication} />
          </View>
        )}

        {/* Boutons bas */}
        <View style={styles.buttonRow}>
          <TouchableOpacity
            onPress={() => navigation.popToTop()}
            activeOpacity={0.8}
            style={styles.btnHome}
          >
            <Text style={styles.btnHomeText}>Accueil</Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => navigation.navigate("Review", { type, entrainementId })}
            activeOpacity={0.9}
            style={styles.btnCorrection}
          >
            <Text style={styles.btnCorrectionText}>CORRECTION</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

/* =========================================================================
   Styles
   ========================================================================= */
const COLORS = {
  bg: theme.colors.bg ?? "#F8F4F1",
  card: "#EDEDED",
  pillPurple: "#D36AD6",
  pillPurpleDark: "#C357C6",
  white: "#FFFFFF",
  grayText: "#4C4C4C",
  blueTitle: "#1F3554",
  greenText: "#37B26C",
  orangeValue: "#F5A300",
  orangeBtn: "#FFB25E",
  shadow: "rgba(0,0,0,0.08)",
};
const CAP_RADIUS = 20;

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  scrollContent: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 32, gap: 16 },

  // Score pill
  scorePill: {
    flexDirection: "row",
    borderRadius: CAP_RADIUS,
    overflow: "hidden",
    height: 48,
    backgroundColor: "#D9D9D9",
  },
  scoreLeft: {
    backgroundColor: COLORS.pillPurple,
    paddingHorizontal: 22,
    alignItems: "center",
    justifyContent: "center",
    borderTopLeftRadius: CAP_RADIUS,
    borderBottomLeftRadius: CAP_RADIUS,
  },
  scoreLeftText: { color: COLORS.white, fontWeight: "700", fontSize: 18 },
  scoreRight: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderTopRightRadius: CAP_RADIUS,
    borderBottomRightRadius: CAP_RADIUS,
  },
  scoreRightText: { color: COLORS.greenText, fontWeight: "800", fontSize: 20 },

  // Session mini-card
  sessionCard: {
    backgroundColor: COLORS.card,
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  sessionText: { color: theme.colors.text, fontSize: 18, textAlign: "center" },
  sessionSub: { color: theme.colors.subtext, textAlign: "center", marginTop: 4, fontSize: 12 },

  // Cards
  card: {
    backgroundColor: COLORS.card,
    borderRadius: 18,
    paddingVertical: 14,
    paddingHorizontal: 14,
    shadowColor: COLORS.shadow,
    shadowOpacity: 1,
    shadowOffset: { width: 0, height: 4 },
    shadowRadius: 10,
    elevation: 2,
    gap: 10,
  },
  cardTitle: {
    textAlign: "center",
    color: COLORS.blueTitle,
    fontWeight: "800",
    fontSize: 18,
    marginBottom: 2,
  },

  opCard: { marginBottom: 16 }, // 16 → augmente si tu veux plus d’air (ex: 20 ou 24)

  // Metric row
  metricRow: { flexDirection: "row", alignItems: "center", gap: 10 },
  metricLabelPill: {
    backgroundColor: COLORS.pillPurple,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    minWidth: 120,
    alignItems: "center",
    justifyContent: "center",
  },
  metricLabelText: { color: COLORS.white, fontWeight: "700", fontSize: 12 },
  metricBarContainer: {
    flex: 1,
    height: 28,
    backgroundColor: COLORS.white,
    borderRadius: 999,
    overflow: "hidden",
    justifyContent: "center",
  },
  metricBarFill: {
    ...StyleSheet.absoluteFillObject,
    width: "50%",
    backgroundColor: COLORS.pillPurpleDark,
    borderRadius: 999,
  },
  metricValuePill: {
    alignSelf: "flex-end",
    marginRight: 8,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: COLORS.white,
  },
  metricValueText: { fontWeight: "800", fontSize: 12, color: COLORS.grayText },
  valueOrange: { color: COLORS.orangeValue },

  // Bottom buttons
  buttonRow: {
    marginTop: 6,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
  },
  btnHome: {
    flex: 1,
    height: 46,
    borderRadius: 999,
    backgroundColor: "#D7D7D7",
    alignItems: "center",
    justifyContent: "center",
  },
  btnHomeText: { color: COLORS.blueTitle, fontWeight: "700", fontSize: 16 },
  btnCorrection: {
    flex: 1,
    height: 46,
    borderRadius: 999,
    backgroundColor: COLORS.orangeBtn,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: COLORS.shadow,
    shadowOpacity: 1,
    shadowOffset: { width: 0, height: 6 },
    shadowRadius: 10,
    elevation: 3,
  },
  btnCorrectionText: { color: "#171717", fontWeight: "900", fontSize: 16, letterSpacing: 0.2 },
});


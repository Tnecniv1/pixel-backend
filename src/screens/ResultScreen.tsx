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
  successRate: number;
  avgTimeSec: number;
  errorMargin: number;
  count: number;
  barTime?: number; // 0..1
};

type MetricsResponse = Record<OperationKey, OperationMetrics>;

type ObsRow = {
  Operation: string | null;
  Etat: string | null;
  Proposition: number | string | null;
  Solution: number | string | null;
  Temps_Seconds: number | string | null;
  Marge_Erreur: number | string | null;
  Score: number | string | null;
  Entrainement_Id?: number | string | null;
};

/* =========================================================================
   Helpers (logique inchangée)
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
    const times = items.map(x => toNum(x.Temps_Seconds)).filter((n): n is number => n !== null);
    const errs = items.map(x => toNum(x.Marge_Erreur)).filter((n): n is number => n !== null);

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

  const maxAvg = Math.max(m.Addition.avgTimeSec, m.Soustraction.avgTimeSec, m.Multiplication.avgTimeSec, 1);
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
   UI — composants visuels
   ========================================================================= */

// En-tête de section
const SectionHeader = ({ title }: { title: string }) => (
  <View style={styles.sectionHeader}>
    <Text style={styles.sectionHeaderText}>{title}</Text>
  </View>
);

// Stat row : barre haute + pastille valeur à droite
const StatRow = ({
  icon,
  label,
  valueText,
  progress = 0.5,
  emphasize = false,
}: {
  icon: string;
  label: string;
  valueText: string;
  progress?: number; // 0..1
  emphasize?: boolean;
}) => {
  const pct = Math.max(0, Math.min(1, progress));
  return (
    <View style={styles.statRow}>
      <View style={styles.statLeft}>
        <Text style={styles.statIcon}>{icon}</Text>
        <Text style={styles.statLabel} numberOfLines={1}>
          {label}
        </Text>
      </View>

      <View style={styles.statRight}>
        <View style={styles.statTrack}>
          <View style={[styles.statFill, { width: `${pct * 100}%` }]} />
        </View>
        <View style={[styles.statChip, emphasize && styles.statChipEmph]}>
          <Text style={[styles.statChipText, emphasize && styles.statChipTextEmph]}>
            {valueText}
          </Text>
        </View>
      </View>
    </View>
  );
};

const OperationCard = ({ title, data }: { title: OperationKey; data: OperationMetrics }) => (
  <View style={styles.card}>
    <SectionHeader title={title} />
    <View style={styles.statsGrid}>
      <StatRow
        icon="🎯"
        label="Taux de réussite"
        valueText={`${Math.round(data.successRate)} %`}
        progress={data.successRate / 100}
        emphasize
      />
      <StatRow
        icon="⏱️"
        label="Temps moyen"
        valueText={`${Number(data.avgTimeSec || 0).toFixed(2)} s`}
        progress={data.barTime ?? 0.5}
      />
      <StatRow
        icon="⚡"
        label="Marge d’erreur"
        valueText={`${Math.round(data.errorMargin || 0)} %`}
        progress={Math.min(1, (data.errorMargin || 0) / 100)}
      />
    </View>
  </View>
);

/* =========================================================================
   Screen
   ========================================================================= */
export default function ResultScreen({ route, navigation }: Props) {
  const { type, entrainementId, parcoursId, score } = route.params;

  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessionScore, setSessionScore] = useState<number | null>(null);

  const ui = useMemo(() => (metrics ? normalizeBarTimes(metrics) : makeEmptyMetrics()), [metrics]);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);

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
      setSessionScore(sumSessionScore(rows));
      setLoading(false);
    })();

    return () => {
      alive = false;
    };
  }, [entrainementId]);

  const effectiveScore = sessionScore ?? score; // ce qui s’affiche en haut

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        {/* HEADER : Score seul, centré */}
        <View style={styles.scoreOnlyCard}>
          <Text
            style={[
              styles.bigScore,
              typeof effectiveScore === "number" && effectiveScore < 0
                ? styles.bigScoreNeg
                : styles.bigScorePos,
            ]}
          >
            {typeof effectiveScore === "number"
              ? effectiveScore >= 0
                ? `+${effectiveScore}`
                : `${effectiveScore}`
              : "…"}
          </Text>
        </View>

        {/* CARTES — zone centrale compacte */}
        <View style={styles.cardsArea}>
          {loading ? (
            <View style={{ alignItems: "center", paddingVertical: 8 }}>
              <ActivityIndicator />
              <Text style={{ color: theme.colors.subtext, marginTop: 6 }}>Chargement…</Text>
            </View>
          ) : error ? (
            <TouchableOpacity
              onPress={() => Alert.alert("Erreur", error)}
              style={[styles.card, { alignItems: "center" }]}
              activeOpacity={0.8}
            >
              <Text style={{ color: COLORS.textMain }}>{error}</Text>
            </TouchableOpacity>
          ) : (
            <>
              <OperationCard title="Addition" data={ui.Addition} />
              <OperationCard title="Soustraction" data={ui.Soustraction} />
              <OperationCard title="Multiplication" data={ui.Multiplication} />
            </>
          )}
        </View>

        {/* FOOTER FIXE */}
        <View style={styles.footer}>
          <TouchableOpacity
            onPress={() => navigation.popToTop()}
            activeOpacity={0.85}
            style={styles.btnGhost}
          >
            <Text style={styles.btnGhostText}>Accueil</Text>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => navigation.navigate("Review", { type, entrainementId })}
            activeOpacity={0.9}
            style={styles.btnPrimary}
          >
            <Text style={styles.btnPrimaryText}>CORRECTION</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

/* =========================================================================
   Styles
   ========================================================================= */
const COLORS = {
  bg: "#0B0C1A",
  layer: "rgba(26,27,43,0.92)",
  layerBorder: "#27283A",
  white: "#FFFFFF",
  textMain: "#E8EAF6",
  title: "#E6E8FF",
  purpleSoft: "rgba(122,90,248,0.28)",
  track: "rgba(255,255,255,0.06)",
  trackBorder: "rgba(255,255,255,0.08)",
  green: "#4ADE80",
  red: "#F87171",
  orange: "#F59E0B",
  shadow: "rgba(0,0,0,0.35)",
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },

  container: {
    flex: 1,
    paddingHorizontal: 14,
    paddingTop: 8,
    paddingBottom: 10,
  },

  /* ----- Score seul, centré ----- */
  scoreOnlyCard: {
    backgroundColor: COLORS.layer,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.layerBorder,
    height: 64,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 6,
  },
  bigScore: { fontSize: 28, fontWeight: "900", letterSpacing: 0.2 },
  bigScorePos: { color: COLORS.green },
  bigScoreNeg: { color: COLORS.red },

  /* ----- Zone cartes compacte ----- */
  cardsArea: {
    flex: 1,
    justifyContent: "space-between",
    gap: 6,
  },

  card: {
    backgroundColor: COLORS.layer,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.layerBorder,
    shadowColor: COLORS.shadow,
    shadowOpacity: 0.35,
    shadowOffset: { width: 0, height: 8 },
    shadowRadius: 12,
    elevation: 2,
    padding: 8,
    gap: 6,
  },

  sectionHeader: {
    alignSelf: "center",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "rgba(122,90,248,0.16)",
    borderWidth: 1,
    borderColor: COLORS.purpleSoft,
    marginBottom: 2,
  },
  sectionHeaderText: { color: COLORS.title, fontWeight: "900", fontSize: 14 },

  statsGrid: { gap: 8 },

  /* ----- Stat rows (barres hautes + chip à droite) ----- */
  statRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  statLeft: { width: 132, flexDirection: "row", alignItems: "center", gap: 6 },
  statIcon: { fontSize: 14 },
  statLabel: { color: COLORS.title, fontWeight: "700", fontSize: 12 },

  statRight: { flex: 1, flexDirection: "row", alignItems: "center", gap: 8 },
  statTrack: {
    flex: 1,
    height: 28,
    borderRadius: 999,
    backgroundColor: COLORS.track,
    borderWidth: 1,
    borderColor: COLORS.trackBorder,
    overflow: "hidden",
  },
  statFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: COLORS.purpleSoft,
  },
  statChip: {
    minWidth: 56,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: "rgba(17,17,17,0.45)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  statChipText: { color: COLORS.textMain, fontWeight: "900", fontSize: 12.5 },
  statChipEmph: { backgroundColor: "rgba(245,158,11,0.18)", borderColor: "rgba(245,158,11,0.35)" },
  statChipTextEmph: { color: COLORS.orange },

  /* ----- Footer fixe ----- */
  footer: {
    flexDirection: "row",
    gap: 10,
    paddingTop: 8,
  },
  btnGhost: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: COLORS.layerBorder,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
  btnGhostText: { color: COLORS.title, fontWeight: "900", fontSize: 15 },

  btnPrimary: {
    flex: 1,
    height: 44,
    borderRadius: 999,
    backgroundColor: "#FFB86B",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: COLORS.shadow,
    shadowOpacity: 0.5,
    shadowOffset: { width: 0, height: 8 },
    shadowRadius: 12,
  },
  btnPrimaryText: { color: "#171717", fontWeight: "900", fontSize: 15, letterSpacing: 0.2 },
});

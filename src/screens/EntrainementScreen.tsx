// src/screens/EntrainementScreen.tsx
import React, { useEffect, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import { AntDesign } from "@expo/vector-icons";
import Constants from "expo-constants";
import { supabase } from "../supabase";
import { theme } from "../theme";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../App";

type Props = NativeStackScreenProps<RootStackParamList, "Train">;

type Position = {
  niveau: number;
  parcours_id: number;
  taux?: number;             // 0..1
  type_evolution?: string;   // "progression" | "régression" | "stagnation"
  date?: string;
  critere?: number;          // ex. 20
  restantes?: number;        // obs restantes avant prochain test critique
};

type Positions = {
  Addition?: Position | null;
  Soustraction?: Position | null;
  Multiplication?: Position | null;
  score_points?: number | null; // somme des points (Observations.Score)
  score_global?: number | null; // 0..1 si tu veux encore t’en servir ailleurs
};

const API_BASE: string =
  // @ts-ignore Expo SDK 50+
  (Constants?.expoConfig?.extra?.API_BASE_URL as string) ||
  // @ts-ignore Expo SDK < 50
  (Constants?.manifest?.extra?.API_BASE_URL as string) ||
  "http://192.168.1.16:8000";

/* =========================================================================
   ÉCRAN
   ========================================================================= */
export default function EntrainementScreen({ navigation }: Props) {
  const [positions, setPositions] = useState<Positions | null>(null);
  const [loading, setLoading] = useState(false);
  const [volume, setVolume] = useState<10 | 50 | 100>(10);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const { data: sessionData } = await supabase.auth.getSession();
        const token = sessionData?.session?.access_token;

        // ⚠️ si besoin, rends le parcoursId dynamique
        const url = `${API_BASE}/parcours/positions_currentes?parcours_id=1`;

        const res = await fetch(url, {
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`HTTP ${res.status} ${txt}`);
        }
        const data = (await res.json()) as Positions;
        if (alive) setPositions(data);
      } catch (e: any) {
        if (alive) Alert.alert("Erreur", e?.message ?? "Impossible de charger les niveaux.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Text style={styles.title}>Préparer l’entraînement</Text>

        {/* === Tableau style maquette === */}
        <PositionsTable positions={positions} loading={loading} />

        {/* === Sélecteur volume === */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Nombre d’opérations</Text>
          <View style={styles.volRow}>
            <VolPill value={100} active={volume === 100} onPress={() => setVolume(100)} />
            <VolPill value={50} active={volume === 50} onPress={() => setVolume(50)} />
            <VolPill value={10} active={volume === 10} onPress={() => setVolume(10)} />
          </View>
        </View>

        {/* === CTA === */}
        <TouchableOpacity
          activeOpacity={0.9}
          style={styles.cta}
          onPress={() => navigation.navigate("Train", { volume })}
        >
          <Text style={styles.ctaText}>CALCULEZ !</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

/* =========================================================================
   COMPOSANTS
   ========================================================================= */

function PositionsTable({
  positions,
  loading,
}: {
  positions: Positions | null;
  loading: boolean;
}) {
  // score en points (entier)
  const scorePoints =
    typeof positions?.score_points === "number" ? positions!.score_points! : null;

  // flèche globale (si au moins une progression -> up ; sinon régression -> down ; sinon flat)
  const evolutions = [
    positions?.Addition?.type_evolution,
    positions?.Soustraction?.type_evolution,
    positions?.Multiplication?.type_evolution,
  ]
    .filter(Boolean)
    .map((x) => String(x).toLowerCase());

  const hasUp = evolutions.includes("progression");
  const hasDown = evolutions.includes("régression") || evolutions.includes("regression");
  const trend: "up" | "down" | "flat" = hasUp ? "up" : hasDown ? "down" : "flat";

  return (
    <View style={styles.tableCard}>
      {/* Header */}
      <View style={styles.tableHeaderRow}>
        <Text style={[styles.th, styles.thLeft]}>OPÉRATIONS</Text>
        <Text style={styles.th}>NIVEAU</Text>
        <Text style={[styles.th, styles.thRight]}>SCORE</Text>
      </View>

      {loading ? (
        <View style={{ padding: 16 }}>
          <ActivityIndicator />
        </View>
      ) : (
        <View style={styles.tableBodyRow}>
          {/* Bloc gauche : Opérations + Niveau (3 lignes) */}
          <View style={styles.leftBlock}>
            <TableLine op="Addition"       pos={positions?.Addition} />
            <View style={styles.rowDivider} />
            <TableLine op="Soustraction"   pos={positions?.Soustraction} />
            <View style={styles.rowDivider} />
            <TableLine op="Multiplication" pos={positions?.Multiplication} />
          </View>

          {/* Bloc droit : SCORE global (points) + flèche */}
          <View style={styles.rightBlock}>
            <View style={[styles.scorePanel, { paddingHorizontal: 14, minWidth: 110 }]}>
              <Text style={[styles.scoreBig, { marginRight: 0 }]}>
                {scorePoints !== null ? scorePoints.toLocaleString("fr-FR") : "--"}
              </Text>
            </View>
            <View
              style={[
                styles.trendBadge,
                trend === "up"
                  ? { backgroundColor: "#2ecc71" }
                  : trend === "down"
                  ? { backgroundColor: "#e74c3c" }
                  : { backgroundColor: "#9CA3AF" },
              ]}
            >
              {trend === "up" && <AntDesign name="arrowup" size={18} color="#fff" />}
              {trend === "down" && <AntDesign name="arrowdown" size={18} color="#fff" />}
              {trend === "flat" && <AntDesign name="minus" size={18} color="#fff" />}
            </View>
          </View>
        </View>
      )}
    </View>
  );
}


function TableLine({ op, pos }: { op: string; pos?: Position | null }) {
  return (
    <View style={styles.bodyRow}>
      {/* Colonne gauche : nom de l’opération */}
      <View style={styles.cellLeft}>
        <Text style={styles.opLabel} numberOfLines={1}>{op}</Text>
      </View>

      {/* Colonne milieu : Niveau + N-restantes */}
      <View style={styles.cellMid}>
        <Text style={styles.levelCell}>Niv {pos?.niveau ?? "--"}</Text>
        {typeof pos?.restantes === "number" && (
          <Text style={styles.subLevelCell}>N-{pos!.restantes}</Text>
        )}
      </View>
    </View>
  );
}

function VolPill({
  value,
  active,
  onPress,
}: {
  value: number;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      style={[
        styles.volPill,
        {
          backgroundColor: active ? COLORS.blue : "#E6E6E6",
          borderColor: active ? COLORS.blueDark : "#d1d5db",
        },
      ]}
    >
      <Text style={[styles.volText, { color: active ? COLORS.blueDark : COLORS.subtext }]}>
        {value}
      </Text>
    </TouchableOpacity>
  );
}

/* =========================================================================
   STYLES
   ========================================================================= */



const COLORS = {
  bg: theme?.colors?.bg ?? "#0E1420", // fond sombre actuel
  text: theme?.colors?.text ?? "#F5F7FB",
  subtext: theme?.colors?.subtext ?? "#9CA3AF",
  card: "#FFFFFF",
  purple: "#D36AD6",
  blue: "#CBE0FF",
  blueDark: "#11283F",
  orange: "#FFB25E",
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  container: { flex: 1, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 24, gap: 16 },
  title: { fontSize: 22, fontWeight: "900", color: COLORS.text, textAlign: "center" },

  card: {
    backgroundColor: COLORS.card,
    borderRadius: 14,
    padding: 14,
    borderWidth: 2,
    borderColor: COLORS.blueDark,
  },
  cardTitle: { color: COLORS.blueDark, fontWeight: "800", marginBottom: 10, fontSize: 16 },

  // --- Tableau (maquette)
  tableCard: {
    backgroundColor: COLORS.card,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: COLORS.blueDark,
    overflow: "hidden",
  },
  tableHeaderRow: {
    flexDirection: "row",
    backgroundColor: COLORS.blue,
    borderBottomWidth: 2,
    borderColor: COLORS.blueDark,
  },
  th: {
    flex: 1,
    textAlign: "center",
    color: COLORS.blueDark,
    fontWeight: "900",
    fontSize: 12,
    paddingVertical: 10,
  },
  thLeft: { flex: 1.4, textAlign: "left", paddingLeft: 14 },
  thRight: { textAlign: "center" },

  tableBodyRow: {
    flexDirection: "row",
  },
  leftBlock: {
    flex: 1.8,
    borderRightWidth: 2,
    borderColor: COLORS.blueDark,
  },
  rightBlock: {
    flex: 1,
    alignItems: "center",
    justifyContent: "space-evenly",
    paddingVertical: 12,
  },

  bodyRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  rowDivider: {
    height: 1.5,
    backgroundColor: "#D1D5DB",
  },

  cellLeft: { flex: 1.2, justifyContent: "center" },
  cellMid: {
    width: 110,
    alignItems: "center",
    justifyContent: "center",
    borderLeftWidth: 1.5,
    borderColor: "#D1D5DB",
  },

  opLabel: { color: COLORS.blueDark, fontWeight: "700" },
  levelCell: { color: COLORS.blueDark, fontWeight: "900", fontSize: 16 },
  levelSub: { fontSize: 11, color: COLORS.subtext, marginTop: 2, fontWeight: "600" },

  scorePanel: {
    minWidth: 88,
    paddingHorizontal: 10,
    height: 44,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: COLORS.blueDark,
    backgroundColor: "#F7F7F7",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  scoreBig: { fontSize: 22, fontWeight: "900", color: COLORS.blueDark },

    subLevelCell: {
    fontSize: 11,
    fontWeight: "600",
    color: COLORS.subtext,
    marginTop: 2,
  },

  trendBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },

  // Volumes
  volRow: { flexDirection: "row", justifyContent: "space-between", gap: 10, marginTop: 8 },
  volPill: {
    flex: 1,
    height: 40,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
  },
  volText: { fontWeight: "800", fontSize: 16 },

  // CTA
  cta: {
    height: 50,
    borderRadius: 999,
    backgroundColor: COLORS.orange,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 6,
  },
  ctaText: { color: "#171717", fontWeight: "900", fontSize: 16, letterSpacing: 0.2 },
});


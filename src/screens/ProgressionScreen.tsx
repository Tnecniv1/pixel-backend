// src/screens/ProgressionScreen.tsx
import React, { useEffect, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
} from "react-native";
import Constants from "expo-constants";
import { supabase } from "../supabase";
import { theme } from "../theme";
import Svg, { Line as SvgLine, Path as SvgPath, Rect, Text as SvgText } from "react-native-svg";


/* ========================== Types ========================== */
type ChartPoint = { x: number; y: number; label?: string };
type ScoreSeries = { points: ChartPoint[]; step: number; windows: number };

/* ========================== Config ========================= */
const API_BASE: string =
  // @ts-ignore Expo SDK 50+
  (Constants?.expoConfig?.extra?.API_BASE_URL as string) ||
  // @ts-ignore Expo SDK < 50
  (Constants?.manifest?.extra?.API_BASE_URL as string) ||
  "http://192.168.1.16:8000";

const SCREEN_W = Dimensions.get("window").width;

/* ====================== Utilitaires UI ===================== */
const COLORS = {
  bg: theme?.colors?.bg ?? "#0E1420",
  text: theme?.colors?.text ?? "#F5F7FB",
  sub: theme?.colors?.subtext ?? "#9CA3AF",
  card: "#FFFFFF",
  border: "#11283F",
  line: "#223A5C",
  marker: "#C066E2",
};

function Card({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.cardOuter}>
      <View style={styles.cardInner}>{children}</View>
    </View>
  );
}

function EmptyBox({ text }: { text: string }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

/* ======================= LineChart (SVG) ======================= */
function LineChart({
  points,
  width,
  height = 240,
  padding = 28,
  color = COLORS.line,
  markerColor = COLORS.marker,
}: {
  points: number[];
  width: number;
  height?: number;
  padding?: number;
  color?: string;
  markerColor?: string;
}) {
  if (!Array.isArray(points) || points.length < 2) {
    return (
      <View
        style={{
          width,
          height,
          backgroundColor: "#fff",
          borderRadius: 12,
          borderWidth: 1,
          borderColor: "#e5e7eb",
        }}
      />
    );
  }

  let minY = Math.min(...points);
  let maxY = Math.max(...points);
  if (minY === maxY) {
    minY -= 1;
    maxY += 1;
  }

  const innerW = width - padding * 2;
  const innerH = height - padding * 2;
  const xSpan = Math.max(points.length - 1, 1);

  const xAt = (i: number) => padding + (i / xSpan) * innerW;
  const yAt = (v: number) =>
    height - padding - ((v - minY) / Math.max(maxY - minY, 1e-6)) * innerH;

  // courbe lissée (quadratic)
  const d = (() => {
    const coords = points.map((v, i) => [xAt(i), yAt(v)] as const);
    let path = `M ${coords[0][0]} ${coords[0][1]}`;
    for (let i = 1; i < coords.length; i++) {
      const [x0, y0] = coords[i - 1];
      const [x1, y1] = coords[i];
      const cx = (x0 + x1) / 2;
      path += ` Q ${cx} ${y0}, ${x1} ${y1}`;
    }
    return path;
  })();

  return (
    <Svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {/* axes */}
      <SvgLine
        x1={padding}
        y1={height - padding}
        x2={width - padding}
        y2={height - padding}
        stroke="#d1d5db"
        strokeWidth={1.2}
      />
      <SvgLine
        x1={padding}
        y1={padding}
        x2={padding}
        y2={height - padding}
        stroke="#d1d5db"
        strokeWidth={1.2}
      />

      {/* courbe */}
      <SvgPath d={d} stroke={color} strokeWidth={2} fill="none" />

      {/* marqueurs carrés violets */}
      {points.map((v, i) => {
        const x = xAt(i);
        const y = yAt(v);
        const size = 6;

        return (
          <React.Fragment key={`m-${i}`}>
            <Rect
              x={x - size / 2}
              y={y - size / 2}
              width={size}
              height={size}
              fill={markerColor}
              rx={1.5}
              ry={1.5}
            />
            <SvgText
              x={x}
              y={y - 8}
              fontSize="10"
              fill="#64748b"
              textAnchor="middle"
            >
              {v}
            </SvgText>
          </React.Fragment>
        );
      })}
    </Svg>
  );
}

/* ============== Helpers “jour Europe/Paris” ============== */
function toParisDayString(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  // convertit en Europe/Paris puis renvoie 'YYYY-MM-DD'
  const s = d.toLocaleString("en-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit", day: "2-digit" }); // en-CA => YYYY-MM-DD
  return s;
}

function computeStreakFromDates(isoDates: (string | Date)[]) {
  const daySet = new Set<string>();
  for (const x of isoDates) daySet.add(toParisDayString(x));

  // courant: qui se termine "aujourd'hui Paris"
  const todayParis = toParisDayString(new Date());
  let cur = 0;
  let probe = new Date(todayParis);
  while (daySet.has(toParisDayString(probe))) {
    cur += 1;
    probe.setDate(probe.getDate() - 1);
  }

  // max: îlots consécutifs
  const allDays = Array.from(daySet).sort(); // 'YYYY-MM-DD' triable
  let max = 0, run = 0, prev: string | null = null;
  for (const d of allDays) {
    if (!prev) { run = 1; }
    else {
      const pd = new Date(prev); const nd = new Date(d);
      const diff = (nd.getTime() - pd.getTime()) / 86400000;
      run = diff === 1 ? run + 1 : 1;
    }
    if (run > max) max = run;
    prev = d;
  }
  return { current: cur, max };
}

/* ============== Fetch “score cumulé” ============== */
async function fetchScoreTimeseries(): Promise<ScoreSeries | null> {
  try {
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData?.session?.access_token;

    const url = `${API_BASE}/parcours/score_timeseries?parcours_id=1&step=100&windows=10`;

    const res = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!res.ok) return null;
    const data = (await res.json()) as ScoreSeries;
    if (!data || !Array.isArray(data.points)) return null;
    return data;
  } catch {
    return null;
  }
}

/* ============== Fetch “série actuelle/max” ============== */
async function fetchDayStreakAPI(): Promise<{ current: number; max: number } | null> {
  try {
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData?.session?.access_token;

    const res = await fetch(`${API_BASE}/stats/day_streak_current`, {
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!res.ok) return null;
    const data = await res.json();
    return {
      current: Number(data.current_streak_days ?? 0),
      max: Number(data.max_streak_days ?? 0),
    };
  } catch {
    return null;
  }
}

/* ============== Fallback local (Supabase) ============== */
async function fallbackDayStreakFromEntrainement(): Promise<{ current: number; max: number } | null> {
  try {
    // RLS doit restreindre à l'utilisateur courant, donc pas besoin de eq("Users_Id", ...)
    const twoYearsAgo = new Date(Date.now() - 730 * 86400000).toISOString();
    const { data, error } = await supabase
      .from("Entrainement")
      .select("created_at")
      .gte("created_at", twoYearsAgo)
      .order("created_at", { ascending: true });

    if (error || !data) return null;
    const { current, max } = computeStreakFromDates(data.map((r: any) => r.created_at));
    return { current, max };
  } catch {
    return null;
  }
}


/* ====================== Écran principal ====================== */
export default function ProgressionScreen() {
  const [series, setSeries] = useState<ScoreSeries | null>(null);
  const [loadingSeries, setLoadingSeries] = useState(false);

  const [streakCur, setStreakCur] = useState(0);
  const [streakMax, setStreakMax] = useState(0);
  const [loadingStreak, setLoadingStreak] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoadingSeries(true);
      setLoadingStreak(true);
      try {
        const [ts, stAPI] = await Promise.all([fetchScoreTimeseries(), fetchDayStreakAPI()]);
        if (alive) setSeries(ts);

        if (alive) {
          if (stAPI) {
            setStreakCur(stAPI.current);
            setStreakMax(stAPI.max);
          } else {
            const stLocal = await fallbackDayStreakFromEntrainement();
            if (stLocal) {
              setStreakCur(stLocal.current);
              setStreakMax(stLocal.max);
            }
          }
        }
      } finally {
        if (alive) {
          setLoadingSeries(false);
          setLoadingStreak(false);
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const pts = Array.isArray(series?.points) ? series!.points : [];
  const points = pts.map((p) => (typeof p?.y === "number" ? p.y : 0));
  const labels = pts.map((p) => p?.label ?? String(p?.x ?? ""));



  useEffect(() => {
    (async () => {
      // 1) essaie de rafraîchir
      const { data: refreshed, error: refreshErr } = await supabase.auth.refreshSession();
      if (refreshErr) console.log("[auth] refresh error:", refreshErr.message);

      // 2) récupère la session courante
      const { data, error } = await supabase.auth.getSession();
      if (error) return console.log("[auth] getSession error:", error.message);

      const token = data?.session?.access_token;
      console.log("[auth] token FULL:", token); // temporaire
    })();
  }, []);



  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 24 }}>
        <Text style={styles.h1}>Analyse Dynamique</Text>
        <Text style={styles.h2}>Score cumulé • 10×100 obs • Mixte</Text>

        {/* Carte 1 : Graphe + résumé des streaks */}
        {/* Carte 1 : Graphe seulement */}
        <Card>
          {loadingSeries ? (
            <View style={{ paddingVertical: 28 }}>
              <ActivityIndicator />
            </View>
          ) : points.length < 2 ? (
            <EmptyBox text="Pas assez de données pour construire la courbe." />
          ) : (
            <View>
              <LineChart
                width={SCREEN_W - 40}
                height={240}
                points={points}
                color={COLORS.line}
              />
              <View style={styles.xAxisLabels}>
                {labels.map((l, i) => (
                  <Text key={`x-${i}`} style={styles.xTick}>
                    {l}
                  </Text>
                ))}
              </View>
            </View>
          )}
        </Card>

        {/* Carte 2 : Bloc dédié 'Série actuelle' */}
        <Card>
          <View style={styles.currentBox}>
            <Text style={styles.currentLabel}>Série actuelle</Text>
            {loadingStreak ? (
              <ActivityIndicator />
            ) : streakCur > 0 ? (
              <Text style={styles.currentValue}>{streakCur} j</Text>
            ) : (
              <Text style={styles.currentHint}>Aucune série en cours</Text>
            )}
            {streakCur > 0 && (
              <Text style={styles.currentHint}>
                jours d’affilée avec ≥ 1 entraînement
              </Text>
            )}
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}



/* ============================ Styles ============================ */
const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  container: { flex: 1, paddingHorizontal: 20, paddingTop: 12 },

  h1: {
    color: COLORS.text,
    fontWeight: "900",
    fontSize: 24,
    textAlign: "center",
    marginTop: 8,
  },
  h2: {
    color: COLORS.sub,
    textAlign: "center",
    marginBottom: 12,
    marginTop: 4,
  },

  cardOuter: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: COLORS.border,
    overflow: "hidden",
    marginBottom: 14,
  },
  cardInner: {
    paddingHorizontal: 10,
    paddingVertical: 10,
  },

  empty: {
    padding: 16,
    backgroundColor: "#F5F7FB",
    borderRadius: 12,
  },
  emptyText: { color: COLORS.sub, fontSize: 15 },

  xAxisLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 6,
    marginTop: 6,
  },
  xTick: { color: COLORS.sub, fontSize: 11 },

  // Bloc "Série actuelle" dédié
  currentBox: { alignItems: "center", paddingVertical: 12 },
  currentLabel: { fontSize: 14, fontWeight: "600", color: "#6b7280", marginBottom: 4 },
  currentValue: { fontSize: 40, fontWeight: "800", color: "#111827", letterSpacing: 0.5 },
  currentHint: { fontSize: 12, color: "#9CA3AF", marginTop: 2 },
});

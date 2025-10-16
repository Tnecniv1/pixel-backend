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
import Svg, {
  Line as SvgLine,
  Path as SvgPath,
  Rect,
  Text as SvgText,
  Defs,
  LinearGradient,
  Stop,
  Circle,
} from "react-native-svg";
import { fetchWithSupabaseAuth } from "../api"; // chemin exact à vérifier

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
  bg: theme?.colors?.bg ?? "#0B0C1A",
  text: theme?.colors?.text ?? "#E8EAF6",
  sub: theme?.colors?.subtext ?? "#98A0B5",
  card: "rgba(26,27,43,0.92)",
  border: "#27283A",
  neon: "#BDA8FF", // ligne principale
  neonGlow: "rgba(189,168,255,0.35)",
  marker: "#C7B6FF",
  track: "rgba(255,255,255,0.06)",
  trackBorder: "rgba(255,255,255,0.10)",
  purpleSoft: "rgba(122,90,248,0.22)",
  title: "#E6E8FF",
  green: "#4ADE80",
  orange: "#FFB86B",
};

/* ------------------ Cartes réutilisables (UI) ------------------ */
function Card({ children, style }: { children: React.ReactNode; style?: any }) {
  return (
    <View style={[styles.cardOuter, style]}>
      <View style={styles.cardInner}>{children}</View>
    </View>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.chip}>
      <Text style={styles.chipText}>{children}</Text>
    </View>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.badge}>
      <Text style={styles.badgeText}>{children}</Text>
    </View>
  );
}

function KPI({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.kpi}>
      <Text style={styles.kpiValue}>{value}</Text>
      <Text style={styles.kpiLabel}>{label}</Text>
    </View>
  );
}

function ProgressBar({ progress, label }: { progress: number; label?: string }) {
  const pct = Math.max(0, Math.min(1, progress));
  return (
    <View style={styles.pbarWrap}>
      <View style={styles.pbarTrack}>
        <View style={[styles.pbarFill, { width: `${Math.round(pct * 100)}%` }]} />
      </View>
      {label ? <Text style={styles.pbarLabel}>{label}</Text> : null}
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
/** Re-skin néon, même API interne (points:number[], width, …). */
function LineChart({
  points,
  width,
  height = 220,
  padding = 20,
  color = COLORS.neon,
  markerColor = COLORS.marker,
  showXAxis = true,
  showYAxis = false,
}: {
  points: number[];
  width: number;
  height?: number;
  padding?: number;
  color?: string;
  markerColor?: string;
  showXAxis?: boolean;
  showYAxis?: boolean;
}) {
  if (!Array.isArray(points) || points.length < 2) {
    return (
      <View
        style={{
          width,
          height,
          backgroundColor: "rgba(255,255,255,0.02)",
          borderRadius: 12,
          borderWidth: 1,
          borderColor: COLORS.trackBorder,
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

  // path lissé quadratique (même principe, mais double pour glow)
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
      <Defs>
        <LinearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0%" stopColor={COLORS.purpleSoft} />
          <Stop offset="100%" stopColor="rgba(122,90,248,0)" />
        </LinearGradient>
      </Defs>

      {/* Axe X minimal (option) */}
      {showXAxis && (
        <SvgLine
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke={COLORS.trackBorder}
          strokeWidth={1}
        />
      )}
      {/* Axe Y coupé (option) */}
      {showYAxis && (
        <SvgLine
          x1={padding}
          y1={padding}
          x2={padding}
          y2={height - padding}
          stroke={COLORS.trackBorder}
          strokeWidth={1}
        />
      )}

      {/* Zone sous courbe (léger) */}
      <SvgPath
        d={`${d} L ${width - padding} ${height - padding} L ${padding} ${height - padding} Z`}
        fill="url(#areaGrad)"
        opacity={0.35}
      />

      {/* Glow */}
      <SvgPath d={d} stroke={COLORS.neonGlow} strokeWidth={8} fill="none" />
      {/* Ligne principale */}
      <SvgPath d={d} stroke={color} strokeWidth={3.5} fill="none" />

      {/* Points ronds */}
      {points.map((v, i) => {
        const x = xAt(i);
        const y = yAt(v);
        return <Circle key={`p-${i}`} cx={x} cy={y} r={4} fill={markerColor} />;
      })}
    </Svg>
  );
}

/* ============== Helpers “jour Europe/Paris” ============== */
function toParisDayString(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const s = d.toLocaleString("en-CA", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return s; // YYYY-MM-DD
}

function computeStreakFromDates(isoDates: (string | Date)[]) {
  const daySet = new Set<string>();
  for (const x of isoDates) daySet.add(toParisDayString(x));

  const todayParis = toParisDayString(new Date());
  let cur = 0;
  let probe = new Date(todayParis);
  while (daySet.has(toParisDayString(probe))) {
    cur += 1;
    probe.setDate(probe.getDate() - 1);
  }

  const allDays = Array.from(daySet).sort();
  let max = 0,
    run = 0,
    prev: string | null = null;
  for (const d of allDays) {
    if (!prev) {
      run = 1;
    } else {
      const pd = new Date(prev);
      const nd = new Date(d);
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

    const res = await fetchWithSupabaseAuth(url, {
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

    const res = await fetchWithSupabaseAuth(`${API_BASE}/stats/day_streak_current`, {
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

  // KPIs faciles à partir des points
  const last = points.length ? points[points.length - 1] : 0;
  const prev = points.length > 1 ? points[points.length - 2] : 0;
  const delta = last - prev;
  const maxVal = points.length ? Math.max(...points) : 0;
  const bestJump = points.reduce((best, v, i, arr) => {
    if (i === 0) return best;
    const d = v - arr[i - 1];
    return d > best ? d : best;
  }, 0);

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 24 }}>
        {/* HERO */}
        <View style={styles.hero}>
          <Text style={styles.h1}>Analyse Dynamique</Text>
          <View style={styles.chipsRow}>
            <Chip>Score cumulé</Chip>
            <Chip>10×100 obs</Chip>
            <Chip>Mixte</Chip>
          </View>
        </View>

        {/* GRAPHE */}
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
                height={220}
                points={points}
                color={COLORS.neon}
                showXAxis
                showYAxis={false}
              />
              {/* Ticks X discrets */}
              <View style={styles.xAxisLabels}>
                {labels.map((l, i) => (
                  <Text key={`x-${i}`} style={styles.xTick}>
                    {l}
                  </Text>
                ))}
              </View>

              {/* Badges overlay (max & meilleur delta) */}
              <View style={styles.chartBadges}>
                <Badge>Max: {maxVal}</Badge>
                {bestJump > 0 ? <Badge>+{bestJump} (meilleur saut)</Badge> : null}
              </View>
            </View>
          )}
        </Card>

        {/* KPIs compacts */}
        <View style={styles.kpiRow}>
          <KPI label="Score cumulé" value={`${last}`} />
          <KPI label="Δ récent" value={`${delta >= 0 ? "+" : ""}${delta}`} />
          <KPI label="Max" value={`${maxVal}`} />
        </View>

        {/* STREAK */}
        <Card>
          <View style={styles.streakBox}>
            <Text style={styles.streakTitle}>Série actuelle</Text>
            {loadingStreak ? (
              <ActivityIndicator />
            ) : streakCur > 0 ? (
              <Text style={styles.streakValue}>🔥 {streakCur} j</Text>
            ) : (
              <Text style={styles.streakHint}>Aucune série en cours</Text>
            )}
            <ProgressBar
              progress={Math.min(1, streakCur / 50)}
              label={`Prochain palier : 50 j • Record : ${streakMax} j`}
            />
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

  hero: { alignItems: "center", marginBottom: 6, gap: 6 },
  h1: {
    color: COLORS.title,
    fontWeight: "900",
    fontSize: 24,
    textAlign: "center",
    letterSpacing: 0.2,
  },
  chipsRow: { flexDirection: "row", gap: 8, flexWrap: "wrap", justifyContent: "center" },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    backgroundColor: "rgba(122,90,248,0.16)",
    borderWidth: 1,
    borderColor: COLORS.purpleSoft,
  },
  chipText: { color: COLORS.text, fontWeight: "700", fontSize: 12 },

  cardOuter: {
    backgroundColor: COLORS.card,
    borderRadius: 16,
    borderWidth: 1,
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
    backgroundColor: "rgba(255,255,255,0.02)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.trackBorder,
  },
  emptyText: { color: COLORS.sub, fontSize: 14 },

  xAxisLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: 6,
    marginTop: 6,
  },
  xTick: { color: COLORS.sub, fontSize: 11 },

  chartBadges: { position: "absolute", top: 8, right: 8, gap: 6, alignItems: "flex-end" },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "rgba(0,0,0,0.35)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
  },
  badgeText: { color: COLORS.text, fontWeight: "800", fontSize: 10, letterSpacing: 0.3 },

  kpiRow: { flexDirection: "row", gap: 10, marginBottom: 4 },
  kpi: {
    flex: 1,
    backgroundColor: COLORS.card,
    borderColor: COLORS.border,
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 10,
    paddingHorizontal: 10,
    alignItems: "center",
    gap: 2,
  },
  kpiValue: { color: COLORS.title, fontSize: 18, fontWeight: "900" },
  kpiLabel: { color: COLORS.sub, fontSize: 11, fontWeight: "600" },

  streakBox: { alignItems: "center", gap: 6 },
  streakTitle: { fontSize: 12, fontWeight: "800", color: COLORS.sub, letterSpacing: 0.4 },
  streakValue: { fontSize: 28, fontWeight: "900", color: COLORS.title },
  streakHint: { fontSize: 12, color: COLORS.sub },

  pbarWrap: { width: "100%", gap: 4, marginTop: 2 },
  pbarTrack: {
    height: 12,
    borderRadius: 999,
    backgroundColor: COLORS.track,
    borderWidth: 1,
    borderColor: COLORS.trackBorder,
    overflow: "hidden",
  },
  pbarFill: {
    height: "100%",
    backgroundColor: COLORS.purpleSoft,
    borderRadius: 999,
  },
  pbarLabel: { color: COLORS.sub, fontSize: 11, textAlign: "center" },
});

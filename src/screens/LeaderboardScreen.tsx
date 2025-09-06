import * as React from "react";
import { SafeAreaView, View, Text, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import Constants from "expo-constants";
import { getLeaderboard, LeaderboardItem } from "../api";
import { fetchWithSupabaseAuth } from "../api"; // chemin exact à vérifier


const MiniPixel = ({ ratio = 0 }: { ratio?: number }) => {
  const r = Math.max(0, Math.min(1, ratio || 0));
  return (
    <View style={{ width: 40, height: 10, borderRadius: 3, backgroundColor: "#fff", borderWidth: 1, borderColor: "#DDD" }}>
      <View style={{ width: 40 * r, height: 10, borderRadius: 3, backgroundColor: "#6C5CE7" }} />
    </View>
  );
};

type Item = LeaderboardItem & { display_name?: string };

const API_BASE: string = (Constants.expoConfig?.extra as any)?.API_BASE_URL ?? "";

/** Essaie de résoudre { user_id -> Name } via le backend, sinon renvoie {}. */
async function resolveDisplayNames(ids: Array<number | string>): Promise<Record<string, string>> {
  const unique = Array.from(new Set(ids.map(String))).filter(Boolean);
  if (!unique.length || !API_BASE) return {};

  // 1) GET /users/resolve?ids=1,2,3
  try {
    const url = `${API_BASE}/users/resolve?ids=${encodeURIComponent(unique.join(","))}`;
    const r = await fetchWithSupabaseAuth(url);
    if (r.ok) {
      const data = await r.json();
      // Supporte { "<id>": "Nom" } ou { users: [{ id/Id/user_id, Name/name/display_name }] }
      if (data && typeof data === "object") {
        if (Array.isArray((data as any).users)) {
          const map: Record<string, string> = {};
          for (const u of (data as any).users) {
            const id = String(u.id ?? u.Id ?? u.user_id ?? "");
            const nm = String(u.Name ?? u.name ?? u.display_name ?? "");
            if (id && nm) map[id] = nm;
          }
          return map;
        }
        return data as Record<string, string>;
      }
    }
  } catch { /* ignore */ }

  // 2) POST /users/resolve  { ids: [...] }
  try {
    const r2 = await fetchWithSupabaseAuth(`${API_BASE}/users/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: unique }),
    });
    if (r2.ok) {
      const data = await r2.json();
      if (data && typeof data === "object") {
        if (Array.isArray((data as any).users)) {
          const map: Record<string, string> = {};
          for (const u of (data as any).users) {
            const id = String(u.id ?? u.Id ?? u.user_id ?? "");
            const nm = String(u.Name ?? u.name ?? u.display_name ?? "");
            if (id && nm) map[id] = nm;
          }
          return map;
        }
        return data as Record<string, string>;
      }
    }
  } catch { /* ignore */ }

  return {};
}

export default function LeaderboardScreen() {
  const [scope, setScope] = React.useState<"all" | "this_week">("all");
  const [items, setItems] = React.useState<Item[]>([]);
  const [me, setMe] = React.useState<Item | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await getLeaderboard(scope, 50, 0);
      const baseItems: Item[] = data.items ?? [];
      const baseMe: Item | null = data.me ?? null;

      // On ne résout que les IDs qui n'ont pas encore de display_name
      const idsToResolve = [
        ...baseItems.filter((r) => !r.display_name).map((r) => r.user_id),
        ...(baseMe && !baseMe.display_name ? [baseMe.user_id] : []),
      ];

      const nameMap = await resolveDisplayNames(idsToResolve);

      const enrichedItems = baseItems.map((r) => ({
        ...r,
        display_name: r.display_name ?? nameMap[String(r.user_id)],
      }));

      const enrichedMe = baseMe
        ? { ...baseMe, display_name: baseMe.display_name ?? nameMap[String(baseMe.user_id)] }
        : null;

      setItems(enrichedItems);
      setMe(enrichedMe);
    } finally {
      setLoading(false);
    }
  }, [scope]);

  React.useEffect(() => { load(); }, [load]);

  const renderName = (it: Item) =>
    it.display_name && it.display_name.trim().length > 0
      ? it.display_name
      : `User #${it.user_id}`;

  return (
    <SafeAreaView style={{ flex: 1, padding: 16 }}>
      <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
        <TouchableOpacity onPress={() => setScope("all")} style={[styles.tab, scope === "all" && styles.tabActive]}>
          <Text>Tous</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setScope("this_week")} style={[styles.tab, scope === "this_week" && styles.tabActive]}>
          <Text>Semaine</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.headerRow}>
        <Text style={[styles.cell, { flex: 0.6 }]}>Pos</Text>
        <Text style={[styles.cell, { flex: 2 }]}>Joueur</Text>
        <Text style={[styles.cell, { flex: 1 }]}>Score</Text>
        <Text style={[styles.cell, { flex: 1 }]}>Pixel</Text>
      </View>

      <FlatList
        data={items}
        keyExtractor={(it) => String(it.user_id)}
        refreshing={loading}
        onRefresh={load}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={[styles.cell, { flex: 0.6 }]}>{item.rank}</Text>
            <Text style={[styles.cell, { flex: 2 }]}>{renderName(item)}</Text>
            <Text style={[styles.cell, { flex: 1 }]}>{item.score_total}</Text>
            <View style={[styles.cell, { flex: 1 }]}>
              <MiniPixel ratio={item.pixel_ratio} />
            </View>
          </View>
        )}
      />

      {me && (
        <View style={[styles.row, { borderTopWidth: 1, borderColor: "#EEE", marginTop: 8 }]}>
          <Text style={[styles.cell, { flex: 0.6 }]}>Moi</Text>
          <Text style={[styles.cell, { flex: 2 }]}>{renderName(me)}</Text>
          <Text style={[styles.cell, { flex: 1 }]}>{me.score_total}</Text>
          <View style={[styles.cell, { flex: 1 }]}>
            <MiniPixel ratio={me.pixel_ratio} />
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: "row", paddingVertical: 6, borderBottomWidth: 1, borderColor: "#EEE" },
  row: { flexDirection: "row", paddingVertical: 10, alignItems: "center" },
  cell: { color: "#1F3554" },
  tab: { paddingVertical: 6, paddingHorizontal: 10, borderWidth: 1, borderColor: "#DDD", borderRadius: 8 },
  tabActive: { backgroundColor: "#EEE" },
});

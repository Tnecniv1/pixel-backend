// src/screens/LeaderboardScreen.tsx
import * as React from "react";
import {
  SafeAreaView,
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { theme } from "../theme";
import { supabase } from "../supabase"; // garde ce chemin

type Scope = "all" | "this_week";

type RpcRow = {
  user_id: number;
  display_name: string | null;
  score_total: number;
  // pixel_ratio retiré volontairement
};

type Item = {
  user_id: number;
  rank: number;
  display_name: string | null;
  score_total: number;
};

export default function LeaderboardScreen() {
  const [scope, setScope] = React.useState<Scope>("all");
  const [items, setItems] = React.useState<Item[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const { data, error } = await supabase.rpc("get_leaderboard_with_names", {
        p_limit: 100,
        p_weekly: scope === "this_week",
      });
      if (error) throw error;

      const rows = (data ?? []) as RpcRow[];

      const mapped: Item[] = rows.map((r, i) => ({
        user_id: r.user_id,
        rank: i + 1,
        display_name: r.display_name,
        score_total: r.score_total,
      }));

      setItems(mapped);
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [scope]);

  React.useEffect(() => {
    load();
  }, [load]);

  const renderName = (it: Item) =>
    (it.display_name && it.display_name.trim()) || `User #${it.user_id}`;

  return (
    <SafeAreaView style={styles.safe}>
      {/* Onglets */}
      <View style={styles.tabs}>
        <TouchableOpacity
          onPress={() => setScope("all")}
          disabled={loading || scope === "all"}
          style={[
            styles.tab,
            scope === "all" && styles.tabActive,
            (loading || scope === "all") && styles.tabDisabled,
          ]}
        >
          <Text style={styles.tabText}>Tous</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => setScope("this_week")}
          disabled={loading || scope === "this_week"}
          style={[
            styles.tab,
            scope === "this_week" && styles.tabActive,
            (loading || scope === "this_week") && styles.tabDisabled,
          ]}
        >
          <Text style={styles.tabText}>Semaine</Text>
        </TouchableOpacity>
      </View>

      {/* En-tête (Pixel retiré) */}
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, { flex: 0.6 }]}>Pos</Text>
        <Text style={[styles.headerCell, { flex: 2 }]}>Joueur</Text>
        <Text style={[styles.headerCell, { flex: 1 }]}>Score</Text>
      </View>

      {/* Liste (Pixel retiré) */}
      <FlatList
        data={items}
        keyExtractor={(it) => String(it.user_id)}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={load} tintColor={theme.colors.text} />
        }
        contentContainerStyle={{ paddingBottom: 12 }}
        ListEmptyComponent={
          !loading ? (
            <View style={{ paddingVertical: 24 }}>
              <Text style={styles.emptyText}>
                {error ?? "Aucun résultat pour cette vue."}
              </Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={[styles.cell, { flex: 0.6 }]}>{item.rank}</Text>
            <Text style={[styles.cell, { flex: 2 }]}>{renderName(item)}</Text>
            <Text style={[styles.cell, { flex: 1 }]}>{item.score_total}</Text>
          </View>
        )}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    padding: 16,
    backgroundColor: theme.colors.bg,
  },

  // Onglets
  tabs: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 12,
  },
  tab: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: 8,
    backgroundColor: theme.colors.card,
  },
  tabActive: {
    backgroundColor: theme.colors.accent,
  },
  tabDisabled: {
    opacity: 0.6,
  },
  tabText: {
    color: theme.colors.text,
    fontWeight: "600",
  },

  // Tableau
  headerRow: {
    flexDirection: "row",
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderColor: theme.colors.border,
  },
  headerCell: {
    color: theme.colors.text,
    opacity: 0.8,
    fontWeight: "700",
  },
  row: {
    flexDirection: "row",
    paddingVertical: 10,
    alignItems: "center",
  },
  cell: {
    color: theme.colors.text,
  },
  emptyText: {
    textAlign: "center",
    color: theme.colors.text,
    opacity: 0.6,
  },
});

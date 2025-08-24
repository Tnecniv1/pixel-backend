import * as React from "react";
import { SafeAreaView, View, Text, StyleSheet, FlatList, TouchableOpacity } from "react-native";
import { getLeaderboard, LeaderboardItem } from "../api";

const MiniPixel = ({ ratio = 0 }: { ratio?: number }) => {
  const r = Math.max(0, Math.min(1, ratio || 0));
  return (
    <View style={{ width: 40, height: 10, borderRadius: 3, backgroundColor: "#fff", borderWidth: 1, borderColor: "#DDD" }}>
      <View style={{ width: 40 * r, height: 10, borderRadius: 3, backgroundColor: "#6C5CE7" }} />
    </View>
  );
};

export default function LeaderboardScreen() {
  const [scope, setScope] = React.useState<"all"|"this_week">("all");
  const [items, setItems] = React.useState<LeaderboardItem[]>([]);
  const [me, setMe] = React.useState<LeaderboardItem | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await getLeaderboard(scope, 50, 0);
      setItems(data.items);
      setMe(data.me);
    } finally {
      setLoading(false);
    }
  }, [scope]);

  React.useEffect(() => { load(); }, [load]);

  return (
    <SafeAreaView style={{ flex: 1, padding: 16 }}>
      <View style={{ flexDirection: "row", gap: 8, marginBottom: 12 }}>
        <TouchableOpacity onPress={() => setScope("all")} style={[styles.tab, scope==="all" && styles.tabActive]}><Text>Tous</Text></TouchableOpacity>
        <TouchableOpacity onPress={() => setScope("this_week")} style={[styles.tab, scope==="this_week" && styles.tabActive]}><Text>Semaine</Text></TouchableOpacity>
      </View>

      <View style={styles.headerRow}>
        <Text style={[styles.cell, {flex: 0.6}]}>Pos</Text>
        <Text style={[styles.cell, {flex: 2}]}>Joueur</Text>
        <Text style={[styles.cell, {flex: 1}]}>Score</Text>
        <Text style={[styles.cell, {flex: 1}]}>Pixel</Text>
      </View>

      <FlatList
        data={items}
        keyExtractor={(it) => String(it.user_id)}
        refreshing={loading}
        onRefresh={load}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={[styles.cell, {flex: 0.6}]}>{item.rank}</Text>
            <Text style={[styles.cell, {flex: 2}]}>{item.display_name ?? `User #${item.user_id}`}</Text>
            <Text style={[styles.cell, {flex: 1}]}>{item.score_total}</Text>
            <View style={[styles.cell, {flex: 1}]}><MiniPixel ratio={item.pixel_ratio} /></View>
          </View>
        )}
      />

      {me && (
        <View style={[styles.row, { borderTopWidth: 1, borderColor: "#EEE", marginTop: 8 }]}>
          <Text style={[styles.cell, {flex: 0.6}]}>Moi</Text>
          <Text style={[styles.cell, {flex: 2}]}>{me.display_name ?? `User #${me.user_id}`}</Text>
          <Text style={[styles.cell, {flex: 1}]}>{me.score_total}</Text>
          <View style={[styles.cell, {flex: 1}]}><MiniPixel ratio={me.pixel_ratio} /></View>
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

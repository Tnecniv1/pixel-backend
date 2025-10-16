import * as React from "react";
import { SafeAreaView, View, Text, TouchableOpacity, StyleSheet } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../App";
import BigPixel from "../components/BigPixel";
import { getPixelState } from "../api";
import { useLayoutEffect } from "react";

type Props = NativeStackScreenProps<RootStackParamList, "Home">;

const COLORS = {
  bg: "#18162A",
  text: "#ffffffff",
  subtext: "#9a9ca1ff",
  orange: "#FFD93D",
  orangeText: "#171717",
  blue: "#4DB7FF",
  blueText: "#11283F",
  card: "#FFFFFF",
  shadow: "rgba(0,0,0,0.08)",
};

export default function HomeScreen({ navigation }: Props) {
  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity
          onPress={() => navigation.navigate("Info")}
          style={{
            width: 32,
            height: 32,
            borderRadius: 16,
            backgroundColor: "#b648c0ff",
            justifyContent: "center",
            alignItems: "center",
            marginRight: 10,
          }}
        >
          <Text style={{ fontWeight: "600", color: "#000" }}>i</Text>
        </TouchableOpacity>
      ),
    });
  }, [navigation]);

  const [pixel, setPixel] = React.useState<{ lit: number; capacity: number; ratio: number } | null>(null);
  const [loading, setLoading] = React.useState(true);

  const loadPixel = React.useCallback(async () => {
    try {
      setLoading(true);
      const data = await getPixelState();
      setPixel({ lit: data.lit, capacity: data.capacity, ratio: data.ratio });
    } catch (e) {
      console.error("getPixelState failed:", e);
      setPixel(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadPixel();
  }, [loadPixel]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>SUCCES OU ECHEC ?</Text>
          <Text style={styles.subtitle}>Parviendras-tu à remplir ton pixel ?</Text>
        </View>

        {/* Grand Pixel */}
        <View style={styles.pixelBlock}>
          {loading ? (
            <View style={styles.pixelPlaceholder}>
              <Text style={styles.pixelPlaceholderText}>Chargement…</Text>
            </View>
          ) : pixel ? (
            <BigPixel lit={pixel.lit} cols={350} rows={350} size={350} />
          ) : (
            <View style={styles.pixelPlaceholder}>
              <Text style={styles.pixelPlaceholderText}>Impossible de charger le Pixel</Text>
            </View>
          )}
        </View>

        <View style={styles.ctaBlock}>
          <TouchableOpacity
            activeOpacity={0.9}
            style={[styles.cta, styles.ctaOrange]}
            onPress={() => navigation.navigate("Entrainement")}
          >
            <Text style={styles.ctaOrangeText}>ENTRAÎNEMENT</Text>
          </TouchableOpacity>

          <TouchableOpacity
            activeOpacity={0.9}
            style={[styles.cta, styles.ctaBlue]}
            onPress={() => navigation.navigate("Progression", { parcoursId: 1 })}
          >
            <Text style={styles.ctaBlueText}>PROGRESSION</Text>
          </TouchableOpacity>

          <TouchableOpacity
            activeOpacity={0.9}
            style={[styles.cta, styles.ctaBlue]}
            onPress={() => navigation.navigate("Leaderboard")}
          >
            <Text style={styles.ctaBlueText}>CLASSEMENT</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  container: { flex: 1, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 24 },
  header: { marginBottom: 24, alignItems: "center" },
  title: { color: COLORS.text, fontWeight: "800", fontSize: 20 },
  subtitle: { color: COLORS.subtext, fontSize: 13, marginTop: 6 },

  pixelBlock: { alignItems: "center", marginBottom: 16 },
  pixelPlaceholder: {
    width: 350,
    height: 350,
    borderWidth: 1,
    borderColor: "#E5E5E5",
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
  },
  pixelPlaceholderText: { color: "#6B7280" },

  ctaBlock: { gap: 16, marginTop: 10 },
  cta: {
    borderRadius: 16,
    paddingVertical: 18,
    paddingHorizontal: 16,
    backgroundColor: COLORS.card,
    shadowColor: COLORS.shadow,
    shadowOpacity: 1,
    shadowOffset: { width: 0, height: 6 },
    shadowRadius: 12,
    elevation: 3,
    alignItems: "center",
  },
  ctaOrange: { backgroundColor: COLORS.orange },
  ctaBlue: { backgroundColor: COLORS.blue },
  ctaOrangeText: { color: COLORS.orangeText, fontWeight: "900", fontSize: 16, letterSpacing: 0.2 },
  ctaBlueText: { color: COLORS.blueText, fontWeight: "900", fontSize: 16, letterSpacing: 0.2 },
});

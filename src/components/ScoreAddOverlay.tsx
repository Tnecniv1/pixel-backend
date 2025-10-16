// components/ScoreAddOverlay.tsx
import React from "react";
import { View, Text, StyleSheet, Modal } from "react-native";
import BigPixel, { BigPixelHandle } from "./BigPixel";

type Props = {
  visible: boolean;
  baseLit: number;        // total avant cette session
  score: number;          // score de la session (-30..+30)
  onDone: (nextTotal: number) => void; // callback quand l’anim est finie
  cols?: number;
  rows?: number;
  size?: number;
};

export default function ScoreAddOverlay({
  visible,
  baseLit,
  score,
  onDone,
  cols = 110,
  rows = 110,
  size = 360,
}: Props) {
  const pixelRef = React.useRef<BigPixelHandle>(null);
  const [scoreLeft, setScoreLeft] = React.useState(score);

  React.useEffect(() => {
    if (!visible) return;
    let cancelled = false;

    const run = async () => {
      // synchroniser la décrémentation du score et l’animation des pixels
      const step = scoreLeft > 0 ? -1 : scoreLeft < 0 ? +1 : 0;
      if (step === 0) {
        onDone(baseLit);
        return;
      }

      let remaining = Math.abs(scoreLeft);
      const dir = Math.sign(scoreLeft); // +1 -> ajout, -1 -> retrait

      while (!cancelled && remaining > 0) {
        // Anime 1 micro-pixel à la fois pour rester “synchro” avec le compteur
        await pixelRef.current?.applyScore(dir); // +1 ou -1 pixel
        remaining -= 1;
        setScoreLeft((s) => s + (s > 0 ? -1 : +1)); // vers 0
      }

      if (!cancelled) {
        const nextTotal = Math.max(0, baseLit + score);
        onDone(nextTotal);
      }
    };

    run();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]); // démarre à l'ouverture

  return (
    <Modal visible={visible} animationType="fade" transparent>
      <View style={styles.backdrop}>
        <View style={styles.container}>
          {/* Score en haut à droite, qui compte vers 0 */}
          <View style={[styles.scorePill, scoreLeft >= 0 ? styles.pos : styles.neg]}>
            <Text style={styles.scoreText}>
              {scoreLeft > 0 ? `+${scoreLeft}` : `${scoreLeft}`}
            </Text>
          </View>

          {/* BigPixel “cloné” pour l’animation */}
          <BigPixel
            ref={pixelRef}
            lit={baseLit}
            cols={cols}
            rows={rows}
            size={size}
            seed={2025}
            stepMs={16}   // vitesse agréable
            maxDelta={1}  // IMPORTANT: on avance 1 par 1 pour garder le score synchro
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  container: {
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

// src/components/Calculator.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ViewStyle,
  StyleProp,
  LayoutChangeEvent,
} from "react-native";
import { Asset } from "expo-asset";
import { Audio } from "expo-av";

/**
 * Calculator (Pixel)
 * - Grille 3×4, touches carrées & responsives
 * - Boutons fixes:
 *    - index 9  (ligne 4, col 1)  → Corriger (••)
 *    - index 11 (ligne 4, col 3)  → Valider (•)
 * - Chiffres: ordre de base [4,8,2,5,0,1,7,6,3,9] sur les 10 autres cases
 * - Déstabilisation (mutuellement exclusive), déclenchée UNIQUEMENT à la validation:
 *    - Au submit() on prépare le “prochain piège” (pending) pour l’opération suivante.
 *    - À chaque changement de currentIndex (nouvelle opération), on active le “pending”.
 *    - La durée se décompte à CHAQUE validation (pas à chaque tap).
 */

// 🎨 Personnalisation
const COLORS = {
  keyBg: "#6a5acd",
  keyText: "#f8f8ff",
  displayText: "#fefdffff",
  displayBorder: "#7aa1f5ff",
};
const UI = {
  cols: 3,
  gap: 10,
  keyRadius: 16,
  keyFontSize: 22,
  displayRadius: 12,
  displayFontSize: 28,
};

// 🔔 Haptique (optionnelle, safe-require)
type HapticsNS = {
  impactAsync?: (s: any) => Promise<void>;
  selectionAsync?: () => Promise<void>;
  notificationAsync?: (t: any) => Promise<void>;
  ImpactFeedbackStyle?: any;
  NotificationFeedbackType?: any;
} | null;
let H: HapticsNS = null;
try { H = require("expo-haptics"); } catch { H = null; }

// Types
type Range = { min: number; max: number };
type DestabMode = "HIDE" | "SHUFFLE";

type Props = {
  value?: string;
  onChangeText?: (text: string) => void;
  onSubmit?: (text: string) => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;

  // Déstabilisation (pilotées depuis TrainScreen)
  currentIndex?: number;             // <- i
  destabilizeEnabled?: boolean;      // default false
  hideChance?: number;               // default 0.25
  hideRange?: Range;                 // default {min:1,max:2}
  shuffleChance?: number;            // default 0.25
  shuffleRange?: Range;              // default {min:1,max:2}
};

// Constantes layout
const BASE_ORDER = ["4", "8", "2", "5", "0", "1", "7", "6", "3", "9"]; // 10 chiffres
const GRID_SIZE = 12;
const ERASE_INDEX = 9;   // bas-gauche
const SUBMIT_INDEX = 11; // bas-droite
const DIGIT_SLOTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]; // 10 positions (tout sauf 9 et 11)

// Utils
const randInt = (min: number, max: number) =>
  Math.floor(min + Math.random() * (max - min + 1));

const pickOne = <T,>(arr: T[]) => arr[Math.floor(Math.random() * arr.length)];

const shuffleArr = <T,>(arr: T[]) => {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
};

export default function Calculator({
  value = "",
  onChangeText,
  onSubmit,
  disabled,
  style,

  currentIndex,
  destabilizeEnabled = false,
  hideChance = 0.25,
  hideRange = { min: 1, max: 2 },
  shuffleChance = 0.25,
  shuffleRange = { min: 1, max: 2 },
}: Props) {
  const [local, setLocal] = useState<string>(value);
  const [gridW, setGridW] = useState(0);

  // expo-av Sound
  const soundRef = useRef<Audio.Sound | null>(null);

  // État actif pour l'OPÉRATION COURANTE
  const activeModeRef = useRef<DestabMode | null>(null);
  const activeRemainingRef = useRef<number>(0); // en nb d'opérations à partir de MAINTENANT (se décrémente à la prochaine validation)

  // Piège “en attente” pour la PROCHAINE opération (préparé dans submit)
  const pendingModeRef = useRef<DestabMode | null>(null);
  const pendingRemainingRef = useRef<number>(0);

  // Ordre des chiffres pour l’opération courante
  const [digitOrder, setDigitOrder] = useState<string[]>(BASE_ORDER);

  useEffect(() => setLocal(value), [value]);

  // ------- AUDIO (expo-av) -------
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await Audio.setAudioModeAsync({
          playsInSilentModeIOS: true,
          staysActiveInBackground: false,
          interruptionModeIOS: 0,
          shouldDuckAndroid: true,
          playThroughEarpieceAndroid: false,
        });

        const asset = Asset.fromModule(
          // @ts-ignore
          require("../../assets/Sounds/coin.mp3")
        );
        await asset.downloadAsync();
        if (!mounted || !asset.localUri) return;

        const { sound } = await Audio.Sound.createAsync(
          { uri: asset.localUri },
          { shouldPlay: false, volume: 1.0, isLooping: false }
        );
        if (mounted) soundRef.current = sound;
        else await sound.unloadAsync();
      } catch {
        soundRef.current = null; // silencieux si indispo
      }
    })();
    return () => {
      mounted = false;
      try { soundRef.current?.unloadAsync(); } catch {}
    };
  }, []);

  // ------- ACTIVATION DU PIÈGE À LA NOUVELLE OPÉRATION -------
  useEffect(() => {
    if (!destabilizeEnabled) {
      activeModeRef.current = null;
      activeRemainingRef.current = 0;
      pendingModeRef.current = null;
      pendingRemainingRef.current = 0;
      setDigitOrder(BASE_ORDER);
      return;
    }
    if (typeof currentIndex !== "number") return;

    // On entre sur une NOUVELLE opération → activer le pending (préparé au submit précédent)
    activeModeRef.current = pendingModeRef.current;
    activeRemainingRef.current = pendingRemainingRef.current;

    // Nettoyer le pending
    pendingModeRef.current = null;
    pendingRemainingRef.current = 0;

    // Ajuster l'ordre selon le mode actif
    if (activeModeRef.current === "SHUFFLE") {
      // Au début de CHAQUE opération sous SHUFFLE, on mélange (pour plus de variété)
      setDigitOrder(shuffleArr(BASE_ORDER));
    } else {
      setDigitOrder(BASE_ORDER);
    }
  }, [currentIndex, destabilizeEnabled]);

  // ------- Haptics -------
  const hTap = () => H?.impactAsync?.(H.ImpactFeedbackStyle?.Light).catch(() => {});
  const hSelect = () => H?.selectionAsync?.().catch(() => {});
  const hSuccess = () => H?.notificationAsync?.(H.NotificationFeedbackType?.Success).catch(() => {});

  // ------- Actions -------
  const pressNumber = useCallback(
    (n: string) => {
      if (disabled) return;
      setLocal((p) => {
        const next = (p ?? "") + n;
        onChangeText?.(next);
        return next;
      });
      hTap();
    },
    [disabled, onChangeText]
  );

  const erase = useCallback(() => {
    if (disabled) return;
    setLocal((p) => {
      const next = (p ?? "")?.slice(0, -1);
      onChangeText?.(next);
      return next;
    });
    hSelect();
  }, [disabled, onChangeText]);

  const submit = useCallback(() => {
    if (disabled) return;

    // 1) On remet la réponse et on notifie le parent
    onSubmit?.(local ?? "");
    hSuccess();
    (async () => {
      try {
        const s = soundRef.current;
        if (!s) return;
        await s.setPositionAsync(0);
        await s.playFromPositionAsync(0);
      } catch {}
    })();

    // 2) Gestion des séquences (décomptage ET préparation du prochain piège)
    if (!destabilizeEnabled) return;

    // Décompter la séquence courante (si active) — elle s’applique jusqu’à CETTE validation
    if (activeModeRef.current) {
      const remain = Math.max(0, (activeRemainingRef.current || 0) - 1);
      activeRemainingRef.current = remain;
      if (remain === 0) {
        activeModeRef.current = null;
      }
    }

    // Si une séquence reste active après ce décompte (remain > 0),
    // alors on prolonge le même mode pour la prochaine opération.
    if (activeModeRef.current && activeRemainingRef.current > 0) {
      pendingModeRef.current = activeModeRef.current;
      pendingRemainingRef.current = activeRemainingRef.current; // déjà décrémenté
      return;
    }

    // Sinon, on peut tirer un nouveau piège pour la prochaine opération.
    const h = Math.random() < (hideChance ?? 0.05);
    const s = Math.random() < (shuffleChance ?? 0.10);

    if (!h && !s) {
      pendingModeRef.current = null;
      pendingRemainingRef.current = 0;
      return;
    }

    // Jamais en même temps → si les deux “tirent”, choisir au hasard
    let chosen: DestabMode = "HIDE";
    if (h && s) {
      chosen = Math.random() < 0.5 ? "HIDE" : "SHUFFLE";
    } else if (s) {
      chosen = "SHUFFLE";
    } else {
      chosen = "HIDE";
    }

    const range = chosen === "HIDE"
      ? (hideRange ?? { min: 1, max: 2 })
      : (shuffleRange ?? { min: 1, max: 2 });

    const duration = Math.max(1, randInt(range.min, range.max));
    pendingModeRef.current = chosen;
    pendingRemainingRef.current = duration;
  }, [disabled, onSubmit, local, destabilizeEnabled, hideChance, hideRange, shuffleChance, shuffleRange]);

  // ------- Layout 3 colonnes (carrés) -------
  const COLS = UI.cols;
  const GAP = UI.gap;
  const [slots, setSlots] = useState<(string | "erase" | "submit")[]>(
    new Array(GRID_SIZE).fill(null) as any
  );

  useEffect(() => {
    const next = new Array(GRID_SIZE).fill(null) as (string | "erase" | "submit")[];
    next[ERASE_INDEX] = "erase";
    next[SUBMIT_INDEX] = "submit";
    DIGIT_SLOTS.forEach((idx, i) => {
      next[idx] = digitOrder[i];
    });
    setSlots(next);
  }, [digitOrder]);

  const [gridWState, setGridWState] = useState(0);
  const keySize = useMemo(() => {
    const w = gridWState || gridW;
    if (w <= 0) return 0;
    return Math.floor((w - GAP * (COLS - 1)) / COLS);
  }, [gridWState, gridW, COLS, GAP]);

  const onGridLayout = (e: LayoutChangeEvent) => {
    const w = Math.floor(e.nativeEvent.layout.width);
    setGridW(w);
    setGridWState(w);
  };

  // Rendu d'une touche
  const renderSlot = useCallback(
    (k: string | "erase" | "submit", idx: number) => {
      const isErase = k === "erase";
      const isSubmit = k === "submit";
      const isDigit = !isErase && !isSubmit;

      // Symboles
      const visualLabel = isErase ? "••" : isSubmit ? "•" : (k as string);
      const a11yLabel = isErase ? "Effacer" : isSubmit ? "Valider" : `Chiffre ${k}`;

      const onPress = isErase ? erase : isSubmit ? submit : () => pressNumber(k as string);

      // HIDE actif → on masque seulement le texte des chiffres (pas •• / •)
      const shouldHide = activeModeRef.current === "HIDE" && isDigit;

      const styleKey = {
        width: keySize,
        height: keySize,
        marginRight: (idx % COLS) !== COLS - 1 ? GAP : 0,
        marginBottom: GAP,
      } as const;

      return (
        <Pressable
          key={`slot-${idx}`}
          style={({ pressed }) => [
            styles.keyBase,
            styleKey,
            pressed && styles.keyPressed,
            disabled && { opacity: 0.5 },
          ]}
          onPress={onPress}
          accessibilityRole="button"
          accessibilityLabel={a11yLabel}
          hitSlop={8}
          disabled={disabled}
          testID={`calc-key-${k}-${idx}`}
        >
          <Text style={[styles.keyText, shouldHide && { opacity: 0 }]}>
            {visualLabel}
          </Text>
        </Pressable>
      );
    },
    [erase, submit, pressNumber, disabled, keySize, COLS, GAP]
  );

  return (
    <View style={[styles.container, style]}>
      {/* Afficheur */}
      <View style={styles.display} testID="calc-display">
        <Text style={styles.displayText}>{local || " "}</Text>
      </View>

      {/* Grille 3×4 */}
      <View style={styles.grid} onLayout={onGridLayout}>
        {keySize > 0 && slots.map((k, idx) => renderSlot(k, idx))}
      </View>
    </View>
  );
}

// Styles
const styles = StyleSheet.create({
  container: { gap: 12, flexGrow: 1 },
  display: {
    borderWidth: 1,
    borderColor: COLORS.displayBorder,
    backgroundColor: "transparent",
    borderRadius: UI.displayRadius,
    paddingVertical: 12,
    paddingHorizontal: 14,
    minHeight: 52,
    justifyContent: "center",
  },
  displayText: {
    color: COLORS.displayText,
    fontSize: UI.displayFontSize,
    textAlign: "center",
    fontWeight: "700",
  },
  grid: {
    flex: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    alignContent: "flex-start",
    justifyContent: "flex-start",
  },
  keyBase: {
    borderRadius: UI.keyRadius,
    backgroundColor: COLORS.keyBg,
    borderWidth: 1,
    borderColor: COLORS.keyBg,
    justifyContent: "center",
    alignItems: "center",
  },
  keyPressed: { opacity: 0.88 },
  keyText: {
    fontSize: UI.keyFontSize,
    fontWeight: "800",
    color: COLORS.keyText,
  },
});


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

/** ========================================================================
 * Calculator (Pixel) — 4×3 keypad, grouped & thumb-friendly
 * - 4 rows × 3 cols (fixed)
 * - Horizontal: keys inside a centered cluster (clusterRatio of grid width)
 * - Vertical: rows block positioned with verticalBias (0 top … 1 bottom)
 * - keyScale (default 0.88), gap (default 10), compactDisplay (optional)
 * - Sounds, haptics, HIDE/SHUFFLE unchanged
 * ======================================================================== */

const COLORS = {
  keyBg: "#4C5BCE",
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
  displayHeight: 64,
};

type HapticsNS = {
  impactAsync?: (s: any) => Promise<void>;
  selectionAsync?: () => Promise<void>;
  notificationAsync?: (t: any) => Promise<void>;
  ImpactFeedbackStyle?: any;
  NotificationFeedbackType?: any;
} | null;
let H: HapticsNS = null;
try { H = require("expo-haptics"); } catch { H = null; }

type Range = { min: number; max: number };
type DestabMode = "HIDE" | "SHUFFLE";

type Props = {
  value?: string;
  onChangeText?: (text: string) => void;
  onSubmit?: (text: string) => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;

  currentIndex?: number;
  destabilizeEnabled?: boolean;
  hideChance?: number;
  hideRange?: Range;
  shuffleChance?: number;
  shuffleRange?: Range;

  keyScale?: number;         // size multiplier for keys (default 0.88)
  gap?: number;              // minimal spacing between keys (default 10)
  compactDisplay?: boolean;  // reduce display height slightly
  clusterRatio?: number;     // keypad cluster width vs grid width (default 0.78)
  verticalBias?: number;     // 0 top … 0.5 center … 1 bottom (default 0.7)
};

const BASE_ORDER = ["4", "8", "2", "5", "0", "1", "7", "6", "3", "9"];
const GRID_SIZE = 12;
const ROWS = 4;
const COLS = 3;
const ERASE_INDEX = 9;
const SUBMIT_INDEX = 11;
const DIGIT_SLOTS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10];

const randInt = (min: number, max: number) =>
  Math.floor(min + Math.random() * (max - min + 1));
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
  hideChance = 0.05,
  hideRange = { min: 1, max: 2 },
  shuffleChance = 0.1,
  shuffleRange = { min: 1, max: 2 },

  keyScale = 0.88,
  gap,
  compactDisplay = false,
  clusterRatio = 0.78,
  verticalBias = 2,     // 👈 pousse le pavé vers le bas par défaut
}: Props) {
  const [local, setLocal] = useState<string>(value);

  // Grid area (under the display)
  const [gridW, setGridW] = useState(0);
  const [gridH, setGridH] = useState(0);

  const soundRef = useRef<Audio.Sound | null>(null);

  const activeModeRef = useRef<DestabMode | null>(null);
  const activeRemainingRef = useRef<number>(0);
  const pendingModeRef = useRef<DestabMode | null>(null);
  const pendingRemainingRef = useRef<number>(0);

  const [digitOrder, setDigitOrder] = useState<string[]>(BASE_ORDER);

  useEffect(() => setLocal(value), [value]);

  // --- AUDIO ---
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
        soundRef.current = null;
      }
    })();
    return () => {
      mounted = false;
      try { soundRef.current?.unloadAsync(); } catch {}
    };
  }, []);

  // --- activate pending mode on new op ---
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

    activeModeRef.current = pendingModeRef.current;
    activeRemainingRef.current = pendingRemainingRef.current;
    pendingModeRef.current = null;
    pendingRemainingRef.current = 0;

    setDigitOrder(activeModeRef.current === "SHUFFLE" ? shuffleArr(BASE_ORDER) : BASE_ORDER);
  }, [currentIndex, destabilizeEnabled]);

  // --- Haptics ---
  const hTap = () => H?.impactAsync?.(H.ImpactFeedbackStyle?.Light).catch(() => {});
  const hSelect = () => H?.selectionAsync?.().catch(() => {});
  const hSuccess = () => H?.notificationAsync?.(H.NotificationFeedbackType?.Success).catch(() => {});

  // --- Actions ---
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

    if (!destabilizeEnabled) return;

    if (activeModeRef.current) {
      const remain = Math.max(0, (activeRemainingRef.current || 0) - 1);
      activeRemainingRef.current = remain;
      if (remain === 0) activeModeRef.current = null;
    }

    if (activeModeRef.current && activeRemainingRef.current > 0) {
      pendingModeRef.current = activeModeRef.current;
      pendingRemainingRef.current = activeRemainingRef.current;
      return;
    }

    const h = Math.random() < (hideChance ?? 0.05);
    const s = Math.random() < (shuffleChance ?? 0.10);

    if (!h && !s) {
      pendingModeRef.current = null;
      pendingRemainingRef.current = 0;
      return;
    }

    let chosen: DestabMode = "HIDE";
    if (h && s) chosen = Math.random() < 0.5 ? "HIDE" : "SHUFFLE";
    else if (s) chosen = "SHUFFLE";

    const range = chosen === "HIDE"
      ? (hideRange ?? { min: 1, max: 2 })
      : (shuffleRange ?? { min: 1, max: 2 });

    const duration = Math.max(1, randInt(range.min, range.max));
    pendingModeRef.current = chosen;
    pendingRemainingRef.current = duration;
  }, [disabled, onSubmit, local, destabilizeEnabled, hideChance, hideRange, shuffleChance, shuffleRange]);

  // --- Sizing ---
  const GAP = gap ?? UI.gap;

  // Key size from width/height (using cluster width) then scaled
  const clusterWidth = useMemo(() => {
    if (gridW <= 0) return 0;
    return Math.floor(gridW * Math.min(1, Math.max(0.5, clusterRatio)));
  }, [gridW, clusterRatio]);

  const keySizeRaw = useMemo(() => {
    if (clusterWidth <= 0) return 0;
    const byWidth = Math.floor((clusterWidth - GAP * (COLS - 1)) / COLS);
    const byHeight = gridH > 0 ? Math.floor((gridH - GAP * (ROWS - 1)) / ROWS) : byWidth;
    return Math.min(byWidth, byHeight);
  }, [clusterWidth, gridH, GAP]);

  const keySize = Math.max(0, Math.floor(keySizeRaw * keyScale));

  // Vertical spacing + bias: distribute the free space with a bias to the bottom
  const vGap = useMemo(() => {
    if (gridH <= 0 || keySize <= 0) return GAP;
    const minRowsHeight = ROWS * keySize + (ROWS - 1) * GAP;
    if (gridH <= minRowsHeight) return GAP;
    // keep uniform gaps between rows, at least GAP
    const extra = gridH - ROWS * keySize;
    return Math.max(GAP, Math.floor(extra / Math.max(1, ROWS - 1)));
  }, [gridH, keySize, GAP]);

  // pads top/bottom with bias
  const { topPad, bottomPad } = useMemo(() => {
    if (gridH <= 0 || keySize <= 0) return { topPad: 0, bottomPad: 0 };
    const used = ROWS * keySize + (ROWS - 1) * vGap;
    const free = Math.max(0, gridH - used);
    const bias = Math.min(1, Math.max(0, verticalBias));
    const top = Math.floor(free * (1 - bias));
    const bottom = free - top;
    return { topPad: top, bottomPad: bottom };
  }, [gridH, keySize, vGap, verticalBias]);

  const sidePad = useMemo(() => Math.max(0, Math.floor((gridW - clusterWidth) / 2)), [gridW, clusterWidth]);

  const onGridLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setGridW(Math.floor(width));
    setGridH(Math.floor(height));
  };

  // Slots with erase/submit
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

  const renderKey = useCallback(
    (k: string | "erase" | "submit", idx: number) => {
      const isErase = k === "erase";
      const isSubmit = k === "submit";
      const isDigit = !isErase && !isSubmit;

      const visualLabel = isErase ? "••" : isSubmit ? "•" : (k as string);
      const a11yLabel = isErase ? "Effacer" : isSubmit ? "Valider" : `Chiffre ${k}`;
      const onPress = isErase ? erase : isSubmit ? submit : () => pressNumber(k as string);

      const shouldHide = activeModeRef.current === "HIDE" && isDigit;
      const dynFontSize = Math.max(16, Math.floor(keySize * 0.44));

      return (
        <Pressable
          key={`key-${idx}`}
          style={({ pressed }) => [
            styles.keyBase,
            { width: keySize, height: keySize, borderRadius: UI.keyRadius },
            pressed && styles.keyPressed,
            disabled && { opacity: 0.5 },
          ]}
          onPress={onPress}
          accessibilityRole="button"
          accessibilityLabel={a11yLabel}
          hitSlop={8}
          disabled={disabled}
        >
          <Text style={[styles.keyText, { fontSize: dynFontSize }, shouldHide && { opacity: 0 }]}>
            {visualLabel}
          </Text>
        </Pressable>
      );
    },
    [erase, submit, pressNumber, disabled, keySize]
  );

  const rows = useMemo(() => [
    [slots[0], slots[1], slots[2]],
    [slots[3], slots[4], slots[5]],
    [slots[6], slots[7], slots[8]],
    [slots[9], slots[10], slots[11]],
  ], [slots]);

  const displayH = compactDisplay ? Math.max(36, Math.floor(UI.displayHeight * 0.75)) : UI.displayHeight;
  const displayFont = compactDisplay ? Math.max(18, Math.floor(UI.displayFontSize * 0.85)) : UI.displayFontSize;

  return (
    <View style={[styles.container, style]}>
      {/* Display */}
      <View style={[styles.display, { minHeight: displayH }]}>
        <Text style={[styles.displayText, { fontSize: displayFont }]}>{local || " "}</Text>
      </View>

      {/* Grid area */}
      <View style={styles.grid} onLayout={onGridLayout}>
        {/* Top pad with bias */}
        <View style={{ height: topPad }} />
        {keySize > 0 && rows.map((row, r) => (
          <View
            key={`row-${r}`}
            style={[
              styles.row,
              { marginBottom: r < ROWS - 1 ? vGap : 0, paddingHorizontal: sidePad },
            ]}
          >
            <View style={[styles.rowInner, { width: clusterWidth }]}>
              {row[0] != null && renderKey(row[0] as any, r * 3 + 0)}
              {row[1] != null && renderKey(row[1] as any, r * 3 + 1)}
              {row[2] != null && renderKey(row[2] as any, r * 3 + 2)}
            </View>
          </View>
        ))}
        {/* Bottom pad mirrors with bias */}
        <View style={{ height: bottomPad }} />
      </View>
    </View>
  );
}

// Styles
const styles = StyleSheet.create({
  container: { gap: 12, flexGrow: 1, flexShrink: 1 },
  display: {
    borderWidth: 1,
    borderColor: COLORS.displayBorder,
    backgroundColor: "transparent",
    borderRadius: UI.displayRadius,
    paddingVertical: 12,
    paddingHorizontal: 14,
    justifyContent: "center",
  },
  displayText: {
    color: COLORS.displayText,
    textAlign: "center",
    fontWeight: "700",
  },
  grid: {
    flexGrow: 1,
    flexShrink: 1,
    justifyContent: "flex-start",
  },
  row: {
    flexDirection: "row",
    justifyContent: "center",
  },
  rowInner: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignSelf: "center",
  },
  keyBase: {
    backgroundColor: COLORS.keyBg,
    borderWidth: 1,
    borderColor: COLORS.keyBg,
    justifyContent: "center",
    alignItems: "center",
  },
  keyPressed: { opacity: 0.88 },
  keyText: {
    fontWeight: "800",
    color: COLORS.keyText,
  },
});

import React, { useEffect, useImperativeHandle, useMemo, useRef, useState, forwardRef } from "react";
import Svg, { Rect } from "react-native-svg";

type Props = {
  /** Nombre de micro-pixels "de base" (état persistant) */
  lit: number;
  /** colonnes x lignes = capacité */
  cols?: number;
  rows?: number;
  /** taille (px) du gros carré */
  size?: number;
  /** seed pour garder un ordre visuel stable dans le temps */
  seed?: number;
  /** vitesse en ms entre deux incréments (10–25ms recommandé) */
  stepMs?: number;
  /** nombre max de pixels à animer par appel (par défaut 30) */
  maxDelta?: number;
  /** couleur des pixels allumés */
  color?: string;
};

/** API exposée au parent pour déclencher l'animation post-entraînement */
export type BigPixelHandle = {
  /** Applique un score (-30..+30) en animant précisément |score| micro-pixels */
  applyScore: (score: number) => Promise<void>;
  /** Anime jusqu'à une cible absolue */
  animateTo: (targetLit: number) => Promise<void>;
};

function mulberry32(a: number) {
  return function () {
    let t = (a += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const BigPixel = forwardRef<BigPixelHandle, Props>(function BigPixel(
  {
    lit,
    cols = 100,
    rows = 100,
    size = 350,
    seed = 1337,
    stepMs = 18,
    maxDelta = 30,
    color = "#6C5CE7",
  },
  ref
) {
  const capacity = cols * rows;
  const cell = size / cols;

  /** ordre stable et joli des cellules -> positionsShuffled[i] donne (row, col) */
  const positionsShuffled = useMemo(() => {
    const rng = mulberry32(seed);
    const arr: [number, number][] = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) arr.push([r, c]);
    // Fisher-Yates seedé
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }, [rows, cols, seed]);

  /** Compteur actuel animé (décorrélé de la prop lit pour pouvoir animer) */
  const currentLitRef = useRef(Math.max(0, Math.min(lit, capacity)));
  const [renderTick, setRenderTick] = useState(0); // force re-render quand on touche currentLitRef

  // Si la prop lit change (re-hydratation ou reset), on se recale sans animer
  useEffect(() => {
    const next = Math.max(0, Math.min(lit, capacity));
    if (next !== currentLitRef.current) {
      currentLitRef.current = next;
      setRenderTick((t) => t + 1);
    }
  }, [lit, capacity]);

  const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

  const animateSteps = async (delta: number) => {
    if (delta === 0) return;
    const dir = Math.sign(delta); // +1 fill, -1 unfill
    const steps = Math.min(Math.abs(delta), maxDelta);
    for (let i = 0; i < steps; i++) {
      const next = currentLitRef.current + dir;
      if (next < 0 || next > capacity) break;
      currentLitRef.current = next;
      setRenderTick((t) => t + 1); // redraw avec |currentLitRef.current| premiers indices
      await sleep(stepMs);
    }
  };

  const animateTo = async (targetLit: number) => {
    const target = Math.max(0, Math.min(targetLit, capacity));
    const delta = target - currentLitRef.current;
    await animateSteps(delta);
  };

  const applyScore = async (score: number) => {
    const capped = Math.max(-maxDelta, Math.min(maxDelta, Math.trunc(score)));
    await animateSteps(capped);
  };

  useImperativeHandle(ref, () => ({ applyScore, animateTo }), [applyScore, animateTo]);

  // On dessine uniquement les currentLit premiers indices dans l'ordre shuffle
  const litPositions = positionsShuffled.slice(0, currentLitRef.current);

  return (
    <Svg width={size} height={size}>
      {/* Fond blanc avec contour subtil */}
      <Rect x={0} y={0} width={size} height={size} fill="#FFFFFF" stroke="#E5E5E5" strokeWidth={1} />
      {litPositions.map(([r, c], i) => (
        <Rect key={i} x={c * cell} y={r * cell} width={cell} height={cell} fill={color} />
      ))}
    </Svg>
  );
});

export default BigPixel;

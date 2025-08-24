import React from "react";
import Svg, { Rect } from "react-native-svg";

type Props = { lit: number; cols?: number; rows?: number; size?: number };

export default function BigPixel({ lit, cols = 350, rows = 350, size = 350 }: Props) {
  const capacity = cols * rows;
  const clamped = Math.max(0, Math.min(lit, capacity));
  const cell = size / cols;

  // Génère toutes les positions possibles
  const positions: [number, number][] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      positions.push([r, c]);
    }
  }

  // Mélange les positions
  for (let i = positions.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [positions[i], positions[j]] = [positions[j], positions[i]];
  }

  // Sélectionne les "lit" premiers pixels
  const litPositions = positions.slice(0, clamped);

  return (
    <Svg width={size} height={size}>
      {/* Fond blanc */}
      <Rect x={0} y={0} width={size} height={size} fill="#FFFFFF" stroke="#E5E5E5" strokeWidth={1} />
      {litPositions.map(([r, c], i) => (
        <Rect
          key={i}
          x={c * cell}
          y={r * cell}
          width={cell}
          height={cell}
          fill="#6C5CE7"
        />
      ))}
    </Svg>
  );
}

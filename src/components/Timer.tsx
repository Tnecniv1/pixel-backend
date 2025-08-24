import React, { useEffect, useState } from "react";
import { Text } from "react-native";
import { theme } from "../theme";

export default function Timer({ keySeed = 0 }: { keySeed?: number }) {
  const [sec, setSec] = useState(0);
  useEffect(() => {
    setSec(0);
    const id = setInterval(() => setSec(s => s + 1), 1000);
    return () => clearInterval(id);
  }, [keySeed]);

  const mm = String(Math.floor(sec / 60)).padStart(2, "0");
  const ss = String(sec % 60).padStart(2, "0");
  return (
    <Text style={{ color: theme.colors.subtext, fontVariant: ["tabular-nums"] }}>
      ⏱ {mm}:{ss}
    </Text>
  );
}

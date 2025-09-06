import "react-native-url-polyfill/auto";
import "react-native-get-random-values";
import React, { useEffect } from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import HomeScreen from "./src/screens/HomeScreen";
import EntrainementScreen from "./src/screens/EntrainementScreen";
import TrainScreen from "./src/screens/TrainScreen";
import ResultScreen from "./src/screens/ResultScreen";
import ReviewScreen from "./src/screens/ReviewScreen";
import AuthScreen from "./src/screens/AuthScreen";
import ProgressionScreen from "./src/screens/ProgressionScreen";
import LeaderboardScreen from "./src/screens/LeaderboardScreen";
import InfoScreen from "./src/screens/InfoScreen";
import SignUpScreen from "./src/screens/SignUpScreen";
import PaywallScreen from "./src/screens/PaywallScreen"; 

import { AuthProvider, useAuth } from "./src/auth";

import Purchases from "react-native-purchases";
import Constants from "expo-constants";

/* --------------------------- RevenueCat (désactivé par défaut) --------------------------- */
async function initRevenueCat(userId?: string) {
  try {
    const extra: any = Constants?.expoConfig?.extra ?? {};

    // Feature flag: n’active RC que si RC_ENABLED=true (env ou app.json.extra)
    const enabledEnv = `${process.env.EXPO_PUBLIC_RC_ENABLED ?? ""}`.toLowerCase();
    const enabled =
      extra?.RC_ENABLED === true ||
      enabledEnv === "true" ||
      enabledEnv === "1";

    if (!enabled) {
      console.log("[RC] Désactivé → skip init");
      return;
    }

    const apiKey =
      process.env.EXPO_PUBLIC_RC_API_KEY ??
      extra?.EXPO_PUBLIC_RC_API_KEY ??
      extra?.RC_API_KEY;

    if (!apiKey) {
      console.warn("[RC] ⚠️ Pas de clé RC → skip init");
      return;
    }

    await Purchases.configure({ apiKey, appUserID: userId ?? null });
    console.log("[RC] ✅ Configuré", userId ? `(user=${userId})` : "(anonyme)");
  } catch (e) {
    console.error("[RC] ❌ Erreur init:", e);
  }
}

/* ------------------------- Types de navigation ------------------------- */
export type ReviewItem = {
  operation: string;
  expected: number;
  userAnswer: number;
  operateurUn?: number;
  operateurDeux?: number;
};

export type RootStackParamList = {
  Auth: undefined;
  SignUp: undefined;
  Home: undefined;
  Paywall: undefined;
  Entrainement: undefined;
  Train: { volume: number };
  Result: {
    entrainementId: number;
    parcoursId?: number;
    score: number;
    total: number;
    mistakes: ReviewItem[];
    mode?: "mixte" | "mono";
  };
  Review: {
    entrainementId: number;
    mistakes: ReviewItem[];
    mode?: "mixte" | "mono";
  };
  Progression: { parcoursId: number };
  Leaderboard: undefined;
  Info: undefined;


};

const Stack = createNativeStackNavigator<RootStackParamList>();

/* --------------------------- Router --------------------------- */
function Router() {
  const { authUid, loading } = useAuth();

  useEffect(() => {
    // Init RevenueCat (feature-flag)
    if (authUid) initRevenueCat(authUid);
    else initRevenueCat();
  }, [authUid]);

  if (loading) return null;

  if (!authUid) {
    return (
      <Stack.Navigator>
        <Stack.Screen
          name="Auth"
          component={AuthScreen}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="SignUp"
          component={SignUpScreen}
          options={{ title: "Créer un compte" }}
        />
      </Stack.Navigator>
    );
  }

  return (
    <Stack.Navigator initialRouteName="Home" screenOptions={{ headerShown: true }}>
      <Stack.Screen
        name="Home"
        component={HomeScreen}
        options={{ title: "Pixel - Calcul Mental" }}
      />
      <Stack.Screen
        name="Paywall"
        component={PaywallScreen}
        options={{ title: "Abonnement"}}
        />
      <Stack.Screen
        name="Entrainement"
        component={EntrainementScreen}
        options={{ title: "Entraînement" }}
      />
      <Stack.Screen
        name="Train"
        component={TrainScreen}
        options={{ title: "Session" }}
      />
      <Stack.Screen
        name="Result"
        component={ResultScreen}
        options={{ title: "Résultats" }}
      />
      <Stack.Screen
        name="Review"
        component={ReviewScreen}
        options={{ title: "Correction" }}
      />
      <Stack.Screen
        name="Leaderboard"
        component={LeaderboardScreen}
        options={{ title: "Classement" }}
      />
      <Stack.Screen
        name="Progression"
        component={ProgressionScreen}
        options={{ title: "Progression" }}
      />
      <Stack.Screen
        name="Info"
        component={InfoScreen}
        options={{ title: "Informations" }}
      />
    </Stack.Navigator>
  );
}

/* --------------------------- App --------------------------- */
export default function App() {
  return (
    <AuthProvider>
      <NavigationContainer>
        <Router />
      </NavigationContainer>
    </AuthProvider>
  );
}



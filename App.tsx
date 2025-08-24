import "react-native-url-polyfill/auto";
import "react-native-get-random-values";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import HomeScreen from "./src/screens/HomeScreen";
import EntrainementScreen from "./src/screens/EntrainementScreen"; 
import TrainScreen from "./src/screens/TrainScreen";
import ResultScreen from "./src/screens/ResultScreen";
import ReviewScreen from "./src/screens/ReviewScreen";
import AuthScreen from "./src/screens/AuthScreen";
import ProgressionScreen from "./src/screens/ProgressionScreen";
import { AuthProvider, useAuth } from "./src/auth";
import LeaderboardScreen from "./src/screens/LeaderboardScreen";
import Purchases from 'react-native-purchases';

/* ------------------------- Types partagés ------------------------- */


export type ReviewItem = {
  operation: string;
  expected: number;
  userAnswer: number;
  operateurUn?: number;
  operateurDeux?: number;
};

export type RootStackParamList = {
  Auth: undefined;
  Home: undefined;                 // Accueil (2 CTA : Entrainement / Progression)
  Entrainement: undefined;         // 👈 Pré-session (niveaux + choix volume)
  Train: { volume: number };       // Session en cours (uniquement volume)
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
  Progression: { parcoursId: number }; // Carrousel d’analyse
  Leaderboard: undefined; // 👈 ajoute ceci
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const RC_API_KEY = process.env.EXPO_PUBLIC_RC_API_KEY!;

/* --------------------------- Router --------------------------- */
function Router() {
  const { authUid, loading } = useAuth();

  if (loading) return null; // (option) afficher un splash ici

  // Non connecté → stack d'auth uniquement
  if (!authUid) {
    return (
      <Stack.Navigator>
        <Stack.Screen
          name="Auth"
          component={AuthScreen}
          options={{ headerShown: false }}
        />
      </Stack.Navigator>
    );
  }

  // Connecté → stack principale
  return (
    <Stack.Navigator initialRouteName="Home" screenOptions={{ headerShown: true }}>
      <Stack.Screen
        name="Home"
        component={HomeScreen}
        options={{ title: "Pixel - Calcul Mental" }}
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
    </Stack.Navigator>
  );
}

/* --------------------------- App --------------------------- */
export default function App() {
  useEffect(() => {
    (async () => {
      // Configure RevenueCat avec ta clé publique
      await Purchases.configure({ apiKey: RC_API_KEY });

      // Connecte l'abonnement à ton utilisateur supabase
      const { data } = await supabase.auth.getUser();
      const authUid = data?.user?.id;
      if (authUid) {
        await Purchases.logIn(authUid);
      }
    })();
  }, []);
  
  return (
    <AuthProvider>
      <NavigationContainer>
        <Router />
      </NavigationContainer>
    </AuthProvider>
  );
}


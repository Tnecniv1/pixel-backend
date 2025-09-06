import React, { useEffect, useState } from "react";
import { View, Text, Button, ActivityIndicator, Alert, Platform, Linking } from "react-native";
import Purchases, { PurchasesPackage, CustomerInfo } from "react-native-purchases";

export default function PaywallScreen({ navigation }: any) {
  const [loading, setLoading] = useState(true);
  const [monthly, setMonthly] = useState<PurchasesPackage | null>(null);
  const [yearly, setYearly]   = useState<PurchasesPackage | null>(null);
  const [isPro, setIsPro]     = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        // 1) offres
        const offerings = await Purchases.getOfferings();
        console.log("[RC] offerings.current:", offerings.current);
        console.log("[RC] packages:", offerings.current?.availablePackages?.map(p => ({
          id: p.identifier,
          type: p.packageType,
          productId: p.product.identifier,
          price: p.product.priceString,
        })));
        const current = offerings.current;
        if (current) {
          setMonthly(current.availablePackages.find(p => p.packageType === "MONTHLY") || null);
          setYearly(current.availablePackages.find(p => p.packageType === "ANNUAL") || null);
        }
        // 2) état actuel
        const info = await Purchases.getCustomerInfo();
        setIsPro(!!info.entitlements.active.pro);
      } catch (e: any) {
        Alert.alert("Erreur", e?.message ?? "Impossible de charger les offres.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const buy = async (pkg: PurchasesPackage | null) => {
    if (!pkg) return;
    try {
      const { customerInfo } = await Purchases.purchasePackage(pkg);
      const pro = !!customerInfo.entitlements.active.pro;
      setIsPro(pro);
      if (pro) navigation.goBack(); // débloqué → on ferme le paywall
    } catch (e: any) {
      // annulé ou erreur
      const code = e?.userCancelled ? "Achat annulé" : (e?.message || "Erreur d’achat");
      console.log("[purchase] ", code);
    }
  };

  const restore = async () => {
    try {
      const { customerInfo } = await Purchases.restorePurchases();
      const pro = !!customerInfo.entitlements.active.pro;
      setIsPro(pro);
      if (pro) navigation.goBack();
      else Alert.alert("Info", "Aucun achat à restaurer.");
    } catch (e: any) {
      Alert.alert("Erreur", e?.message ?? "Restauration impossible.");
    }
  };

  const manage = () => {
    if (Platform.OS === "ios") {
      Linking.openURL("itms-apps://apps.apple.com/account/subscriptions");
    } else {
      Linking.openURL("https://play.google.com/store/account/subscriptions");
    }
  };

  if (loading) {
    return (
      <View style={{ flex:1, alignItems:"center", justifyContent:"center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  if (isPro) {
    return (
      <View style={{ padding:16, gap:12 }}>
        <Text style={{ fontSize:18, fontWeight:"600" }}>Déjà PRO 🎉</Text>
        <Button title="Gérer mon abonnement" onPress={manage} />
      </View>
    );
  }

  return (
    <View style={{ padding:16, gap:12 }}>
      <Text style={{ fontSize:22, fontWeight:"700" }}>Deviens PRO</Text>
      <Text>Essai gratuit 3 jours, puis abonnement. Annulable à tout moment.</Text>

      <Button
        title={monthly ? `Mensuel — ${monthly.product.priceString}` : "Mensuel"}
        onPress={() => buy(monthly)}
      />
      <Button
        title={yearly ? `Annuel — ${yearly.product.priceString}` : "Annuel"}
        onPress={() => buy(yearly)}
      />

      <Button title="Restaurer mes achats" onPress={restore} />
      <Button title="Gérer mon abonnement" onPress={manage} />
    </View>
  );
}

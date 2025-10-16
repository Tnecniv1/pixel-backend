import React from 'react';
import { View, Text, ScrollView } from 'react-native';

type Props = { children: React.ReactNode };
type State = { error?: any };

export default class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: undefined };

  static getDerivedStateFromError(error: any) {
    return { error };
  }

  componentDidCatch(error: any, info: any) {
    try { console.error('[FATAL]', String(error), info?.componentStack); } catch {}
  }

  render() {
    if (!this.state.error) return this.props.children;
    const msg = (this.state.error?.message ?? String(this.state.error) ?? 'Unknown error');
    return (
      <ScrollView contentContainerStyle={{ flexGrow: 1, padding: 16, justifyContent: 'center' }}>
        <View>
          <Text style={{ fontSize: 18, fontWeight: '600', marginBottom: 8 }}>
            Oups — erreur de démarrage JS
          </Text>
          <Text selectable>{msg}</Text>
          <Text style={{ marginTop: 12, opacity: 0.7 }}>
            L’app ne s’éteindra plus : l’erreur est affichée pour diagnostic.
          </Text>
        </View>
      </ScrollView>
    );
  }
}

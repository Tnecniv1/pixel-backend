// DEBUT - Code de debug temporaire
import { Alert } from 'react-native';

const originalError = console.error;
console.error = (...args) => {
  originalError(...args);
  const errorMsg = args.map(a => String(a)).join(' ');
  Alert.alert('ERREUR DÉTECTÉE', errorMsg.substring(0, 500));
};

if (!__DEV__) {
  ErrorUtils.setGlobalHandler((error, isFatal) => {
    Alert.alert(
      'CRASH IMMINENT',
      `${error.name}: ${error.message}\n\nStack: ${error.stack?.substring(0, 300)}`,
      [{ text: 'OK' }]
    );
  });
}
// FIN - Code de debug temporaire

import { registerRootComponent } from 'expo';

import App from './App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
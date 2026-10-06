import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'cl.stepsapp.movil',
  appName: 'Steps Móvil',
  webDir: 'dist',
  server: { androidScheme: 'https' },
  android: { useLegacyBridge: true },
};
export default config;

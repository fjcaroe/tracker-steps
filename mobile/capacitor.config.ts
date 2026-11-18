import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'comm.stepsapp.mobile',
  appName: 'Steps App',
  webDir: 'dist',
  server: { androidScheme: 'https' },
  android: { useLegacyBridge: true },
};
export default config;

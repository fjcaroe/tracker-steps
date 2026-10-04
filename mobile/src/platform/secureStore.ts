// Almacén de credenciales. Nativo: Keychain (iOS) / Keystore (Android) mediante @aparajita/capacitor-secure-storage.
// Web: NO existe almacenamiento seguro equivalente; los tokens viven solo en sessionStorage (se pierden al cerrar la pestaña) para
// reducir la exposición ante XSS. La API usa cabecera Bearer, no cookies, por lo que no hay superficie CSRF.
import { Capacitor } from '@capacitor/core';

export interface SecureStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

export function memorySecureStore(): SecureStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return { data, async get(k) { return data.get(k) ?? null; }, async set(k, v) { data.set(k, v); }, async remove(k) { data.delete(k); } };
}

export const webSessionStore: SecureStore = {
  async get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
  async set(key, value) { try { sessionStorage.setItem(key, value); } catch { /* sin sessionStorage: la sesión no persiste */ } },
  async remove(key) { try { sessionStorage.removeItem(key); } catch { /* nada */ } },
};

export const nativeSecureStore: SecureStore = {
  async get(key) {
    const { SecureStorage } = await import('@aparajita/capacitor-secure-storage');
    const value = await SecureStorage.get(key, false, false);
    return typeof value === 'string' ? value : value == null ? null : JSON.stringify(value);
  },
  async set(key, value) {
    const { SecureStorage } = await import('@aparajita/capacitor-secure-storage');
    await SecureStorage.set(key, value, false, false);
  },
  async remove(key) {
    const { SecureStorage } = await import('@aparajita/capacitor-secure-storage');
    await SecureStorage.remove(key, false);
  },
};

export const selectSecureStore = (): SecureStore => (Capacitor.isNativePlatform() ? nativeSecureStore : webSessionStore);

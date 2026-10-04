import { Capacitor } from '@capacitor/core';
import type { DeviceInfo } from '../shared/contracts';
import { uuid } from '../sync/queue';
import type { KeyValueStore } from '../shared/storage';
import { APP_VERSION } from '../app/version';

const KEY = 'steps.device.uuid.v1';

/** Identificador estable de esta instalación (no es un dato personal ni un secreto). */
export async function deviceInfo(kv: KeyValueStore): Promise<DeviceInfo> {
  let id = await kv.get(KEY);
  if (!id) { id = uuid(); await kv.set(KEY, id); }
  const platform = Capacitor.getPlatform();
  return { uuid: id, platform, label: platform === 'web' ? 'Navegador' : platform === 'ios' ? 'iPhone / iPad' : 'Android', app_version: APP_VERSION };
}

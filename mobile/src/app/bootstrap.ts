import { MODULES } from '../modules';
import { supportedContracts } from '../modules/registry';
import { deviceInfo } from '../platform/device';
import { selectSecureStore, memorySecureStore } from '../platform/secureStore';
import { localKv } from '../shared/storage';
import { Runtime } from './runtime';
import { SessionManager } from './session';

export function createRuntime(): Runtime {
  const session = new SessionManager({ kv: localKv, secure: selectSecureStore(), device: () => deviceInfo(localKv), supported: supportedContracts(MODULES) });
  return new Runtime(session, localKv, MODULES);
}

/** Modo demostración (`npm run demo`): servidor falso con datos ficticios; se elimina de las compilaciones normales. */
export async function createDemoRuntime(): Promise<{ runtime: Runtime; email: string; title: string; password: string }> {
  const { scenario, DEMO_PASSWORD } = await import('../testing/demo');
  const name = (new URLSearchParams(location.search).get('scenario') ?? 'conductor') as Parameters<typeof scenario>[0];
  const s = scenario(name);
  const session = new SessionManager({ kv: s.kv, secure: memorySecureStore(), device: async () => ({ uuid: 'demo-device', platform: 'web', label: 'Demo', app_version: 'demo' }), supported: supportedContracts(MODULES), fetchImpl: s.server.fetch, baseUrl: 'https://demo.invalid/steps_app/v1' });
  const runtime = new Runtime(session, s.kv, MODULES);
  // Inicia sesión sola para mostrar el escenario; «nuevo» queda en la bienvenida.
  if (s.email && name !== 'nuevo') { await session.boot(); await session.login(s.email, DEMO_PASSWORD); await s.seed(); await runtime.refresh(); }
  return { runtime, email: s.email, title: s.title, password: DEMO_PASSWORD };
}

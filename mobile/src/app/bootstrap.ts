import { MODULES } from '../modules';
import { supportedContracts } from '../modules/registry';
import { deviceInfo } from '../platform/device';
import { selectSecureStore } from '../platform/secureStore';
import { localKv } from '../shared/storage';
import { Runtime } from './runtime';
import { SessionManager } from './session';

export function createRuntime(): Runtime {
  const session = new SessionManager({ kv: localKv, secure: selectSecureStore(), device: () => deviceInfo(localKv), supported: supportedContracts(MODULES) });
  return new Runtime(session, localKv, MODULES);
}

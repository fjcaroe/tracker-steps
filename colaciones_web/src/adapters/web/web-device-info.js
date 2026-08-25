import { createUuid } from "../../core/identity.js";

const INSTALL_KEY = "steps_colaciones_install_id";

/**
 * `DeviceInfo` de la PWA.
 *
 * El identificador de instalación es un UUID aleatorio generado en el equipo:
 * no deriva de hardware ni de datos del navegador, por lo que no permite
 * rastrear a la persona que lo usa. Sirve para que un administrador reconozca
 * qué equipo está sincronizando.
 */
export function createWebDeviceInfo({
  storage = globalThis.localStorage,
  appVersion = "",
  platform = "web",
} = {}) {
  function installId() {
    let value = storage.getItem(INSTALL_KEY);
    if (!value) {
      value = createUuid();
      storage.setItem(INSTALL_KEY, value);
    }
    return value;
  }

  return {
    installId,
    async describe() {
      return {
        installId: installId(),
        platform,
        appVersion,
        appBuild: appVersion,
      };
    },
    /** Carga útil enviada a Odoo: sin datos personales ni de red. */
    async payload() {
      return {
        uuid: installId(),
        platform,
        app_version: appVersion,
      };
    },
  };
}

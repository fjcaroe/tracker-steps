// Manifiestos tipados de módulos. El código de cada módulo VIAJA EN LA APP; Odoo solo entrega catálogo y autorizaciones.
// Habilitar un módulo en Odoo muestra uno instalado y compatible; agregar funcionalidad nueva exige actualizar la app.
import type { ComponentType } from 'react';
import type { Api } from '../app/api';
import type { Runtime } from '../app/runtime';
import type { Handler } from '../sync/engine';

export type ModuleProps = { runtime: Runtime; onExit: () => void };

export type ModuleManifest = {
  /** Identificador estable: coincide con `step.app.module.code` en Odoo. */
  id: string;
  /** Versión de contrato servidor↔app que este código entiende. */
  contractVersion: number;
  name: string;
  /** Texto corto para la tarjeta (el icono visual lo define la capa de presentación). */
  tagline: string;
  icon: string;
  /** Permisos nativos que el módulo puede pedir, solo al ejecutar la acción que los necesita. */
  capabilities: ('camera' | 'gps' | 'background-gps')[];
  /** El módulo se muestra si la persona tiene AL MENOS uno de estos permisos en la empresa activa. */
  requiredPermissions: string[];
  load: () => Promise<{ default: ComponentType<ModuleProps> }>;
  /** Handlers de sincronización, con clave `<módulo>:<tipo de operación>`. */
  handlers?: (api: Api) => Record<string, Handler>;
};

export const supportedContracts = (manifests: ModuleManifest[]): Record<string, number> => Object.fromEntries(manifests.map((m) => [m.id, m.contractVersion]));

/** Módulos que se muestran: instalados en la app, autorizados por el catálogo y con algún permiso requerido vigente. */
export function visibleModules(manifests: ModuleManifest[], catalog: { modules: { code: string; permissions: string[] }[] } | null) {
  if (!catalog) return [];
  return manifests.flatMap((m) => {
    const granted = catalog.modules.find((c) => c.code === m.id);
    return granted && m.requiredPermissions.some((p) => granted.permissions.includes(p)) ? [{ manifest: m, permissions: granted.permissions }] : [];
  });
}

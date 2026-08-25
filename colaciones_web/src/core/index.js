/**
 * Punto de entrada del núcleo compartido de Colaciones.
 *
 * La PWA lo importa directamente; la App móvil lo consume a través del
 * submódulo `vendor/steps_colaciones`. Todo lo que se exporte aquí debe
 * funcionar sin DOM y sin APIs propias de una plataforma.
 */
export * from "./constants.js";
export * from "./errors.js";
export * from "./identity.js";
export { createApiClient, readCapabilities } from "./api-client.js";
export { createQueue, backoffDelay, QueueFullError } from "./queue.js";
export { createSyncEngine } from "./sync-engine.js";
export { createTotemSession } from "./totem-session.js";
export { buildDiagnostics } from "./diagnostics.js";
export { migrateLegacyQueue } from "./migrations.js";

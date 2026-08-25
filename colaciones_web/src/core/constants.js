/**
 * Constantes del dominio de Colaciones.
 *
 * Este directorio (`web/src/core`) es la única fuente de verdad de la lógica
 * compartida entre la PWA y la App móvil. No debe importar nada del DOM, de
 * Capacitor ni de Node: todo lo específico de plataforma entra por adaptadores.
 */

/** Versión del núcleo compartido. Se informa en el diagnóstico. */
export const CORE_VERSION = "2.0.0";

/** Versión del contrato HTTP que este núcleo sabe hablar. */
export const SUPPORTED_API_VERSION = 2;

/** Estados de una captura en la cola local. */
export const QUEUE_STATE = Object.freeze({
  PENDING: "pending",
  SYNCING: "syncing",
  SYNCED: "synced",
  TERMINAL_ERROR: "terminal_error",
});

/** Clasificación de un error para decidir si se reintenta. */
export const ERROR_KIND = Object.freeze({
  /** Sin red o servidor no disponible: conservar y reintentar. */
  TEMPORARY: "temporary",
  /** Rechazo funcional del servidor: no reintentar indefinidamente. */
  TERMINAL: "terminal",
});

export const DEFAULT_LIMITS = Object.freeze({
  /** Máximo de capturas conservadas antes de rechazar nuevas. */
  maxQueueRecords: 500,
  /** A partir de aquí se avisa al operador que debe recuperar conexión. */
  warnQueueRecords: 100,
  /** Horas sin sincronizar tras las cuales se muestra una alerta. */
  warnOfflineHours: 24,
  /** Capturas enviadas por lote. El servidor confirma el máximo real. */
  maxBatchRecords: 100,
  /** Capturas ya confirmadas que se conservan para el diagnóstico. */
  keepSyncedRecords: 25,
  /** Intentos fallidos temporales antes de marcar la captura como problemática. */
  warnAttempts: 5,
});

export const BACKOFF = Object.freeze({
  baseMs: 5_000,
  factor: 2,
  maxMs: 5 * 60_000,
  jitterRatio: 0.2,
});

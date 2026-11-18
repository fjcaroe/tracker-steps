// Mensajes para personas, por código estable del servidor. El texto del servidor es solo respaldo.
import { ApiError } from './api';
import { StorageError } from '../shared/storage';

const BY_CODE: Record<string, string> = {
  network: 'Sin conexión con el servidor. Tus datos siguen guardados en el teléfono.',
  invalid_credentials: 'Correo o contraseña incorrectos.',
  too_many_attempts: 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.',
  email_in_use: 'Ese correo ya tiene una cuenta. Prueba con «Ingresar».',
  weak_password: 'La contraseña es muy débil: usa al menos 10 caracteres y que no sea tu correo.',
  invalid_email: 'Revisa el correo: no parece válido.',
  invalid_invitation: 'El código de invitación no es válido o ya venció.',
  email_not_verified: 'Confirma tu correo con el código recibido o pide a tu administrador que revise tu cuenta.',
  invalid_recovery: 'El código de recuperación no es válido o ya venció. Pide uno nuevo.',
  invalid_verification: 'El código de verificación no es válido o ya venció.',
  invalid_org_code: 'No reconocemos ese código de empresa.',
  organization_not_authorized: 'No tienes acceso activo a esa empresa.',
  forbidden: 'No tienes permiso para esta acción. Consulta a tu administrador.',
  trip_not_found: 'Ese servicio no está asignado a ti.',
  totem_not_authorized: 'No tienes autorizado ese tótem.',
  driver_not_linked: 'Tu cuenta aún no está vinculada a un chofer. Pide al administrador que la vincule.',
  provider_not_configured: 'Este método de ingreso aún no está disponible.',
  session_invalid: 'Tu sesión expiró. Vuelve a entrar.',
  session_revoked: 'Tu sesión fue cerrada por seguridad. Vuelve a entrar.',
  too_many_devices: 'Tienes demasiados dispositivos activos. Cierra alguno desde otro equipo.',
  device_revoked: 'Este teléfono fue desvinculado de tu cuenta.',
  server_error: 'El servidor tuvo un problema. Inténtalo de nuevo en un momento.',
};

export function messageFor(error: unknown, fallback = 'No se pudo completar la acción.'): string {
  if (error instanceof StorageError) return error.message;
  if (error instanceof ApiError) return BY_CODE[error.code] ?? (error.message && error.message !== error.code ? error.message : fallback);
  return (error as Error)?.message || fallback;
}

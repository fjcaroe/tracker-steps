/**
 * Identificadores del dispositivo y de cada captura.
 *
 * El UUID de captura hace idempotente el reenvío; el UUID de instalación
 * permite a Odoo saber qué equipo está usando un tótem sin guardar datos
 * personales ni de red.
 */

const HEX = "0123456789abcdef";

function randomHex(length, random) {
  let out = "";
  for (let index = 0; index < length; index += 1) {
    out += HEX[Math.floor(random() * 16)];
  }
  return out;
}

/**
 * Genera un UUID v4. Usa `crypto.randomUUID` cuando existe y, si no, una
 * construcción manual: WebView antiguos y contextos no seguros no la exponen.
 */
export function createUuid({ crypto: cryptoImpl = globalThis.crypto, random = Math.random } = {}) {
  if (cryptoImpl && typeof cryptoImpl.randomUUID === "function") {
    return cryptoImpl.randomUUID();
  }
  if (cryptoImpl && typeof cryptoImpl.getRandomValues === "function") {
    const bytes = cryptoImpl.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  const hex = randomHex(32, random);
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20)}`;
}

/**
 * Enmascara un token para mostrarlo o exportarlo en un diagnóstico.
 * Nunca debe mostrarse el valor completo fuera del formulario de Odoo.
 */
export function maskToken(token) {
  const value = (token || "").trim();
  if (!value) return "(sin asociar)";
  if (value.length <= 8) return `${"•".repeat(value.length - 2)}${value.slice(-2)}`;
  return `${value.slice(0, 4)}…${value.slice(-4)}`;
}

/**
 * Enmascara un identificador de trabajador para no conservar el dato completo
 * en el dispositivo más tiempo del necesario.
 */
export function maskIdentifier(identifier, { visible = 4 } = {}) {
  const value = (identifier || "").trim();
  if (!value) return "";
  if (value.length <= visible) return "•".repeat(value.length);
  return `${"•".repeat(value.length - visible)}${value.slice(-visible)}`;
}

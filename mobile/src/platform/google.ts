// Inicio de sesión con Google. PENDIENTE de configuración externa: requiere el ID de cliente OAuth de Google (Android/iOS/Web) y un plugin
// nativo que use el flujo del sistema (no una WebView propia, RFC 8252). Mientras `googleIdToken` sea null la interfaz no ofrece el botón,
// y el servidor responde `provider_not_configured`. No se simula un inicio de sesión exitoso.
export const googleIdToken: null | (() => Promise<string>) = null;

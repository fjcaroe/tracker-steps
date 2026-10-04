// Preferencias de terreno (I14): letra, modo noche, botones grandes (guantes), sonidos y límite de velocidad.
export type Settings = { fontScale: number; night: 'auto' | 'on' | 'off'; gloves: boolean; sound: boolean; speedLimitKmh: number; breakAfterMin: number; seenHelp: boolean };
export const DEFAULTS: Settings = { fontScale: 1, night: 'auto', gloves: false, sound: true, speedLimitKmh: 30, breakAfterMin: 240, seenHelp: false };
const KEY = 'steps_movil_settings';

export function loadSettings(): Settings {
  try { const raw = localStorage.getItem(KEY); return { ...DEFAULTS, ...(raw ? (JSON.parse(raw) as Partial<Settings>) : {}) }; } catch { return { ...DEFAULTS }; }
}
export function saveSettings(s: Settings) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* modo privado */ } }

/** Aplica las preferencias al documento mediante atributos y una variable CSS. */
export function applySettings(s: Settings, root: HTMLElement = document.documentElement) {
  root.style.setProperty('--font-scale', String(s.fontScale));
  root.dataset.gloves = s.gloves ? 'on' : 'off';
  root.dataset.night = s.night;
}

/** Pitido corto de aviso (sin archivos de audio: funciona sin conexión). */
export function beep(enabled: boolean) {
  if (!enabled) return;
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx(); const osc = ctx.createOscillator(); const gain = ctx.createGain();
    osc.frequency.value = 880; gain.gain.value = 0.15; osc.connect(gain); gain.connect(ctx.destination);
    osc.start(); osc.stop(ctx.currentTime + 0.25); osc.onended = () => void ctx.close();
  } catch { /* sin audio */ }
  try { navigator.vibrate?.(200); } catch { /* sin vibración */ }
}

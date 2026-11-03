// The native app cannot use the web dev proxy or a localhost fallback.
const base = process.env.VITE_STEPS_API_BASE;
let url;
try { url = new URL(base); } catch { throw new Error('Set VITE_STEPS_API_BASE to the authorized HTTPS pilot /steps_app/v1 endpoint.'); }
if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || !url.pathname.endsWith('/steps_app/v1') || /^(localhost|127\.|0\.|\[::1\])/.test(url.hostname)) {
  throw new Error('The iPhone pilot requires an HTTPS backend, no credentials in the URL, and the /steps_app/v1 path.');
}
console.log('Pilot endpoint validated (URL omitted).');

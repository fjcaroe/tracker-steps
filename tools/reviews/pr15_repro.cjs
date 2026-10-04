// Variante parametrizada del script de revisión de la PR #15 (original en codex/cierre-cambios-locales). Úsese con LIB_DIR/SCREENS_DIR para el diseño actual.
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = process.argv[2];
const LIB = process.env.LIB_DIR || 'lib', SCREENS = process.env.SCREENS_DIR || 'screens';
if (!root || !fs.existsSync(path.join(root, 'src', LIB, 'queue.ts'))) {
  throw new Error('Usage: [LIB_DIR=modules/tracker/lib SCREENS_DIR=modules/tracker/screens] node tools/reviews/pr15_repro.cjs /absolute/path/to/mobile (npm ci required)');
}
const ts = require(path.join(root, 'node_modules/typescript'));
const modules = {};
const store = new Map();
let refuseArchive = false;
const callbacks = [], updates = [];
let ops = [];
let resolveOpen;
const react = {
  useState: init => { const value = typeof init === 'function' ? init() : init; const index = updates.length; updates.push([]); return [value, next => updates[index].push(next)]; },
  useCallback: cb => { callbacks.push(cb); return cb; },
  useEffect: () => {}, useRef: value => ({ current: value }),
};
const storage = {
  getItem: key => store.get(key) ?? null,
  setItem: (key, value) => { if (refuseArchive && key === 'steps_movil_points_rejected') throw new Error('QuotaExceededError'); store.set(key, value); },
  removeItem: key => store.delete(key),
};
function load(rel) {
  if (modules[rel]) return modules[rel].exports;
  const module = { exports: {} }; modules[rel] = module;
  const source = fs.readFileSync(path.join(root, 'src', rel), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const requireMock = name => {
    if (name === 'react') return react;
    if (name === 'react/jsx-runtime') return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }), Fragment: 'fragment' };
    if (name.endsWith('/api') || name === './api') return { sessions: { open: () => new Promise(resolve => { resolveOpen = resolve; }) } };
    if (name.endsWith('/sync')) return { outboxStore: { ops: () => ops }, syncAll: async () => {} };
    for (const filename of ['queue', 'outbox', 'reconcile']) if (name.endsWith('/' + filename)) return load(LIB + '/' + filename + '.ts');
    return {};
  };
  vm.runInNewContext(code, { module, exports: module.exports, require: requireMock, localStorage: storage, console, Date, Set }, { filename: rel });
  return module.exports;
}
(async () => {
  const queue = load(LIB + '/queue.ts').pointQueue;
  const point = n => ({ ts: new Date(n * 1000).toISOString(), lat: -35, lon: -71, speed_mps: null, accuracy_m: 5 });
  const reject = async () => { throw Object.assign(new Error('closed'), { status: 400 }); };
  queue.push('quota', point(0)); refuseArchive = true;
  await queue.flush('quota', reject);
  console.log(JSON.stringify({ case: 'archive-write-failure', pending: queue.size('quota'), archived: queue.rejected().quota?.length ?? 0, lost: queue.size('quota') === 0 && !queue.rejected().quota }));
  refuseArchive = false; store.clear();
  store.set('steps_movil_pending', JSON.stringify({ cap: Array.from({ length: 5001 }, (_, i) => point(i)) }));
  await queue.flush('cap', reject);
  console.log(JSON.stringify({ case: 'archive-cap', original: 5001, archived: queue.rejected().cap.length, missingOldest: !queue.rejected().cap.some(p => p.ts === point(0).ts) }));
  store.clear(); callbacks.length = 0; updates.length = 0; ops = [];
  load(SCREENS + '/Journey.tsx').default({ online: true, preset: null, onPresetUsed: () => {} });
  const checking = callbacks[1]();
  // The GET already has an old snapshot. A close is queued and drained while it is in flight.
  // Como en la app real, terminar la jornada deja constancia persistente (finishedStore) ANTES de encolar el cierre.
  const fin = load(LIB + '/queue.ts').finishedStore; if (fin) fin.add('closed-during-get');
  ops = [{ kind: 'session_close', sessionId: 'closed-during-get', endedAt: '2026-10-03T13:00:00Z' }];
  ops = [];
  resolveOpen([{ id: 'closed-during-get', status: 'open', machine_id: 7, started_at: '2026-10-03T12:00:00Z' }]);
  await checking;
  console.log(JSON.stringify({ case: 'close-drained-during-get', offered: updates[3].at(-1)?.map(s => s.id) }));
})();

import { useEffect, useState } from 'react';
import { fleetRequest, type FleetContext } from '../services/fleetApi';
import type { Zone, ZoneDraft, ZoneReport } from '../services/fleetZones';
import sample from '../demo/zone-report.json';
export const demoZoneReport = sample as ZoneReport;
export function useFleetZones(context: FleetContext | null, demo: boolean) {
  const [realZones, setRealZones] = useState<Zone[]>([]);
  const [demoZones, setDemoZones] = useState<Zone[]>([demoZoneReport.zone]);
  const [error, setError] = useState(''); const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!context || demo) return;
    let active = true;
    const load = async () => { try { const rows = await fleetRequest<Zone[]>('zones', context); if (active) { setRealZones(rows); setError(''); } } catch (e) { if (active) setError((e as Error).message); } };
    void load(); const timer = setInterval(() => void load(), 60000);
    return () => { active = false; clearInterval(timer); };
  }, [context, demo, tick]);
  const save = async (draft: ZoneDraft, existing?: Zone) => {
    if (!context) throw new Error('Carga tu sesión antes de guardar.');
    if (draft.vertices.length < 3 || draft.vertices.length > 100) throw new Error('Usa entre 3 y 100 vértices.');
    let saved: Zone;
    if (demo) {
      saved = { ...draft, id: existing?.id || crypto.randomUUID(), version: (existing?.version || 0)+1, area_m2: 0, perimeter_m: 0, created_at: existing?.created_at || new Date().toISOString(), updated_at: new Date().toISOString() };
      setDemoZones(rows => [...rows.filter(z => z.id !== saved.id), saved]);
    } else {
      saved = await fleetRequest<Zone>(existing ? `zones/${existing.id}` : 'zones', context, existing ? 'PATCH' : 'POST', { ...draft, ...(existing ? { version: existing.version } : {}) });
      setRealZones(rows => [...rows.filter(z => z.id !== saved.id), saved]);
    }
    return saved;
  };
  return { zones: demo ? demoZones : realZones, error: demo ? '' : error, refresh: () => setTick(n => n+1), save };
}

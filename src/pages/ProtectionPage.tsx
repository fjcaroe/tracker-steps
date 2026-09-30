import { useEffect, useState } from 'react';
import { allPages, dateLabel, fleetRequest, label, type FleetAsset, type FleetContext, type Incident, type Policy } from '../services/fleetApi';

export type DemoProtection = { incidents: Incident[]; policies: Policy[] };
export default function ProtectionPage({ context, assets, selected, demo, refresh, demoStore, onDemoChange }: { context: FleetContext; assets: FleetAsset[]; selected: string | null; demo: boolean; refresh: () => void; demoStore: DemoProtection; onDemoChange: (value: DemoProtection) => void }) {
  const [incidents, setIncidents] = useState<Incident[]>(demo ? demoStore.incidents : []);
  const [policies, setPolicies] = useState<Policy[]>(demo ? demoStore.policies : []);
  const [detail, setDetail] = useState<Incident | null>(null);
  const [assetId, setAssetId] = useState(selected || assets[0]?.asset_id || '');
  const [reason, setReason] = useState('');
  const [contacts, setContacts] = useState('');
  const [kind, setKind] = useState('manual');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const operator = context.role !== 'viewer';
  const manager = context.role === 'manager';
  useEffect(() => { if (demo) onDemoChange({ incidents, policies }); }, [demo, incidents, policies, onDemoChange]);
  useEffect(() => {
    if (demo) return;
    let active = true;
    const load = async () => {
      try {
        const [rows, settings] = await Promise.all([allPages<Incident>('security/incidents', context), fleetRequest<Policy[]>('security/policies', context)]);
        if (active) { setIncidents(rows); setPolicies(settings); }
      } catch (e) { if (active) setMessage((e as Error).message); }
    };
    void load(); const timer = window.setInterval(() => void load(), 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, [context, demo, revision]);
  const policy = policies.find(p => p.asset_id === assetId);
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setMessage('');
    try { await action(); setReason(''); setRevision(v => v+1); refresh(); }
    catch (e) { setMessage((e as Error).message); }
    finally { setBusy(false); }
  };
  const open = (row: Incident) => void run(async () => setDetail(demo ? row : await fleetRequest<Incident>(`security/incidents/${row.id}`, context)));
  const create = () => void run(async () => {
    const row = demo ? { id: crypto.randomUUID(), asset_id: assetId, type: kind, severity: 'medium', state: 'open', responsible: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), timeline: [{ id: crypto.randomUUID(), actor: 'Demo', action: 'incident_opened', detail: { reason }, created_at: new Date().toISOString() }] } : await fleetRequest<Incident>('security/incidents', context, 'POST', { asset_id: assetId, type: kind, reason });
    if (demo) setIncidents(rows => [...rows, row]); setDetail(row);
  });
  const update = (state: string) => void run(async () => {
    if (!detail) return;
    const row = demo ? { ...detail, state, timeline: [...(detail.timeline || []), { id: crypto.randomUUID(), actor: 'Demo', action: state, detail: { reason }, created_at: new Date().toISOString() }] } : await fleetRequest<Incident>(`security/incidents/${detail.id}`, context, 'PATCH', { state, reason });
    setDetail(row); if (demo) setIncidents(rows => rows.map(r => r.id === row.id ? row : r));
  });
  const arm = () => void run(async () => {
    const value = { asset_id: assetId, armed: !policy?.armed, version: policy?.version || 0, reason,
      contacts: contacts ? contacts.split(',').map(c => c.trim()).filter(Boolean) : policy?.contacts || [],
      allowed_hours_utc: policy?.allowed_hours_utc || [], zone: policy?.zone || null };
    if (demo) setPolicies(rows => [...rows.filter(p => p.asset_id !== assetId), { ...value, version: value.version+1 }]);
    else await fleetRequest('security/policies', context, 'PUT', value);
    setMessage(value.armed ? 'Protección armada. Movimiento o ACC genera aviso durante todo el día hasta configurar horarios autorizados.' : 'Protección desarmada.');
  });
  return <section className="protection-workspace"><div className="fleet-notice"><strong>Protección digital</strong><span>Avisos en esta bandeja. Envío externo y atención humana 24/7 no configurados. Control físico deshabilitado.</span></div>{message && <p role="status" className="fleet-notice">{message}</p>}<div className="protection-grid"><section className="fleet-panel"><h2>Armado y registro</h2><label>Equipo<select value={assetId} onChange={e => { setAssetId(e.target.value); setContacts(''); }}>{assets.map(a => <option value={a.asset_id} key={a.asset_id}>{a.name}</option>)}</select></label><p>Estado: <strong>{policy?.armed ? 'Armada' : 'Desarmada'}</strong></p><label>Motivo de la acción<textarea value={reason} minLength={5} maxLength={2000} onChange={e => setReason(e.target.value)} placeholder="Qué ocurrió o por qué cambia la protección"/></label>{manager && <><label>Contactos de referencia (separados por coma)<input value={contacts} onChange={e => setContacts(e.target.value)} placeholder={policy?.contacts.join(', ') || 'Responsable y teléfono'}/></label><button disabled={busy || !assetId || reason.trim().length < 5} onClick={arm}>{policy?.armed ? 'Desarmar' : 'Armar'} protección</button><p className="fleet-note">Armado continuo. Contactos guardados como referencia, sin envío automático.</p></>}{operator && <><label>Tipo de incidente<select value={kind} onChange={e => setKind(e.target.value)}>{['manual', 'suspected_movement', 'external_power_lost', 'communication_failure', 'sos', 'outside_zone'].map(k => <option key={k} value={k}>{label(k)}</option>)}</select></label><button className="fleet-primary" disabled={busy || !assetId || reason.trim().length < 5} onClick={create}>Registrar incidente</button></>}</section><section className="fleet-panel"><h2>Incidentes <span>{incidents.length}</span></h2>{!incidents.length && <p>No hay incidentes registrados.</p>}{[...incidents].sort((a,b) => b.created_at.localeCompare(a.created_at)).map(i => <button className="fleet-card" key={i.id} onClick={() => open(i)} aria-pressed={detail?.id === i.id}><strong>{label(i.type)}</strong><span>{assets.find(a => a.asset_id === i.asset_id)?.name || 'Equipo fuera del filtro'}</span><span>{label(i.severity)} · {label(i.state)}</span><small>{dateLabel(i.created_at)}</small></button>)}</section><section className="fleet-panel"><h2>Expediente</h2>{detail ? <><h3>{label(detail.type)}</h3><p>{label(detail.state)} · {dateLabel(detail.created_at)}</p><ol className="fleet-timeline">{detail.timeline?.map(e => <li key={e.id}><strong>{label(e.action)}</strong><small>{dateLabel(e.created_at)} · {e.actor}</small><p>{String(e.detail.reason || (e.action === 'notification_pending' ? 'Aviso disponible en la bandeja. Entrega externa no configurada.' : JSON.stringify(e.detail)))}</p></li>)}</ol>{operator && detail.state !== 'closed' && <button disabled={busy || reason.trim().length < 5} onClick={() => update(detail.state === 'open' ? 'acknowledged' : 'closed')}>{detail.state === 'open' ? 'Reconocer incidente' : 'Cerrar con motivo'}</button>}<p className="fleet-note">Usa el motivo del formulario para documentar la decisión y cualquier falsa alarma.</p></> : <p>Selecciona un incidente para ver evidencia, responsables y decisiones.</p>}<hr/><h3>Inhibición del próximo arranque</h3><p>Instalación no homologada. No hay despacho de órdenes al vehículo.</p><button disabled>Solicitar inhibición · no disponible</button><p className="fleet-note">Una respuesta del GPS no confirma la actuación del relé.</p></section></div></section>;
}

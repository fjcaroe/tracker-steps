import { useCallback, useEffect, useRef, useState } from 'react';
import TrackerIcon from '../components/TrackerIcon';
import { allPages, dateLabel, FleetApiError, fleetRequest, label, type FleetAsset, type FleetContext, type Incident, type Policy } from '../services/fleetApi';
import './ProtectionPage.css';
import StarterControl from '../components/StarterControl';

export type DemoProtection = { incidents: Incident[]; policies: Policy[] };
type Confirmation = Policy & { reason: string };
const presets = ['Salida autorizada', 'Prueba finalizada', 'Vehículo estacionado', 'Mantenimiento'];

export default function ProtectionPage({ context, assets, selected, demo, refresh, demoStore, onDemoChange }: { context: FleetContext; assets: FleetAsset[]; selected: string | null; demo: boolean; refresh: () => void; demoStore: DemoProtection; onDemoChange: (value: DemoProtection) => void }) {
  const [incidents, setIncidents] = useState<Incident[]>(demo ? demoStore.incidents : []);
  const [policies, setPolicies] = useState<Policy[]>(demo ? demoStore.policies : []);
  const [detail, setDetail] = useState<Incident | null>(null);
  const [assetId, setAssetId] = useState(selected || assets[0]?.asset_id || '');
  const [reason, setReason] = useState('');
  const [contacts, setContacts] = useState<string | null>(null);
  const [incidentReason, setIncidentReason] = useState('');
  const [caseReason, setCaseReason] = useState('');
  const [kind, setKind] = useState('manual');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [policyError, setPolicyError] = useState('');
  const [incidentError, setIncidentError] = useState('');
  const [ready, setReady] = useState(demo);
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const reasonInput = useRef<HTMLTextAreaElement>(null);
  const serial = useRef(0), inFlight = useRef(false);
  const operator = context.role !== 'viewer', manager = context.role === 'manager' || context.can_manage_protection === true;
  const policy = policies.find(p => p.asset_id === assetId);
  const asset = assets.find(a => a.asset_id === assetId);
  const visibleIncidents = incidents.filter(i => showAll || i.asset_id === assetId).sort((a,b) => b.created_at.localeCompare(a.created_at));
  const openCount = incidents.filter(i => i.asset_id === assetId && i.state !== 'closed').length;

  useEffect(() => { if (demo) onDemoChange({ incidents, policies }); }, [demo, incidents, policies, onDemoChange]);
  useEffect(() => { if (selected && assets.some(a => a.asset_id === selected)) setAssetId(selected); }, [selected, assets]);
  const load = useCallback(async (foreground = false) => {
    if (demo) return;
    const sequence = ++serial.current;
    if (foreground) setReady(false);
    // Failed incident reads must never replace a policy with an unverified default.
    const [settings, rows] = await Promise.allSettled([fleetRequest<Policy[]>('security/policies', context), allPages<Incident>('security/incidents', context)]);
    if (sequence !== serial.current) return;
    if (settings.status === 'fulfilled') { setPolicies(settings.value); setPolicyError(''); setReady(true); }
    else { setReady(false); setPolicyError((settings.reason as Error).message); }
    if (rows.status === 'fulfilled') { setIncidents(rows.value); setIncidentError(''); }
    else { setIncidents([]); setDetail(null); setIncidentError((rows.reason as Error).message); }
  }, [context, demo]);
  useEffect(() => {
    void load(true);
    const timer = window.setInterval(() => { if (!inFlight.current) void load(); }, 30000);
    return () => { serial.current++; window.clearInterval(timer); };
  }, [load]);
  useEffect(() => { if (confirmation) dialog.current?.showModal(); else dialog.current?.close(); }, [confirmation]);

  const run = async (action: () => Promise<void>) => {
    if (inFlight.current) return;
    inFlight.current = true; serial.current++; setBusy(true); setError(''); setMessage('');
    try { await action(); refresh(); }
    catch (e) {
      if (e instanceof FleetApiError && e.status === 409) {
        setConfirmation(null);
        setError('El estado cambió mientras trabajabas. Lo actualizamos; revisa el estado y vuelve a confirmar tu acción. Tu motivo se conserva.');
        await load(true);
      } else setError((e as Error).message);
    } finally { inFlight.current = false; setBusy(false); }
  };
  const prepare = () => {
    if (!ready || busy || !asset || !manager) return;
    if (reason.trim().length < 5) { setError('Escribe un motivo de al menos 5 caracteres o elige una opción rápida.'); reasonInput.current?.focus(); return; }
    if (reason.trim().length > 2000) { setError('El motivo admite hasta 2.000 caracteres.'); return; }
    const referenceContacts = contacts === null ? policy?.contacts || [] : contacts.split(',').map(c => c.trim()).filter(Boolean);
    if (referenceContacts.length > 10 || referenceContacts.some(c => c.length > 200)) { setError('Puedes guardar hasta 10 contactos, con un máximo de 200 caracteres por contacto.'); return; }
    setError('');
    setConfirmation({ asset_id: assetId, armed: !policy?.armed, version: policy?.version || 0, reason: reason.trim(), contacts: referenceContacts, allowed_hours_utc: policy?.allowed_hours_utc || [], zone: policy?.zone || null });
  };
  const confirmPolicy = () => void run(async () => {
    if (!confirmation) return;
    if (demo) setPolicies(rows => [...rows.filter(p => p.asset_id !== confirmation.asset_id), { ...confirmation, version: confirmation.version+1 }]);
    else {
      // Never toggle an unseen state or automatically retry a security action.
      const settings = await fleetRequest<Policy[]>('security/policies', context);
      const current = settings.find(p => p.asset_id === confirmation.asset_id);
      if ((current?.version || 0) !== confirmation.version) { setPolicies(settings); throw new FleetApiError('Estado actualizado', 409); }
      const result = await fleetRequest<{version:number}>('security/policies', context, 'PUT', confirmation);
      setPolicies(rows => [...rows.filter(p => p.asset_id !== confirmation.asset_id), { ...confirmation, version: result.version }]);
    }
    setMessage(confirmation.armed ? 'Protección armada. Los nuevos eventos se revisan en la bandeja de incidentes.' : 'Protección desarmada. Los incidentes anteriores conservan su historial.');
    setReason(''); setContacts(null); setConfirmation(null);
  });
  const open = (row: Incident) => void run(async () => { setDetail(demo ? row : await fleetRequest<Incident>(`security/incidents/${row.id}`, context)); setCaseReason(''); });
  const create = () => void run(async () => {
    const clean = incidentReason.trim();
    if (clean.length < 5) throw new Error('Describe el incidente con al menos 5 caracteres.');
    const row:Incident = demo ? { id: crypto.randomUUID(), asset_id: assetId, type: kind, severity: kind === 'sos' ? 'high' : 'medium', state: 'open', responsible: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), timeline: [{ id: crypto.randomUUID(), actor: 'Demostración', action: 'incident_opened', detail: { reason: clean }, created_at: new Date().toISOString() }] } : await fleetRequest<Incident>('security/incidents', context, 'POST', { asset_id: assetId, type: kind, reason: clean });
    setIncidents(rows => [...rows.filter(i => i.id !== row.id),row]); setDetail(row); setIncidentReason(''); setCaseReason(''); setMessage('Incidente registrado en la bandeja. No se envió una solicitud a servicios de emergencia.');
  });
  const update = () => void run(async () => {
    if (!detail) return;
    const state = detail.state === 'open' ? 'acknowledged' : 'closed', clean = caseReason.trim();
    if (clean.length < 5) throw new Error('Escribe un motivo de al menos 5 caracteres para continuar.');
    const row = demo ? { ...detail, state, timeline: [...(detail.timeline || []), { id: crypto.randomUUID(), actor: 'Demostración', action: state, detail: { reason: clean }, created_at: new Date().toISOString() }] } : await fleetRequest<Incident>(`security/incidents/${detail.id}`, context, 'PATCH', { state, reason: clean });
    setDetail(row); setIncidents(rows => rows.map(i => i.id === row.id ? row : i)); setCaseReason(''); setMessage(state === 'closed' ? 'Incidente cerrado con su motivo e historial conservados.' : 'Incidente reconocido. Revisa lo ocurrido antes de cerrarlo.');
  });

  return <section className="protection-workspace">
    <div className="protection-hero"><div className="protection-hero-icon"><TrackerIcon name="protection" size={30}/></div><div><span className="protection-kicker">Tú decides cuándo proteger</span><h2>Control claro, en cada paso.</h2><p>Arma las alertas al estacionar. Desármalas antes de una salida autorizada.</p></div><button className="protection-guide-link" onClick={() => document.getElementById("protection-guide")?.scrollIntoView({behavior:"smooth"})}>Cómo funciona ↘</button></div>
    {message && <div role="status" className="protection-feedback is-success">{message}</div>}
    {error && <div role="alert" className="protection-feedback is-error">{error}</div>}
    <div className="protection-top-grid">
      {asset&&!demo&&<StarterControl key={asset.asset_id} asset={asset} context={context}/>}
      <section className="protection-control fleet-panel" aria-labelledby="protection-control-title">
        <div className="protection-section-heading"><div><span className="protection-kicker">01 · Elige el vehículo</span><h2 id="protection-control-title">Armar o desarmar</h2></div><button onClick={() => void load(true)} disabled={busy || demo}>Actualizar estado</button></div>
        <label>Vehículo<select value={assetId} disabled={busy} onChange={e => { setAssetId(e.target.value); setContacts(null); setReason(''); setDetail(null); setError(''); setMessage(''); }}>{assets.map(a => <option value={a.asset_id} key={a.asset_id}>{a.plate ? `${a.plate} · ` : ''}{a.name}</option>)}</select></label>
        {!asset && <p className="fleet-note">Selecciona un vehículo de tu flota para continuar.</p>}
        <div className={'protection-status '+(ready && policy?.armed ? 'is-armed' : '')} aria-live="polite"><TrackerIcon name="protection" size={32}/><div><small>Estado de la protección</small><strong>{!ready ? policyError ? 'Estado sin verificar' : 'Consultando estado…' : policy?.armed ? 'Armada' : 'Desarmada'}</strong><span>{ready ? policy?.armed ? 'Las reglas de protección están activas.' : 'Las alertas automáticas de protección están desactivadas.' : 'Esperamos la confirmación del servidor antes de permitir cambios.'}</span></div></div>
        {policyError && <p role="alert" className="protection-feedback is-error">{policyError} Usa «Actualizar estado» para reintentar.</p>}
        {openCount > 0 && <p className="protection-incident-hint"><strong>{openCount} incidente{openCount > 1 ? 's' : ''} pendiente{openCount > 1 ? 's' : ''}.</strong> Su revisión es independiente del armado. Desarmar no los cierra.</p>}
        {manager ? <><label htmlFor="protection-reason"><span className="protection-kicker">02 · Indica el motivo</span>Motivo del cambio <span className="protection-required">Obligatorio · mínimo 5 caracteres</span></label><div className="protection-presets" aria-label="Motivos rápidos">{presets.map(p => <button key={p} disabled={busy} aria-pressed={reason===p} onClick={() => {setReason(p);setError('');}}>{p}</button>)}</div><textarea id="protection-reason" ref={reasonInput} value={reason} disabled={busy} minLength={5} maxLength={2000} onChange={e => setReason(e.target.value)} placeholder="Ej.: saldré a conducir y quiero desactivar las alertas." aria-describedby="protection-reason-help"/><p id="protection-reason-help" className="fleet-note">Elige un motivo rápido o escribe el tuyo. Quedará registrado para saber quién hizo el cambio y por qué.</p><button className="fleet-primary protection-main-action" disabled={busy || !ready || !asset} onClick={prepare}><TrackerIcon name="protection" size={19}/>{busy ? 'Guardando…' : policy?.armed ? 'Desarmar protección' : 'Armar protección'}</button><p className="protection-action-note">03 · Revisa el vehículo y confirma. El estado cambia cuando el servidor lo guarda.</p></> : <p className="fleet-note">Un administrador de Tracker puede armar o desarmar la protección.</p>}
        <details className="protection-reference"><summary>Contactos y reglas actuales</summary>{manager ? <label>Contactos de referencia<input value={contacts ?? policy?.contacts.join(', ') ?? ''} disabled={busy} onChange={e=>setContacts(e.target.value)} placeholder="Responsable y teléfono, separados por coma"/></label> : <p>Contactos: {policy?.contacts.length ? policy.contacts.join(', ') : 'Sin contactos de referencia.'}</p>}<p>{policy?.allowed_hours_utc.length ? 'Hay horarios autorizados configurados.' : 'Al armar, la supervisión se aplica durante todo el día.'} {policy?.zone ? 'Tiene una zona de protección configurada.' : 'Sin zona de protección configurada.'}</p><p>Los contactos son de referencia; no se les envían avisos automáticamente.</p></details>
      </section>
      <aside className="protection-guide fleet-panel" id="protection-guide"><span className="protection-kicker">Guía rápida</span><h2>Qué ocurre en cada estado</h2><ol><li><b>Arma al estacionar</b><p>Activa la supervisión de eventos recibidos del GPS, según las reglas y datos disponibles.</p></li><li><b>Desarma antes de salir</b><p>Detiene las nuevas alertas automáticas de protección. El GPS sigue mostrando la ubicación y guardando el recorrido.</p></li><li><b>Revisa cada incidente</b><p>Abre su expediente, reconoce lo ocurrido y ciérralo con un motivo cuando esté resuelto.</p></li></ol><div className="protection-scope"><TrackerIcon name="signal" size={22}/><div><strong>Avisos dentro de Tracker</strong><p>Este panel no corta el motor ni activa un relé. No envía SMS, llamadas ni avisos a servicios de emergencia. No incluye atención humana 24/7.</p></div></div></aside>
    </div>
    <div className="protection-bottom-grid"><section className="fleet-panel protection-incidents"><div className="protection-section-heading"><div><span className="protection-kicker">Bandeja de protección</span><h2>Incidentes <span>{visibleIncidents.length}</span></h2></div><label className="protection-inline-toggle"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>Toda la flota</label></div>{incidentError && <p role="alert" className="protection-feedback is-error">No se pudo consultar la bandeja: {incidentError} <button onClick={() => void load()}>Reintentar</button></p>}{!incidentError && !visibleIncidents.length && <div className="protection-empty"><TrackerIcon name="protection" size={30}/><strong>Sin incidentes registrados</strong><p>{showAll ? 'La bandeja de tu flota está vacía.' : 'No hay incidentes para el vehículo seleccionado.'}</p></div>}<div className="protection-incident-list">{visibleIncidents.map(i => <button className="protection-incident" key={i.id} onClick={() => open(i)} disabled={busy} aria-pressed={detail?.id === i.id}><span className={'protection-incident-dot '+(i.state==='closed'?'is-closed':'')}/><div><strong>{label(i.type)}</strong><span>{assets.find(a => a.asset_id === i.asset_id)?.plate || assets.find(a=>a.asset_id===i.asset_id)?.name || 'Equipo fuera del filtro'}</span><small>{dateLabel(i.created_at)}</small></div><span className="protection-chip">{label(i.state)}</span></button>)}</div>
      {operator && <details className="protection-register"><summary>Registrar un incidente o una prueba SOS</summary><p className="fleet-note">Registra lo ocurrido para el vehículo seleccionado. Una prueba SOS crea un expediente en esta bandeja; no solicita ayuda externa.</p><label>Tipo de incidente<select aria-label="Tipo de incidente" value={kind} onChange={e=>setKind(e.target.value)}>{['manual','suspected_movement','external_power_lost','communication_failure','sos','outside_zone'].map(k=><option key={k} value={k}>{label(k)}</option>)}</select></label><label>Descripción del incidente<textarea value={incidentReason} maxLength={2000} onChange={e=>setIncidentReason(e.target.value)} placeholder="Ej.: prueba SOS coordinada, sin una emergencia real."/></label><p className="fleet-note">Obligatoria · mínimo 5 caracteres. Este motivo es independiente del cambio de protección.</p><button className="fleet-primary" disabled={busy || !asset} onClick={create}>Registrar incidente</button></details>}
    </section><section className="fleet-panel protection-case"><span className="protection-kicker">Expediente y seguimiento</span><h2>{detail ? label(detail.type) : 'Cada aviso, con su contexto'}</h2>{detail ? <><span className="protection-chip">{label(detail.state)}</span><p className="fleet-note">{assets.find(a=>a.asset_id===detail.asset_id)?.plate || 'Vehículo'} · {dateLabel(detail.created_at)}</p><ol className="fleet-timeline">{detail.timeline?.map(e=><li key={e.id}><strong>{label(e.action)}</strong><small>{dateLabel(e.created_at)} · {e.actor}</small><p>{String(e.detail.reason || (e.action==='notification_pending'?'Disponible en la bandeja. Sin envío externo.':JSON.stringify(e.detail)))}</p></li>)}</ol>{operator && detail.state!=='closed' && <><label>Motivo del seguimiento<textarea value={caseReason} maxLength={2000} onChange={e=>setCaseReason(e.target.value)} placeholder={detail.state==='open'?'Ej.: revisé el aviso y estoy comprobando lo ocurrido.':'Ej.: prueba finalizada, sin emergencia real.'}/></label><p className="fleet-note">Mínimo 5 caracteres. Primero reconoce el incidente; después puedes cerrarlo. El cierre es definitivo.</p><button disabled={busy} onClick={update}>{detail.state==='open'?'Reconocer incidente':'Cerrar incidente con motivo'}</button></>}</> : <div className="protection-empty"><TrackerIcon name="history" size={32}/><strong>Selecciona un incidente</strong><p>Aquí verás su origen, las decisiones y los motivos registrados.</p></div>}</section></div>
    <dialog ref={dialog} className="protection-confirm" aria-labelledby="protection-confirm-title" onCancel={e=>{if(busy)e.preventDefault();else setConfirmation(null);}}>{confirmation && <><span className="protection-kicker">Último paso · confirmar</span><h2 id="protection-confirm-title">¿{confirmation.armed?'Armar':'Desarmar'} la protección?</h2><p><strong>{asset?.plate || asset?.name}</strong>{asset?.plate ? ` · ${asset.name}` : ''}</p><dl><dt>Nuevo estado</dt><dd>{confirmation.armed?'Armada':'Desarmada'}</dd><dt>Motivo registrado</dt><dd>{confirmation.reason}</dd></dl><p className="fleet-note">{confirmation.armed?'Activa las reglas de alertas digitales del vehículo.':'El GPS seguirá registrando ubicación y recorrido. Los incidentes abiertos no se cierran.'}</p>{error && <p role="alert" className="protection-feedback is-error">{error}</p>}<footer><button disabled={busy} onClick={()=>setConfirmation(null)}>Cancelar</button><button className="fleet-primary" disabled={busy} onClick={confirmPolicy}>{busy?'Guardando…':confirmation.armed?'Confirmar armado':'Confirmar desarmado'}</button></footer></>}</dialog>
  </section>;
}

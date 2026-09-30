import { useEffect, useRef, useState, type FormEvent } from 'react';
import { fleetRequest, type FleetAsset, type FleetContext } from '../services/fleetApi';
export type AssetDetails = Pick<FleetAsset, 'name' | 'plate' | 'type' | 'cost_center' | 'responsible'>;
const assetTypes: Record<string,string> = { vehicle:'Vehículo', car:'Auto', pickup:'Camioneta', van:'Furgón', truck:'Camión', motorcycle:'Moto', tractor:'Tractor', machinery:'Maquinaria', other:'Otro' };
export default function FleetAssetEditor({ asset, context, demo, onClose, onSaved }: { asset?: FleetAsset; context: FleetContext; demo: boolean; onClose: () => void; onSaved: (id: string, data: AssetDetails) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [data, setData] = useState<AssetDetails>({ name:asset?.name || '', plate:asset?.plate || '', type:asset?.type || 'car', cost_center:asset?.cost_center || '', responsible:asset?.responsible || '' });
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { dialog.current?.showModal(); }, []);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); if (busy) return; setBusy(true); setError('');
    const clean = { ...data, name:data.name.trim(), plate:data.plate?.trim().toUpperCase() || null, responsible:data.responsible?.trim() || null, cost_center:data.cost_center?.trim() || null };
    if (!clean.name) { setError('Escribe un nombre para identificar el vehículo.'); setBusy(false); return; }
    try {
      const result = demo ? { asset_id:asset?.asset_id || crypto.randomUUID() } : await fleetRequest<{asset_id:string}>(asset ? 'assets/'+asset.asset_id : 'assets', context, asset ? 'PATCH' : 'POST', clean);
      onSaved(result.asset_id, clean);
    } catch (e) { setError((e as Error).message); setBusy(false); }
  };
  return <dialog ref={dialog} className="tracker-dialog" onCancel={e => { e.preventDefault(); if (!busy) onClose(); }} aria-labelledby="asset-editor-title"><form onSubmit={submit}><div className="tracker-section-title"><div><span className="fleet-eyebrow">{demo ? 'DEMOSTRACIÓN' : context.company}</span><h2 id="asset-editor-title">{asset ? 'Editar vehículo o equipo' : 'Registrar vehículo o equipo'}</h2></div><button type="button" aria-label="Cerrar registro" disabled={busy} onClick={onClose}>×</button></div><p className="fleet-note">Organiza tu flota de autos, transporte y maquinaria. El GPS se asocia después de verificar la instalación.</p>{asset?.linked_to_odoo && <p className="fleet-notice">Este registro viene de Odoo. Una nueva sincronización reemplazará estos datos con los de Flota Odoo.</p>}<div className="tracker-form-grid"><label>Nombre<input autoFocus required maxLength={200} value={data.name} placeholder="Ej. Camioneta de servicio" onChange={e => setData({...data,name:e.target.value})}/></label><label>Tipo<select value={data.type} onChange={e => setData({...data,type:e.target.value})}>{!assetTypes[data.type] && <option value={data.type}>{data.type}</option>}{Object.entries(assetTypes).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label><label>Patente<input maxLength={40} value={data.plate || ''} placeholder="Opcional" onChange={e => setData({...data,plate:e.target.value})}/></label><label>Responsable<input maxLength={200} value={data.responsible || ''} placeholder="Nombre del responsable" onChange={e => setData({...data,responsible:e.target.value})}/></label><label>Centro de costo o sucursal<input maxLength={200} value={data.cost_center || ''} placeholder="Ej. Operaciones Santiago" onChange={e => setData({...data,cost_center:e.target.value})}/></label></div>{error && <p role="alert" className="fleet-error">{error}</p>}<div className="tracker-dialog-actions"><button type="button" disabled={busy} onClick={onClose}>Cancelar</button><button className="fleet-primary" disabled={busy}>{busy ? 'Guardando…' : asset ? 'Guardar cambios' : 'Registrar vehículo'}</button></div></form></dialog>;
}

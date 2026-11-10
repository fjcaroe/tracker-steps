import { useMemo, useState } from 'react';
import TrackerIcon from '../components/TrackerIcon';
import { assignedDriverLabel, assetSignalLabel, dateLabel, emptyFilters, filterFleet, type FleetAsset, type FleetContext, type FleetFilters } from '../services/fleetApi';
export type TrackerView = 'home' | 'live' | 'fleet' | 'protection' | 'settings' | 'zones' | 'ops';
export default function FleetHome({ assets, context, demo, navigate, onCreate, onImport, onFilter, onOpenAsset, busy }: {
  assets: FleetAsset[]; context: FleetContext; demo: boolean; navigate: (view: TrackerView) => void;
  onCreate: () => void; onImport: () => void; onFilter: (filters: Partial<FleetFilters>, view?: TrackerView) => void;
  onOpenAsset: (asset: FleetAsset, view: 'map' | 'history' | 'ops') => void; busy: boolean;
}) {
  const [query, setQuery] = useState('');
  const connected = assets.filter(a => !a.position_stale).length;
  const moving = assets.filter(a => a.motion_state === 'moving').length;
  const pending = assets.filter(a => !a.device).length;
  const incidents = assets.filter(a => a.protection_state === 'incident_open').length;
  const missingDrivers = assets.filter(a => a.driver_name === null).length;
  const visible = useMemo(() => filterFleet(assets, { ...emptyFilters, q: query }), [assets, query]);
  return <div className="tracker-home tracker-workbench">
    <section className="tracker-workbench-intro">
      <div><span className="fleet-eyebrow">Vista general · {context.company}</span><h1>Tu flota, lista para decidir.</h1><p>Ubica cada vehículo, identifica a su conductor y revisa su actividad.</p></div>
      <div><button className="fleet-primary" onClick={() => navigate('live')}><TrackerIcon name="live" size={18}/> Abrir mapa</button><button disabled={demo} onClick={() => navigate('ops')}><TrackerIcon name="ops" size={18}/> Operaciones</button></div>
    </section>
    <section className="tracker-overview" aria-label="Resumen de la compañía">
      {[
        { n: assets.length, title: 'Vehículos y equipos', note: 'Flota de esta compañía', icon: 'fleet', action: () => onFilter({}) },
        { n: connected, title: 'Ubicación reciente', note: 'Posiciones GPS vigentes', icon: 'signal', action: () => onFilter({ signal: 'received' }, 'live') },
        { n: moving, title: 'En movimiento', note: 'Desplazamiento detectado', icon: 'live', action: () => onFilter({ motion: 'moving' }, 'live') },
        { n: incidents, title: 'Incidentes abiertos', note: 'Revisa y da seguimiento', icon: 'protection', action: () => onFilter({ protection: 'incident_open' }, 'protection') },
      ].map(item => <button className="tracker-stat" key={item.title} onClick={item.action}><span className="tracker-stat-icon"><TrackerIcon name={item.icon}/></span><strong>{item.n}</strong><span>{item.title}</span><small>{item.note}</small></button>)}
    </section>
    <div className="tracker-workbench-grid">
      <section className="tracker-home-card tracker-fleet-overview">
        <header className="tracker-section-title"><div><span className="fleet-eyebrow">Acceso por vehículo</span><h2>Patente y conductor, a la vista</h2></div><button onClick={() => navigate('fleet')}>Ver toda la flota →</button></header>
        <label className="workbench-search">Buscar en mi flota<input type="search" placeholder="Patente, vehículo o conductor" value={query} onChange={e => setQuery(e.target.value)}/></label>
        <div className="workbench-vehicle-list">{visible.slice(0, 8).map(asset => <article key={asset.asset_id}>
          <div className="workbench-vehicle-title"><span><TrackerIcon name={asset.type === 'truck' ? 'truck' : 'fleet'} size={23}/></span><div><h3>{asset.plate || asset.name}</h3><p>{asset.name}</p><strong>{assignedDriverLabel(asset)}</strong></div></div>
          <div className="workbench-vehicle-state"><span className={asset.position_stale ? 'is-caution' : 'is-connected'}>{assetSignalLabel(asset)}</span><small>{dateLabel(asset.last_position?.recorded_at)}</small></div>
          <div className="workbench-vehicle-actions"><button aria-label={'Mapa de '+(asset.plate||asset.name)} onClick={() => onOpenAsset(asset, 'map')}>Mapa</button><button aria-label={'Historial de '+(asset.plate||asset.name)} onClick={() => onOpenAsset(asset, 'history')}>Historial</button><button disabled={demo} aria-label={'Operaciones de '+(asset.plate||asset.name)} onClick={() => onOpenAsset(asset, 'ops')}>Operaciones</button></div>
        </article>)}</div>
        {!visible.length && <div className="fleet-empty"><h3>{assets.length ? 'No hay coincidencias' : 'Todavía no hay vehículos en esta compañía'}</h3><p>{assets.length ? 'Prueba con otra patente o conductor.' : 'Revisa la compañía activa o incorpora tu flota desde Odoo.'}</p></div>}
        {visible.length > 8 && <button className="workbench-show-all" onClick={() => onFilter({ q: query })}>Ver los {visible.length} resultados en Flota</button>}
      </section>
      <aside className="tracker-workbench-aside">
        <section className="tracker-home-card"><span className="fleet-eyebrow">Atención de la flota</span><h2>Para revisar</h2><div className="workbench-attention">
          <button onClick={() => onFilter({ signal: 'stale' }, 'live')}><TrackerIcon name="signal"/><span>Posiciones antiguas<small>Revisar conectividad y última ubicación</small></span><b>{assets.filter(a => a.signal_state === 'stale').length}</b></button>
          <button onClick={() => onFilter({ signal: 'no_signal' }, 'live')}><TrackerIcon name="locate"/><span>Sin señal registrada<small>Comprobar instalación o asociación</small></span><b>{assets.filter(a => a.signal_state === 'no_signal').length}</b></button>
          <div><TrackerIcon name="user"/><span>Sin conductor asignado<small>La asignación se gestiona en Flota de Odoo</small></span><b>{missingDrivers}</b></div>
        </div>{missingDrivers > 0 && <a className="workbench-native-link" href="/odoo/action-fleet.fleet_vehicle_action" target="_blank" rel="noopener noreferrer">Revisar conductores en Odoo ↗</a>}</section>
        <section className="tracker-home-card"><span className="fleet-eyebrow">Herramientas de trabajo</span><h2>Continúa desde aquí</h2><div className="workbench-shortcuts">
          <button onClick={() => navigate('zones')}><TrackerIcon name="zones"/><span><strong>Zonas y actividad</strong><small>Entradas, salidas y permanencia</small></span><TrackerIcon name="arrow" size={17}/></button>
          <button onClick={() => navigate('protection')}><TrackerIcon name="protection"/><span><strong>Protección e incidentes</strong><small>Revisar alertas y seguimiento</small></span><TrackerIcon name="arrow" size={17}/></button>
          <button onClick={() => navigate('settings')}><TrackerIcon name="settings"/><span><strong>GPS y conectividad</strong><small>{pending ? `${pending} vehículos sin GPS asociado` : 'Equipos, SIM y ayuda'}</small></span><TrackerIcon name="arrow" size={17}/></button>
        </div></section>
      </aside>
    </div>
    {context.role === 'manager' && <section className="workbench-fleet-management"><div><h2>Organiza tu flota</h2><p>Incorpora vehículos o actualiza los que ya tienes en Odoo.</p></div><button onClick={onCreate}><TrackerIcon name="plus" size={17}/> Registrar vehículo</button><button disabled={demo || busy} onClick={onImport}>Sincronizar con Odoo</button></section>}
  </div>;
}

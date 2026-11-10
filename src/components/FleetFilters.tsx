import { emptyFilters, label, type FleetAsset, type FleetFilters as Filters } from '../services/fleetApi';
export default function FleetFilters({ assets, value, onChange }: { assets: FleetAsset[]; value: Filters; onChange: (v: Filters) => void }) {
  const unique = (values: (string | null | undefined)[]) => [...new Set(values.filter((v): v is string => !!v))].sort();
  const select = (key: keyof Filters, title: string, options: string[]) => <label>{title}<select value={value[key]} onChange={e => onChange({ ...value, [key]: e.target.value })}><option value="">Todos</option>{options.map(v => <option key={v} value={v}>{label(v)}</option>)}</select></label>;
  const active = Object.entries(value).filter(([,v])=>v);
  const titles:Record<string,string>={q:'Búsqueda',type:'Tipo',cost_center:'Centro',motion:'Movimiento',signal:'Señal',protection:'Protección',gps:'GPS'};
  return <section className="fleet-filter-workspace" aria-label="Búsqueda y filtros de flota"><div className="fleet-filters"><label className="fleet-search">Buscar equipo, patente o chofer<input type="search" value={value.q} onChange={e => onChange({ ...value, q: e.target.value })} placeholder="Nombre, patente o chofer"/></label><details><summary>Más filtros{active.length ? ` (${active.length})` : ''}</summary><div className="fleet-filter-options">{select('type', 'Tipo de activo', unique(assets.map(a => a.type)))}{select('cost_center', 'Centro de costo / fundo', unique(assets.map(a => a.cost_center)))}{select('motion', 'Movimiento', ['moving', 'stationary', 'unknown'])}{select('signal', 'Señal', ['received', 'stale', 'no_signal'])}{select('protection', 'Protección', ['armed', 'disarmed', 'incident_open'])}{select('gps', 'Modelo GPS', unique(assets.map(a => a.device?.model)))}</div></details><button disabled={!active.length} onClick={() => onChange(emptyFilters)}>Limpiar filtros</button></div>
    <div className="fleet-quick-filters" aria-label="Filtros rápidos"><span>Mostrar</span>{([
      ['moving','En movimiento',assets.filter(a=>a.motion_state==='moving').length],
      ['stationary','Detenidos',assets.filter(a=>a.motion_state==='stationary').length],
      ['stale','Ubicación antigua',assets.filter(a=>a.signal_state==='stale').length],
      ['no_signal','Sin señal',assets.filter(a=>a.signal_state==='no_signal').length],
    ] as const).map(([key,text,count])=>{const field=key==='moving'||key==='stationary'?'motion':'signal';return <button key={key} aria-pressed={value[field]===key} onClick={()=>onChange({...value,[field]:value[field]===key?'':key})}>{text}<b>{count}</b></button>;})}</div>
    {active.length>0&&<div className="fleet-active-filters" aria-label="Filtros aplicados">{active.map(([key,v])=><button key={key} aria-label={'Quitar filtro '+titles[key]} onClick={()=>onChange({...value,[key]:''})}>{titles[key]}: {label(v)} <span aria-hidden="true">×</span></button>)}</div>}
  </section>;
}

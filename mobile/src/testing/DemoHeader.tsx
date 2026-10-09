import { SCENARIOS } from './demo';

export default function DemoHeader({ title }: { title: string }) {
  return <aside style={{ background: '#7a1510', color: '#fff', padding: '8px 12px', fontSize: 12 }}>
    <strong>MODO DEMOSTRACIÓN · datos ficticios</strong>
    <label style={{ display: 'block', marginTop: 4 }}>Recorrido de prueba
      <select aria-label="Recorrido de prueba" value={new URLSearchParams(location.search).get('scenario') ?? 'conductor'} onChange={(e) => { const url = new URL(location.href); url.searchParams.set('scenario', e.target.value); location.assign(url.href); }}>
        {Object.entries(SCENARIOS).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
    </label><small>{title}. Cambiar de recorrido reinicia los datos ficticios. Tracker conserva su acceso propio.</small>
  </aside>;
}

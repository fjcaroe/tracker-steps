import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLon, Waypoint } from '../lib/nav';

export type MapMarker = LatLon & { label?: string; kind: 'machine' | 'incident' | 'sos' | 'stop' };
export type MapField = { name: string; polygon: LatLon[] };

type Props = {
  me?: LatLon | null;
  track?: LatLon[];
  route?: Waypoint[];
  reached?: number;
  draft?: Waypoint[];
  fields?: MapField[];
  markers?: MapMarker[];
  focus?: LatLon | null;
  height?: number;
  onTap?: (p: LatLon) => void;
};

const dot = (cls: string, text = '') => L.divIcon({ className: '', html: `<span class="mk ${cls}">${text}</span>`, iconSize: [26, 26], iconAnchor: [13, 13] });

/** Mapa real (OpenStreetMap) con la posición, la ruta recorrida, la ruta asignada, los campos y los vehículos. Sin señal el trazado se sigue dibujando sobre fondo liso. */
export default function LiveMap({ me, track = [], route = [], reached = 0, draft = [], fields = [], markers = [], focus, height = 300, onTap }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const fitted = useRef(false);
  const tap = useRef(onTap);
  tap.current = onTap;

  useEffect(() => {
    if (!host.current || map.current) return;
    const m = L.map(host.current, { zoomControl: true, attributionControl: true }).setView([-35.43, -71.65], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(m);
    m.on('click', (e: L.LeafletMouseEvent) => tap.current?.({ lat: e.latlng.lat, lon: e.latlng.lng }));
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => { m.remove(); map.current = null; fitted.current = false; };
  }, []);

  useEffect(() => {
    const m = map.current, g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const bounds: L.LatLngTuple[] = [];
    const ll = (p: LatLon): L.LatLngTuple => [p.lat, p.lon];
    for (const f of fields) if (f.polygon.length > 2) L.polygon(f.polygon.map(ll), { color: '#6f8f3a', weight: 1.5, fillOpacity: 0.12 }).bindTooltip(f.name).addTo(g);
    if (route.length > 1) {
      L.polyline(route.map(ll), { color: '#1d6bd8', weight: 5, opacity: 0.85, dashArray: '10 8' }).addTo(g);
      route.forEach((w, i) => L.marker(ll(w), { icon: dot(i < reached ? 'mk--done' : i === route.length - 1 ? 'mk--end' : 'mk--wp', String(i + 1)) }).bindTooltip(w.label || `Punto ${i + 1}`).addTo(g));
      route.forEach((w) => bounds.push(ll(w)));
    }
    if (draft.length) {
      if (draft.length > 1) L.polyline(draft.map(ll), { color: '#d98a00', weight: 5 }).addTo(g);
      draft.forEach((w, i) => L.marker(ll(w), { icon: dot('mk--draft', String(i + 1)) }).addTo(g));
    }
    if (track.length > 1) { L.polyline(track.map(ll), { color: '#d2402f', weight: 4 }).addTo(g); track.forEach((p) => bounds.push(ll(p))); }
    for (const k of markers) { L.marker(ll(k), { icon: dot(`mk--${k.kind}`, k.kind === 'sos' ? '!' : '') }).bindTooltip(k.label ?? '').addTo(g); bounds.push(ll(k)); }
    if (me) { L.circleMarker(ll(me), { radius: 9, color: '#fff', weight: 3, fillColor: '#2563eb', fillOpacity: 1 }).addTo(g); bounds.push(ll(me)); }
    if (!fitted.current && bounds.length) { m.fitBounds(L.latLngBounds(bounds), { padding: [28, 28], maxZoom: 17 }); fitted.current = true; }
    else if (me && !route.length && !markers.length) m.panTo(ll(me), { animate: true });
  }, [me, track, route, reached, draft, fields, markers]);

  useEffect(() => { if (focus && map.current) map.current.setView([focus.lat, focus.lon], Math.max(map.current.getZoom(), 16)); }, [focus]);
  useEffect(() => { const t = setTimeout(() => map.current?.invalidateSize(), 150); return () => clearTimeout(t); }, [height]);

  return <div ref={host} className="livemap" style={{ height }} role="application" aria-label="Mapa" />;
}

import type { FleetAsset } from './fleetApi';
import type { Vertex } from './fleetZones';
export type TrailPosition = NonNullable<FleetAsset['last_position']>;
// Current GPS assignment only; do not bridge missing, ambiguous or impossible fixes.
export function trailPaths(rows: TrailPosition[]): Vertex[][] {
  const sorted = [...rows].sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at));
  const points: TrailPosition[] = [];
  for (const p of sorted) {
    const last=points.at(-1);
    if (last && Date.parse(last.recorded_at)===Date.parse(p.recorded_at)) {
      if (last.lat!==p.lat || last.lon!==p.lon || last.quality!==p.quality || last.speed_kmh!==p.speed_kmh) points[points.length-1]={...p,quality:'ambiguous'};
    } else points.push(p);
  }
  const paths: Vertex[][] = []; let path: Vertex[]=[];
  for (let i=1;i<points.length;i++) {
    const a=points[i-1],b=points[i]; const seconds=(Date.parse(b.recorded_at)-Date.parse(a.recorded_at))/1000;
    const rad=Math.PI/180;
    const h=Math.sin((b.lat-a.lat)*rad/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin((b.lon-a.lon)*rad/2)**2;
    const meters=12742017.6*Math.asin(Math.min(1,Math.sqrt(h)));
    if (a.quality!=='gps' || b.quality!=='gps' || !Number.isFinite(seconds) || seconds<=0 || seconds>300 || !Number.isFinite(meters) || meters/seconds*3.6>200 || [a.speed_kmh,b.speed_kmh].some(s=>s!==null && (!Number.isFinite(s)||s<0||s>200))) {
      path=[]; continue;
    }
    if (!path.length) { path=[{lat:a.lat,lon:a.lon}]; paths.push(path); }
    path.push({lat:b.lat,lon:b.lon});
  }
  return paths;
}

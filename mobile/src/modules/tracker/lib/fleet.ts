/** Hardware fleet uses the current Odoo session, never the phone journey token. */
export type FleetAsset = {
 asset_id:string;name:string;plate:string|null;signal_state:string;motion_state:string;position_stale:boolean;
 device:{brand:string;model:string}|null;
 last_position:{id:string;recorded_at:string;received_at:string;lat:number;lon:number;speed_kmh:number|null;quality:string}|null;
};
export type HardwareFleet = {tenant:string;tenant_id:string;user_id:string;items:FleetAsset[];total:number;next_cursor:string|null;generated_at:string};
export class FleetAccessError extends Error {}
export async function loadHardwareFleet(signal?:AbortSignal):Promise<HardwareFleet> {
 const response=await fetch('/steps_tracker/api/fleet/snapshot?limit=500', {credentials:'same-origin',redirect:'manual',cache:'no-store',headers:{Accept:'application/json'},signal});
 if(response.type==='opaqueredirect'||response.status===0||[401,403,404].includes(response.status)||!response.headers.get('content-type')?.includes('application/json'))throw new FleetAccessError('Inicia sesión en Odoo con acceso a Tracker para consultar la flota de tu compañía.');
 if(!response.ok)throw new Error('No se pudo actualizar la flota GPS. Reintenta cuando tengas conexión.');
 return response.json() as Promise<HardwareFleet>;
}
export function recentPosition(asset:FleetAsset,at=Date.now()):boolean {
 const p=asset.last_position;
 return !!p && p.quality==='gps' && !asset.position_stale && asset.signal_state==='received' && at-Date.parse(p.recorded_at)<=300000 && at-Date.parse(p.received_at)<=300000;
}

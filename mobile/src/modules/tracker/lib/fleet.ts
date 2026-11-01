/** Hardware fleet uses the current Odoo session, never the phone journey token. */
export type FleetAsset = {
 asset_id:string;name:string;plate:string|null;signal_state:string;motion_state:string;position_stale:boolean;
 device:{brand:string;model:string}|null;
 last_position:{id:string;recorded_at:string;received_at:string;lat:number;lon:number;speed_kmh:number|null;quality:string}|null;
};
export type InstallationGps = {id:string;label:string;asset_id:string|null;asset_name:string|null;mode:'capture'|'disabled';last_seen_at:string|null;fix_at:string|null;fix_received_at:string|null;lat:number|null;lon:number|null};
export type HardwareFleet = {tenant:string;tenant_id:string;user_id:string;role?:string;items:FleetAsset[];total:number;next_cursor:string|null;generated_at:string;installations?:InstallationGps[];installation_error?:string};
export class FleetAccessError extends Error {}
async function read(path:string,signal?:AbortSignal):Promise<Response> {
 const response=await fetch('/steps_tracker/api/'+path, {credentials:'same-origin',redirect:'manual',cache:'no-store',headers:{Accept:'application/json'},signal});
 if(response.type==='opaqueredirect'||response.status===0||[401,403,404].includes(response.status)||!response.headers.get('content-type')?.includes('application/json'))throw new FleetAccessError('Inicia sesión en Odoo con acceso a Tracker para consultar la flota de tu compañía.');
 if(!response.ok)throw new Error('No se pudo actualizar la flota GPS. Reintenta cuando tengas conexión.');
 return response;
}
type Registration={id:string;imei:string;asset_id:string|null;asset_name:string|null;commissioning?:{mode:string;last_seen_at:string|null;fix_at:string|null;fix_received_at:string|null;lat:number|null;lon:number|null}};
export async function loadHardwareFleet(signal?:AbortSignal):Promise<HardwareFleet> {
 const fleet=await (await read('fleet/snapshot?limit=500',signal)).json() as HardwareFleet;
 if(fleet.role!=='manager')return {...fleet,installations:[]};
 let registrations:Registration[]=[];let warning='';
 try{registrations=((await (await read('configuration',signal)).json()) as {items:Registration[]}).items;}
 catch(e){if(e instanceof FleetAccessError||(e as Error).name==='AbortError')throw e;warning='No se pudo consultar la recepción de los GPS en prueba.';}
 // Cookie selection or permissions can change between the two reads. Never label
 // another company's private diagnostics with the earlier fleet's identity.
 const confirmed=await (await read('fleet/snapshot?limit=1',signal)).json() as HardwareFleet;
 if(confirmed.tenant_id!==fleet.tenant_id||confirmed.user_id!==fleet.user_id||confirmed.role!==fleet.role)return {...await (await read('fleet/snapshot?limit=500',signal)).json(),installations:[]} as HardwareFleet;
 const installations:InstallationGps[]=registrations.filter(r=>r.commissioning?.mode==='capture'||(!r.asset_id&&r.commissioning?.mode==='disabled')).map(r=>({id:r.id,label:'GPS · ••••'+r.imei.slice(-4),asset_id:r.asset_id,asset_name:r.asset_name,mode:r.commissioning!.mode as 'capture'|'disabled',last_seen_at:r.commissioning!.last_seen_at,fix_at:r.commissioning!.fix_at,fix_received_at:r.commissioning!.fix_received_at,lat:r.commissioning!.lat,lon:r.commissioning!.lon}));
 return {...fleet,installations,installation_error:warning};
}
export function recentPosition(asset:FleetAsset,at=Date.now()):boolean {
 const p=asset.last_position;
 return !!p && p.quality==='gps' && !asset.position_stale && asset.signal_state==='received' && at-Date.parse(p.recorded_at)<=300000 && at-Date.parse(p.received_at)<=300000;
}

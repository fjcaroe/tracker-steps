import { FleetApiError, portalRequest, type FleetContext } from './fleetApi';

export type OdooVehicle={id:number;name:string;license_plate:string|false;odometer:number;odometer_unit:'kilometers'|'miles';driver_id:[number,string]|false};
export type OdometerReading={id:number;date:string;value:number;unit:'kilometers'|'miles'};
export type AssetLink={id:number;asset_id:string;vehicle_id:[number,string]};
export type OdooMenu={id:number;name:string;xmlid?:string;action:string|false;children:number[]};

export async function odooCall<T>(context:FleetContext,model:string,method:string,args:unknown[]=[],kwargs:Record<string,unknown>={}):Promise<T>{
 const response=await fetch(`/web/dataset/call_kw/${model}/${method}`,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',method:'call',id:crypto.randomUUID(),params:{model,method,args,kwargs:{...kwargs,context:{allowed_company_ids:[context.company_id]}}}})});
 if(!response.ok)throw new FleetApiError('No fue posible consultar Odoo. Comprueba tu sesión y vuelve a intentar.',response.status);
 const data=await response.json();
 if(data.error){const name=String(data.error.data?.name||'');throw new FleetApiError(String(data.error.data?.message||'Odoo no pudo completar esta acción.').slice(0,600),name.includes('Access')?403:400);}
 return data.result as T;
}
async function verifyCurrentCompany(context:FleetContext){
 const current=await portalRequest<FleetContext>('/steps_tracker/context');
 if(current.tenant_key!==context.tenant_key||current.company_id!==context.company_id||current.role==='viewer')throw new Error('La compañía o los permisos cambiaron. Recarga Tracker antes de guardar.');
}
export async function readAssetLink(context:FleetContext,assetId:string){
 const rows=await odooCall<AssetLink[]>(context,'step.tracker.asset.link','search_read',[],{domain:[['company_id','=',context.company_id],['asset_id','=',assetId],['active','=',true]],fields:['id','asset_id','vehicle_id'],limit:2});
 if(rows.length>1)throw new Error('Hay más de un vínculo para este equipo. Revisa sus asociaciones en Odoo.');
 return rows[0]||null;
}
export async function readVehicle(context:FleetContext,id:number){
 const rows=await odooCall<OdooVehicle[]>(context,'fleet.vehicle','search_read',[],{domain:[['id','=',id],'|',['company_id','=',context.company_id],['company_id','=',false]],fields:['id','name','license_plate','odometer','odometer_unit','driver_id'],limit:1});
 if(!rows[0])throw new Error('El vehículo vinculado no está disponible en esta compañía con tu perfil.');return rows[0];
}
export async function readOdometers(context:FleetContext,id:number){
 await readVehicle(context,id);
 return odooCall<OdometerReading[]>(context,'fleet.vehicle.odometer','search_read',[],{domain:[['vehicle_id','=',id]],fields:['id','date','value','unit'],order:'date desc,id desc',limit:51});
}
export async function recordOdometer(context:FleetContext,assetId:string,vehicleId:number,date:string,value:number){
 if(context.role==='viewer')throw new Error('Tu perfil de Tracker es de consulta.');
 await verifyCurrentCompany(context);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date))throw new Error('Selecciona una fecha válida.');
 if(!Number.isFinite(value)||value<0)throw new Error('Ingresa una lectura de odómetro válida, igual o mayor que cero.');
 const link=await readAssetLink(context,assetId);
 if(!link||link.vehicle_id[0]!==vehicleId)throw new Error('El vínculo cambió. Actualiza el vehículo antes de guardar.');
 await readVehicle(context,vehicleId);
 const readings=await odooCall<OdometerReading[]>(context,'fleet.vehicle.odometer','search_read',[],{domain:[['vehicle_id','=',vehicleId]],fields:['id','date','value','unit'],order:'date desc,id desc',limit:5000});
 if(readings.length===5000)throw new Error('Este historial requiere revisión desde Flota de Odoo antes de ingresar una lectura.');
 const duplicate=readings.find(r=>r.date===date&&r.value===value);if(duplicate)return {id:duplicate.id,existing:true};
 if(readings.some(r=>(r.date<=date&&r.value>value)||(r.date>=date&&r.value<value)))throw new Error('La lectura no es coherente con las lecturas anteriores o posteriores. Revisa la fecha y el valor; si hubo un cambio de tablero, regístralo desde Flota de Odoo.');
 const created=await odooCall<number|number[]>(context,'fleet.vehicle.odometer','create',[[{vehicle_id:vehicleId,date,value}]]);
 const id=Array.isArray(created)?created[0]:created;
 const saved=await odooCall<OdometerReading[]>(context,'fleet.vehicle.odometer','read',[[id]],{fields:['id','date','value','unit']});
 if(saved[0]?.value!==value||saved[0]?.date!==date)throw new Error('La lectura requiere revisión en Odoo. Actualiza el historial antes de volver a guardarla.');
 return {id,existing:false};
}
export async function linkVehicle(context:FleetContext,assetId:string,vehicleId:number){
 if(context.role!=='manager')throw new Error('Solo un administrador de Tracker puede vincular vehículos.');
 await verifyCurrentCompany(context);
 await readVehicle(context,vehicleId);
 if(await readAssetLink(context,assetId))throw new Error('Este equipo ya está vinculado. Actualiza el estado antes de continuar.');
 return odooCall<number|number[]>(context,'step.tracker.asset.link','create',[[{company_id:context.company_id,asset_id:assetId,vehicle_id:vehicleId,note:'Vínculo explícito confirmado desde Operaciones de Tracker.'}]]);
}
export function applicationLinks(menus:Record<string,OdooMenu>){
 const categories=[['fleet.','Flota'],['hr_expense.','Gastos'],['step_cosecha.','Cosecha'],['step_management_costs.','Gestión y Costos'],['step_freight.','Fletes'],['step_movi.','Movilización']];
 const rootIds=new Set(menus.root?.children||[]),result:{label:string;href:string;id:number}[]=[];
 function action(menu:OdooMenu):{id:number;action:string}|null{
  const pending=[menu],seen=new Set<number>();
  while(pending.length){const current=pending.shift()!;if(seen.has(current.id))continue;seen.add(current.id);if(typeof current.action==='string'&&/^ir\.actions\.(?:act_window|client|server),\d+$/.test(current.action))return {id:current.id,action:current.action};for(const id of current.children||[])if(menus[String(id)])pending.push(menus[String(id)]);}
  return null;
 }
 for(const [prefix,label] of categories){const candidates=Object.values(menus).filter(m=>m.id&&m.xmlid?.startsWith(prefix));const menu=candidates.find(m=>rootIds.has(m.id))||candidates[0];if(!menu)continue;const target=action(menu);if(target)result.push({label,id:target.id,href:'/odoo/action-'+target.action.split(',')[1]});}
 return result;
}

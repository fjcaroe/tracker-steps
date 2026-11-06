import {useEffect,useRef,useState} from 'react';
import {fleetRequest,type FleetContext} from './fleetApi';
export type GpsMetric={point_count:number;distance_m:number;moving_seconds:number;stop_count:number;gap_count:number;max_speed:number|null;first_at:string|null;last_at:string|null};
export type GpsSummary={asset_id:string;metrics:GpsMetric;complete:boolean;pending_hours:number;daily:(GpsMetric&{day:string})[]};
export const emptyGpsMetric:GpsMetric={point_count:0,distance_m:0,moving_seconds:0,stop_count:0,gap_count:0,max_speed:null,first_at:null,last_at:null};
export function useGpsAnalytics(context:FleetContext,ids:string[],period:{from:number;to:number},enabled=true){
 const key=[context.tenant_key,context.company_id,context.user_id,period.from,period.to].join(':'),selection=JSON.stringify([...ids].sort());
 const cache=useRef<{key:string;items:Record<string,GpsSummary>}>({key,items:{}});
 const [state,setState]=useState<{key:string;items:Record<string,GpsSummary>;loading:boolean;error:string}>({key,items:{},loading:false,error:''});
 const [round,setRound]=useState(0);
 useEffect(()=>{
  if(!enabled)return;
  const controller=new AbortController();let timer:ReturnType<typeof setTimeout>|undefined,attempt=0;
  if(cache.current.key!==key)cache.current={key,items:{}};
  const selected=JSON.parse(selection) as string[];
  const publish=(loading:boolean,error='')=>{if(!controller.signal.aborted)setState({key,items:{...cache.current.items},loading,error});};
  async function load(){
   const pending=selected.filter(id=>!cache.current.items[id]?.complete||round>0);
   publish(!!pending.length);
   try{
    // Bounded batches: fifty vehicles share one request, never pages of raw fixes.
    for(let offset=0;offset<pending.length;offset+=50){
     const result=await fleetRequest<{items:GpsSummary[]}>(`assets/analytics?asset_ids=${encodeURIComponent(pending.slice(offset,offset+50).join(','))}&since=${encodeURIComponent(new Date(period.from).toISOString())}&until=${encodeURIComponent(new Date(period.to).toISOString())}`,context,'GET',undefined,controller.signal);
     if(controller.signal.aborted)return;
     for(const item of result.items)cache.current.items[item.asset_id]=item;
    }
    publish(false);
    if(selected.some(id=>!cache.current.items[id]?.complete)&&++attempt<12)timer=setTimeout(()=>void load(),5000);
   }catch(error){if(!controller.signal.aborted)publish(false,(error as Error).message);}
  }
  void load();return()=>{controller.abort();clearTimeout(timer);};
 },[key,selection,round,enabled,context,period.from,period.to]);
 return {...(state.key===key?state:{key,items:{},loading:enabled,error:''}),retry:()=>setRound(n=>n+1)};
}

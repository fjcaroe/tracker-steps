import { useEffect, useState } from 'react';
import { fleetRequest, type FleetContext } from '../services/fleetApi';
import { trailPaths, type TrailPosition } from '../services/vehicleTrail';
import type { Vertex } from '../services/fleetZones';
import { demoZoneReport } from './useFleetZones';
export function useVehicleTrail(context: FleetContext, assetId: string | undefined, demo: boolean) {
  const [state,setState]=useState<{paths:Vertex[][];error:string;busy:boolean;truncated:boolean;updated:string|null;count:number}>({paths:[],error:'',busy:false,truncated:false,updated:null,count:0});
  const [tick,setTick]=useState(0);
  useEffect(()=>{
    let active=true; let pending=false;
    setState({paths:[],error:'',busy:!!assetId,truncated:false,updated:null,count:0});
    if (demo) {setState({paths:demoZoneReport.segments.map(s=>s.path),error:'',busy:false,truncated:false,updated:demoZoneReport.end,count:demoZoneReport.point_count});return;}
    if (!assetId) return;
    const load=async()=>{
      if(pending)return;pending=true;
      try {
        const since=new Date(Date.now()-24*3600000).toISOString();
        const result=await fleetRequest<{items:TrailPosition[];next_cursor:string|null}>(`assets/${assetId}/positions?${new URLSearchParams({limit:'500',current_assignment:'true',since})}`,context);
        if(active)setState({paths:trailPaths(result.items),error:'',busy:false,truncated:!!result.next_cursor,updated:new Date().toISOString(),count:result.items.length});
      }catch(e){if(active)setState({paths:[],error:(e as Error).message,busy:false,truncated:false,updated:null,count:0});}
      finally{pending=false;}
    };
    void load();const timer=setInterval(()=>void load(),60000);
    return()=>{active=false;clearInterval(timer);};
  },[context,assetId,demo,tick]);
  return {...state,refresh:()=>setTick(n=>n+1)};
}

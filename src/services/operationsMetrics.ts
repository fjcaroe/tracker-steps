import {buildTrail,meters,type TrailPoint} from './fleetTrail.ts';
export function operationsMetrics(input:TrailPoint[],from:number,to:number){
 const trail=buildTrail(input,from,to),daily=new Map<string,{day:string;km:number;movingMinutes:number}>();
 let movingSeconds=0;
 const calendar=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Santiago',year:'numeric',month:'2-digit',day:'2-digit'});
 const dayOf=(time:string)=>calendar.format(new Date(time));
 for(const point of trail.points){const day=dayOf(point.recorded_at);if(!daily.has(day))daily.set(day,{day,km:0,movingMinutes:0});}
 for(const segment of trail.segments){
  for(let i=1;i<segment.length;i++){
   const a=segment[i-1],b=segment[i],seconds=(Date.parse(b.recorded_at)-Date.parse(a.recorded_at))/1000;
   if(seconds<=0||seconds>600)continue;
   const distance=meters(a,b),day=dayOf(b.recorded_at),row=daily.get(day)!;
   movingSeconds+=seconds;row.km+=distance/1000;row.movingMinutes+=seconds/60;
  }
 }
 const speeds=trail.points.map(p=>p.speed_kmh).filter((v):v is number=>v!=null&&Number.isFinite(v)&&v>=0&&v<=300);
 return {...trail,movingSeconds,maxReportedSpeed:speeds.length?Math.max(...speeds):null,daily:[...daily.values()].sort((a,b)=>a.day.localeCompare(b.day)),spanSeconds:trail.points.length>1?(Date.parse(trail.points.at(-1)!.recorded_at)-Date.parse(trail.points[0].recorded_at))/1000:0};
}
export function operationsCsv(rows:unknown[][]){
 const safe=(value:unknown)=>{const raw=String(value??'');return '"'+(/^[=+\-@\t\r]/.test(raw)?"'"+raw:raw).replaceAll('"','""')+'"';};
 return '\uFEFF'+rows.map(row=>row.map(safe).join(';')).join('\r\n');
}

import type {FleetAsset} from './fleetApi';
export type TrailPoint=NonNullable<FleetAsset['last_position']>;
export type Stop={point:TrailPoint;start:string;end:string;minutes:number};
export function meters(a:{lat:number;lon:number},b:{lat:number;lon:number}){
 const rad=Math.PI/180,dlat=(b.lat-a.lat)*rad,dlon=(b.lon-a.lon)*rad;
 const h=Math.sin(dlat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dlon/2)**2;
 return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));
}
export function buildTrail(input:TrailPoint[],from:number,to:number){
 const points=[...new Map(input.filter(p=>Number.isFinite(p.lat)&&Math.abs(p.lat)<=90&&Number.isFinite(p.lon)&&Math.abs(p.lon)<=180&&Date.parse(p.recorded_at)>=from&&Date.parse(p.recorded_at)<=to).map(p=>[p.id,p])).values()].sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at)||a.id.localeCompare(b.id));
 const segments:TrailPoint[][]=[];const stops:Stop[]=[];let gapCount=0,distanceM=0;
 let run:TrailPoint[]=[];
 const saveStop=()=>{if(run.length<2)return;const start=run[0],end=run[run.length-1],minutes=(Date.parse(end.recorded_at)-Date.parse(start.recorded_at))/60000;if(minutes>=3)stops.push({point:start,start:start.recorded_at,end:end.recorded_at,minutes});};
 for(const p of points){
  const previous=run[run.length-1];
  if(run.length&&((p.speed_kmh??0)>5||meters(run[0],p)>50||Date.parse(p.recorded_at)-Date.parse(previous.recorded_at)>600000)){saveStop();run=[];}
  if((p.speed_kmh??0)<=5)run.push(p);
 }
 saveStop();
 let previousRaw:TrailPoint|undefined;
 for(const p of points){
  const rawBefore=previousRaw;previousRaw=p;
  const segment=segments[segments.length-1],previous=segment?.[segment.length-1];
  if(!previous){segments.push([p]);continue;}
  const seconds=(Date.parse(p.recorded_at)-Date.parse(rawBefore!.recorded_at))/1000,d=meters(previous,p),rawDistance=meters(rawBefore!,p);
  if(seconds>600||rawDistance>5000||seconds<=0||(rawDistance/seconds)*3.6>220){gapCount++;segments.push([p]);continue;}
  // Keep raw readings intact; suppress short low-speed wander in the displayed path.
  if(d<25&&(p.speed_kmh??0)<5&&(previous.speed_kmh??0)<5)continue;
  segment.push(p);distanceM+=d;
 }
 const stationary=points.length>1&&gapCount===0&&points.every(p=>(p.speed_kmh??0)<5&&meters(points[0],p)<120);
 return {points,segments:stationary?[[points[0]]]:segments,stops,distanceM:stationary?0:distanceM,gapCount,stationary,maxSpeed:Math.max(0,...points.map(p=>p.speed_kmh??0))};
}
export function routeAnchors(points:TrailPoint[]){
 if(points.length<2)return [];
 const result:TrailPoint[]=[];const count=Math.min(8,points.length);
 for(let i=0;i<count;i++){const p=points[Math.round(i*(points.length-1)/(count-1))];if(!result.length||meters(result[result.length-1],p)>15)result.push(p);}
 return result;
}

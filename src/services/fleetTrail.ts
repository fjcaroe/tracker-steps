import type {FleetAsset} from './fleetApi';
export type TrailPoint=NonNullable<FleetAsset['last_position']>;
export type Stop={point:TrailPoint;start:string;end:string;minutes:number;sparse:boolean};
export type TrailGap={before:TrailPoint;after:TrailPoint;seconds:number;reason:'time_gap'|'position_jump'|'timestamp_conflict'|'implausible_speed'};
export function nextTrailStep(points:TrailPoint[],gaps:TrailGap[],index:number){
 if(index>=points.length-1)return {index,gap:null,ended:true};
 const gap=gaps.find(g=>g.after.id===points[index+1].id)||null;
 return {index:gap?index:index+1,gap,ended:false};
}
export function meters(a:{lat:number;lon:number},b:{lat:number;lon:number}){
 const rad=Math.PI/180,dlat=(b.lat-a.lat)*rad,dlon=(b.lon-a.lon)*rad;
 const h=Math.sin(dlat/2)**2+Math.cos(a.lat*rad)*Math.cos(b.lat*rad)*Math.sin(dlon/2)**2;
 return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));
}
export function buildTrail(input:TrailPoint[],from:number,to:number){
 const points=[...new Map(input.filter(p=>Number.isFinite(p.lat)&&Math.abs(p.lat)<=90&&Number.isFinite(p.lon)&&Math.abs(p.lon)<=180&&Date.parse(p.recorded_at)>=from&&Date.parse(p.recorded_at)<=to).map(p=>[p.id,p])).values()].sort((a,b)=>Date.parse(a.recorded_at)-Date.parse(b.recorded_at)||a.id.localeCompare(b.id));
 const segments:TrailPoint[][]=[];const stops:Stop[]=[];const gaps:TrailGap[]=[];
 const parked=new Map<string,TrailPoint>();
 const omitted=new Set<string>();
 let run:TrailPoint[]=[];
 let sparse=false;
 const saveStop=()=>{
  if(run.length<2||(sparse&&run.length<3))return;
  const start=run[0],end=run[run.length-1];
  const minutes=(Date.parse(end.recorded_at)-Date.parse(start.recorded_at))/60000;
  if(minutes<3)return;
  stops.push({point:start,start:start.recorded_at,end:end.recorded_at,minutes,sparse});
  run.forEach((point,i)=>{
   parked.set(point.id,start);
   if(i>0&&i<run.length-1)omitted.add(point.id);
  });
 };
 for(const p of points){
  const previous=run[run.length-1];
  const slow=p.speed_kmh!=null&&p.speed_kmh>=0&&p.speed_kmh<=2;
  const seconds=previous?(Date.parse(p.recorded_at)-Date.parse(previous.recorded_at))/1000:0;
  // Some units send a parked fix only once per hour. Bound the cluster to
  // its first sample so accumulated drift cannot turn into a trip.
  if(previous&&(!slow||meters(run[0],p)>35||seconds<=0||seconds>4500)){
   saveStop();run=[];sparse=false;
  }
  if(slow){
   if(run.length&&seconds>600)sparse=true;
   run.push(p);
  }
 }
 saveStop();
 let previousRaw:TrailPoint|undefined;
 for(const p of points){
  const rawBefore=previousRaw;previousRaw=p;
  const segment=segments[segments.length-1],previous=segment?.[segment.length-1];
  if(!previous){segments.push([p]);continue;}
  if(parked.has(p.id)&&parked.get(p.id)===parked.get(rawBefore!.id))continue;
  const seconds=(Date.parse(p.recorded_at)-Date.parse(rawBefore!.recorded_at))/1000,d=meters(previous,p),rawDistance=meters(rawBefore!,p);
  if(seconds>600||rawDistance>5000||seconds<=0||(rawDistance/seconds)*3.6>220){gaps.push({before:rawBefore!,after:p,seconds,reason:seconds>600?'time_gap':seconds<=0?'timestamp_conflict':rawDistance>5000?'position_jump':'implausible_speed'});segments.push([p]);continue;}
  // Keep raw readings intact; suppress short low-speed wander in the displayed path.
  if(d<25&&(p.speed_kmh??0)<5&&(previous.speed_kmh??0)<5)continue;
  segment.push(p);
 }
 let confirmedMovement=false;const movingIds=new Set<string>();
 for(let i=1;i<points.length;i++){
  const a=points[i-1],b=points[i],dt=(Date.parse(b.recorded_at)-Date.parse(a.recorded_at))/1000,d=meters(a,b);
  if((a.speed_kmh??0)>=8&&(b.speed_kmh??0)>=8&&dt>0&&dt<=600&&d>=25&&d/dt*3.6<=220){confirmedMovement=true;movingIds.add(a.id);movingIds.add(b.id);}
 }
 for(let i=2;i<points.length;i++){
  const a=points[i-2],b=points[i-1],c=points[i],dt=(Date.parse(c.recorded_at)-Date.parse(a.recorded_at))/1000;
  const ab=meters(a,b),bc=meters(b,c),net=meters(a,c);
  const fast=[a,b,c].filter(p=>(p.speed_kmh??0)>=8).length>=2;
  const inferred=[a,b,c].every(p=>p.speed_kmh==null)&&dt>0&&net/dt*3.6>=8;
  if(dt>0&&dt<=1200&&ab<5000&&bc<5000&&net>=60&&net/Math.max(1,ab+bc)>.65&&(fast||inferred)){confirmedMovement=true;movingIds.add(a.id);movingIds.add(b.id);movingIds.add(c.id);}
 }
 const stationary=points.length>1&&!confirmedMovement;
 const display:TrailPoint[][]=[];
 for(const segment of segments){
  let motion:TrailPoint[]=[];
  for(const p of segment){if(movingIds.has(p.id))motion.push(p);else{if(motion.length)display.push(motion);motion=[];display.push([p]);}}
  if(motion.length)display.push(motion);
 }
 const distanceM=display.reduce((sum,s)=>sum+s.slice(1).reduce((d,p,i)=>d+meters(s[i],p),0),0);
 const playback=points.filter(p=>!omitted.has(p.id)).map(p=>{
  const stop=parked.get(p.id);
  return stop&&stop!==p?{...p,lat:stop.lat,lon:stop.lon}:p;
 });
 const onlyParking=stops.length===1&&parked.size===points.length;
 return {points,playback,onlyParking,segments:stationary?[[points[0]]]:display,stops,gaps,distanceM:stationary?0:distanceM,gapCount:gaps.length,stationary,maxSpeed:Math.max(0,...playback.map(p=>p.speed_kmh??0))};
}
export function routeAnchors(points:TrailPoint[]){
 if(points.length<2)return [];
 const result:TrailPoint[]=[];const count=Math.min(8,points.length);
 for(let i=0;i<count;i++){const p=points[Math.round(i*(points.length-1)/(count-1))];if(!result.length||meters(result[result.length-1],p)>15)result.push(p);}
 return result;
}

import test from 'node:test';
import assert from 'node:assert/strict';
import {buildTrail,routeAnchors,nextTrailStep,shortContinuity} from '../../../src/services/fleetTrail.ts';
const start=Date.parse('2026-01-01T00:00:00Z');
const point=(i,lat=-33-i*.001,speed=30)=>({id:String(i),recorded_at:new Date(start+i*60000).toISOString(),received_at:new Date(start+i*60000).toISOString(),lat,lon:-70,speed_kmh:speed,quality:'gps',acc:null,external_power:null});
test('sorts, deduplicates and filters invalid/out-of-period samples',()=>{
 const r=buildTrail([point(2),point(1),point(1),point(3,200),point(-1)],start,start+180000);
 assert.deepEqual(r.points.map(p=>p.id),['1','2']);assert.ok(r.distanceM>100);
});
test('stationary drift never becomes a trip, even after a long parking interval',()=>{
 const r=buildTrail(Array.from({length:90},(_,i)=>point(i,-33+(i%3)*.00001,1)),start,start+90*60000);
 assert.equal(r.distanceM,0);assert.equal(r.gapCount,0);assert.equal(r.stationary,true);assert.equal(r.stops.length,1);
});
test('hourly parked readings produce one probable stop and retain raw samples',()=>{
 const rows=Array.from({length:9},(_,i)=>point(i*60,-33+(i%3)*.00004,0));
 const r=buildTrail(rows,start,start+9*3600000);
 assert.equal(r.onlyParking,true);
 assert.deepEqual(r.points,rows);
 assert.equal(r.stops.length,1);
 assert.equal(r.stops[0].minutes,480);
 assert.equal(r.stops[0].sparse,true);
 assert.equal(r.distanceM,0);
 assert.equal(r.gaps.length,0);
 assert.equal(r.playback.length,2);
 assert.equal(r.playback[0].lat,r.playback[1].lat);
});
test('a long unobserved interval stays visible even at the same parking location',()=>{
 const rows=[0,60,120,300,360,420].map(i=>point(i,-33,0));
 const r=buildTrail(rows,start,start+8*3600000);
 assert.equal(r.onlyParking,false);
 assert.equal(r.stops.length,2);
 assert.equal(r.gaps.length,1);
 assert.equal(nextTrailStep(r.playback,r.gaps,1).gap,r.gaps[0]);
});
test('does not bridge a communication gap or invent a road distance',()=>{
 const r=buildTrail([point(0),point(1),point(30,-33.04)],start,start+3600000);
 assert.equal(r.gapCount,1);assert.equal(r.segments.length,2);assert.ok(r.distanceM<200);assert.equal(r.stops.length,0);
});
test('separates implausible jumps and simultaneous positions',()=>{
 const r=buildTrail([point(0),{...point(1,-34),recorded_at:point(0).recorded_at}],start,start+60000);
 assert.equal(r.gapCount,1);assert.equal(r.distanceM,0);
});
test('routing anchors preserve chronological order and bound provider cost',()=>{
 const rows=Array.from({length:120},(_,i)=>point(i));const anchors=routeAnchors(rows);
 assert.equal(anchors.length,8);assert.equal(anchors[0].id,'0');assert.equal(anchors.at(-1).id,'119');assert.equal(routeAnchors([point(0)]).length,0);
});
test('empty and one-point periods remain usable',()=>{
 assert.equal(buildTrail([],start,start+1).distanceM,0);
 const r=buildTrail([point(0)],start,start+1);assert.equal(r.segments.length,1);assert.equal(r.distanceM,0);
});

test('one speed spike amid low-speed bench wander does not establish a vehicle trip',()=>{
 const rows=Array.from({length:30},(_,i)=>({...point(i,-33+(i%4)*.0007,i===10?19:2),lon:-70+(i%3)*.0004}));
 const r=buildTrail(rows,start,start+1800000);assert.equal(r.stationary,true);assert.equal(r.distanceM,0);
});

test('parking wander is excluded even when followed by a real drive',()=>{
 const parked=Array.from({length:12},(_,i)=>point(i,-33+(i%4)*.0002,1));
 const driving=[point(12,-33,30),point(13,-33.001,30),point(14,-33.002,30)];
 const r=buildTrail([...parked,...driving],start,start+3600000);
 assert.equal(r.stationary,false);assert.ok(r.distanceM>200&&r.distanceM<230);
});
test('two consistent moving readings can establish a short low-speed trip',()=>{
 const r=buildTrail([point(0,-33,10),point(1,-33.0003,10)],start,start+60000);
 assert.equal(r.stationary,false);assert.ok(r.distanceM>30&&r.distanceM<40);
});

test('playback stops before a long gap and preserves its exact bounding observations',()=>{
 const rows=[point(0),point(1),point(151),point(152)];
 const r=buildTrail(rows,start,start+180*60000);
 assert.equal(r.gaps.length,1);assert.equal(r.gaps[0].seconds,9000);assert.equal(r.gaps[0].reason,'time_gap');
 assert.equal(r.gaps[0].before.id,'1');assert.equal(r.gaps[0].after.id,'151');
 assert.equal(nextTrailStep(r.points,r.gaps,0).index,1);
 const paused=nextTrailStep(r.points,r.gaps,1);assert.equal(paused.index,1);assert.equal(paused.gap,r.gaps[0]);assert.equal(paused.ended,false);
 assert.equal(nextTrailStep(r.points,r.gaps,2).index,3);assert.equal(nextTrailStep(r.points,r.gaps,3).ended,true);
 assert.ok(r.distanceM<250);assert.equal(r.points.length,4);
});

test('backfilled real observations remove a time gap without interpolation',()=>{
 const partial=buildTrail([point(0),point(1),point(31)],start,start+40*60000);assert.equal(partial.gaps.length,1);
 const complete=buildTrail(Array.from({length:32},(_,i)=>point(i)),start,start+40*60000);
 assert.equal(complete.gaps.length,0);assert.equal(nextTrailStep(complete.points,complete.gaps,1).index,2);
});

test('brief plausible missing fixes are visual estimates, not disconnection or invented GPS',()=>{
 const times=[0,10,20,80,90,100];
 const values=times.map((seconds,i)=>({...point(i,-33-seconds*.0001,40),recorded_at:new Date(start+seconds*1000).toISOString(),assignment_id:'one'}));
 const trail=buildTrail(values,start,start+200000),links=shortContinuity(trail.segments);
 assert.equal(trail.gapCount,0);assert.equal(links.length,1);assert.equal(links[0].seconds,60);
 assert.equal(trail.points.length,values.length);
 const swapped=values.map((p,i)=>({...p,assignment_id:i>=3?'two':'one'}));
 const other=buildTrail(swapped,start,start+200000);
 assert.ok(other.gaps.some(g=>g.reason==='device_changed'));assert.equal(shortContinuity(other.segments).length,0);
});

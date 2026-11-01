import test from 'node:test';
import assert from 'node:assert/strict';
import {buildTrail,routeAnchors} from '../../../src/services/fleetTrail.ts';
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

import test from 'node:test';
import assert from 'node:assert/strict';
import {gapEvidence} from '../../../src/services/receiverHistory.ts';
const gap={before:{recorded_at:'2026-01-01T12:00:00Z',assignment_id:'one'},after:{recorded_at:'2026-01-01T12:15:00Z'}};
const event={contact_at:'2026-01-01T12:03:00Z',assignment_id:'one',state:'no_gps'};
test('only actual contact inside the same assignment proves no fix',()=>{
 assert.match(gapEvidence(gap,[event]),/falta de posición GPS válida/);
 for(const changed of [{state:'no_contact'},{assignment_id:'other'},{contact_at:'2026-01-01T11:59:00Z'}])assert.match(gapEvidence(gap,[{...event,...changed}]),/sin comprobar/);
 assert.match(gapEvidence(gap,[{...event,state:'contact_without_fix'}]),/Hubo comunicación/);
 assert.match(gapEvidence({...gap,after:{...gap.after,recovered:true}},[]),/llegó con atraso/);
});

import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Exercise the actual patch methods, with the Odoo services isolated from the DOM.
class ProducerDashboard { setup() {} }
class AgroComparison {
    async load() {
        if (this.fail) {
            this.state.error = 'offline'; this.state.data = null; return;
        }
        this.state.error = '';
        this.state.data = { companies: [{ id: 1 }, { id: 2 }],
            selected_company_ids: this.state.filters.company_ids || [1, 2] };
    }
}
function patch(target, extension) {
    const previous = Object.create(Object.getPrototypeOf(target), Object.getOwnPropertyDescriptors(target));
    Object.setPrototypeOf(extension, previous);
    Object.defineProperties(target, Object.getOwnPropertyDescriptors(extension));
}
const source = fs.readFileSync(new URL('../../step_producer_holding/static/src/holding.js', import.meta.url), 'utf8');
vm.runInNewContext(source.replace(/^import .+;$/gm, ''), { patch, ProducerDashboard, AgroComparison, useBus() {} });
const events = [];
const comparison = new AgroComparison();
Object.assign(comparison, { props: { kind: 'producers' }, state: { filters: {}, data: null, error: '' },
    env: { bus: { trigger: (name, ids) => events.push([name, Array.from(ids)]) } } });
await comparison.load();
assert.deepEqual(events.at(-1)[1], [1, 2]);
await comparison.changeHoldingCompany(1, { target: { checked: false } });
assert.deepEqual(events.at(-1)[1], [2]);
const lastSelection = { target: { checked: false } };
await comparison.changeHoldingCompany(2, lastSelection);
assert.equal(lastSelection.target.checked, true);
assert.deepEqual(events.at(-1)[1], [2]);
await comparison.selectAllHolding();
assert.deepEqual(events.at(-1)[1], [1, 2]);
comparison.fail = true;
await comparison.changeHoldingCompany(2, { target: { checked: false } });
assert.equal(comparison.state.error, 'offline');
assert.deepEqual(events.at(-1)[1], [1, 2]);
comparison.fail = false;
await comparison.load(); // Retrying must synchronize the cards with the new selection.
assert.deepEqual(events.at(-1)[1], [1]);

const dashboard = new ProducerDashboard();
const pending = [];
dashboard.state = {};
dashboard.orm = { call: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) };
const earlier = dashboard.loadCounts([1]);
const latest = dashboard.loadCounts([2]);
pending[1].resolve({ estimates: 20 }); await latest;
pending[0].resolve({ estimates: 10 }); await earlier;
assert.equal(dashboard.state.counts.estimates, 20);
const failed = dashboard.loadCounts([2]);
pending[2].reject(new Error('offline')); await failed;
assert.equal(dashboard.state.loading, false);
assert.ok(dashboard.state.holdingError);
console.log('PRODUCER_HOLDING_UI_OK scope, last selection, retry, race, error');

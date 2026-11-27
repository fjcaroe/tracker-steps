/* Exercise the actual 0.0.12 client against a certified writable copy only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { randomUUID } = require('node:crypto');
const { chromium } = require('playwright');

(async () => {
    const [origin, policyFile, output] = process.argv.slice(2);
    assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
    const policy = JSON.parse(fs.readFileSync(policyFile, 'utf8'));
    assert.equal(policy.copy_sync_allowed, true);
    assert.equal(policy.read_only, false);
    assert.equal(policy.sync_origin, origin);
    assert.match(policy.database, /^MANAGEMENT_QA_(DEVELOPMENT|CERRO|QA-CERRO)_t244245_[a-f0-9]{8}$/);
    assert.equal(policy.harvest_web.version, '0.0.12');
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
    try {
        const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'es-CL' });
        const page = await context.newPage();
        page.setDefaultTimeout(60000);
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(origin + '/cosecha/', { waitUntil: 'domcontentloaded' });
        await page.getByText(/· Harvest 0\.0\.12$/).waitFor();
        const data = await context.request.get(origin + '/api/harvest/bootstrap').then(r => r.json());
        assert.equal(data.user.id, policy.user_id);
        assert.equal(data.company.id, policy.company_id);
        const workers = new Set(data.workers.map(row => row.id));
        const crew = data.crews.find(row => row.worker_ids?.length && row.worker_ids.every(id => workers.has(id))
            && (row.type === 'propio' || row.contractor));
        assert.ok(crew);
        const worker = crew.worker_ids[0];
        const center = data.cost_centers.find(row => data.farms.some(farm => farm.id === row.farm_id)
            && data.varieties.some(variety => variety.id === row.variety_id));
        assert.ok(center);
        const location = data.operation_locations.find(row => row.farm_id === center.farm_id);
        const id = 'QA-T244245-BROWSER-' + randomUUID();
        const nav = page.getByRole('navigation', { name: 'Navegación móvil' });
        await page.getByTitle('Configuración', { exact: true }).click();
        await page.locator('.setting').filter({ hasText: 'Folio de tarja' }).getByRole('button', { name: 'Sin tarja', exact: true }).click();
        await page.locator('.setting').filter({ hasText: 'Pesaje de cosecha' }).getByRole('button', { name: 'Manual', exact: true }).click();
        await nav.getByRole('button', { name: 'OT', exact: true }).click();
        await page.getByRole('button', { name: 'Nueva OT', exact: true }).click();
        const form = page.getByRole('dialog', { name: 'Nueva orden de trabajo' });
        await form.locator('[name=id]').fill(id);
        await form.locator('[name=crew]').selectOption(String(crew.id));
        await form.locator('[name=farm]').selectOption(String(center.farm_id));
        if (location) await form.locator('[name=operationLocation]').selectOption(String(location.id));
        await form.locator('[name=passNumber]').fill('2');
        await form.locator('[name=harvestType]').selectOption('industrial');
        await form.locator('[name=variety]').selectOption(String(center.variety_id));
        await form.locator('[name=costCenter]').selectOption(String(center.id));
        await form.getByRole('button', { name: 'Crear jornada local', exact: true }).click();
        await nav.getByRole('button', { name: /^Registrar(?:\s|$)/ }).click();
        await page.locator('form.capture-card select').selectOption(String(worker));
        await page.getByLabel('Hilera', { exact: true }).fill('QA-T244245');
        await page.locator('.quantity-row input[type=number]').fill('9.27');
        await page.getByRole('button', { name: 'Guardar entrega', exact: true }).click();
        await nav.getByRole('button', { name: 'OT', exact: true }).click();
        const card = page.locator('.order-list > article').filter({ has: page.getByRole('heading', { name: id, exact: true }) });
        await card.getByRole('button', { name: 'Cerrar OT', exact: true }).click();
        const close = page.getByRole('dialog', { name: 'Cerrar OT ' + id, exact: true });
        await close.getByText(/Jornada:/).waitFor();
        const day = (await close.locator('[name=workStart]').inputValue()).slice(0, 10);
        await close.locator('[name=workStart]').fill(day + 'T00:00');
        await close.locator('[name=workEnd]').fill(day + 'T01:00');
        await close.locator('[name=workHours]').fill('1');
        function transition(action) {
            return page.waitForResponse(r => r.url().endsWith('/api/harvest/orders/transition')
                && r.request().method() === 'POST' && r.request().postDataJSON().action === action);
        }
        const closedResponse = transition('close');
        await close.getByRole('button', { name: 'Confirmar cierre y horas', exact: true }).click();
        const response = await closedResponse;
        const payload = response.request().postDataJSON();
        const closed = await response.json();
        assert.equal(closed.ok, true, closed.error);
        assert.equal(closed.order.work_hours, 1);
        assert.equal(closed.order.pass_number, 2);
        assert.equal(closed.order.harvest_type, 'industrial');
        assert.equal(closed.order.operation_location_id, location?.id || false);
        assert.ok(closed.order.odoo_id > 0);
        assert.equal(payload.work_time.hours, 1);
        await close.waitFor({ state: 'hidden' });
        const approve = transition('approve');
        await card.getByRole('button', { name: 'Aprobar OT', exact: true }).click();
        const approved = await (await approve).json();
        assert.equal(approved.ok, true, approved.error);
        assert.equal(approved.order.erp_state, 'apro');
        const send = transition('send');
        await card.getByRole('button', { name: 'Enviar OT', exact: true }).click();
        const sent = await (await send).json();
        assert.equal(sent.ok, true, sent.error);
        assert.equal(sent.order.status, 'Enviada');
        assert.equal(sent.order.work_hours, 1);
        assert.equal(sent.order.can_reopen, false);
        await page.reload();
        await page.getByText(/· Harvest 0\.0\.12$/).waitFor();
        await nav.getByRole('button', { name: 'OT', exact: true }).click();
        await card.getByText('Enviada', { exact: true }).waitFor();
        await card.getByText('Industrial', { exact: true }).waitFor();
        assert.match(await card.innerText(), /Horas trabajadas por persona\s+1 h/);
        const model = crew.type === 'propio' ? 'step.cosecha.registry.line' : 'step.cosecha.tarja.line';
        const native = await context.request.post(origin + '/web/dataset/call_kw/' + model + '/search_read', {
            data: { jsonrpc: '2.0', method: 'call', params: { model, method: 'search_read',
                args: [[['registry_id', '=', closed.order.odoo_id]]], kwargs: { fields: ['employee_id', 'hrs'] } } },
        }).then(r => r.json());
        assert.ok(!native.error && native.result.length);
        assert.ok(native.result.every(row => row.hrs === 1));
        assert.ok(native.result.some(row => row.employee_id[0] === worker));
        assert.deepEqual(errors, []);
        await page.screenshot({ path: output + '.png', fullPage: true });
        fs.writeFileSync(output, JSON.stringify({ environment: policy.environment, database: policy.database,
            web_commit: policy.web_commit, user_id: policy.user_id, company_id: policy.company_id,
            native_order_id: closed.order.odoo_id, client_close_with_hours: true, client_approval_send: true,
            client_native_fields: true, native_cost_hours: true, client_reload_preserved: true }, null, 2));
        console.log('HARVEST_CLIENT_HOURS_FLOW_OK ' + policy.environment);
    } finally { await browser.close(); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });

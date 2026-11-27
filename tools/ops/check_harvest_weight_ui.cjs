const assert = require('node:assert/strict');
const fs = require('node:fs');
const { randomUUID } = require('node:crypto');
const { chromium } = require('playwright');

async function main() {
    const [origin, output, mode] = process.argv.slice(2);
    assert.match(origin, /^http:\/\/127\.0\.0\.1:\d+$/);
    assert.ok(mode === 'copy' || mode === 'live');
    const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
    try {
        const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'es-CL' });
        await context.route(`${origin}/api/harvest/**`, route => {
            return route.request().method() === 'GET' ? route.continue() : route.abort();
        });
        const page = await context.newPage();
        page.setDefaultTimeout(40000);
        await page.goto(`${origin}/cosecha/`, { waitUntil: 'domcontentloaded' });
        const build = page.getByText(/· Harvest 0\.0\.(10|11|12)$/);
        await build.waitFor();
        const version = (await build.textContent()).split('Harvest ').at(-1);
        const launcher = await context.request.get(`${origin}/harvest/open`, { maxRedirects: 0 });
        assert.equal(launcher.status(), 302);
        assert.equal(new URL(launcher.headers().location, origin).pathname, '/cosecha/');
        const nativeForm = await context.request.post(`${origin}/web/dataset/call_kw/step.cosecha.registry/get_view`, {
            data: { jsonrpc: '2.0', method: 'call', params: { model: 'step.cosecha.registry',
                method: 'get_view', args: [false, 'form'], kwargs: {} } },
        }).then(response => response.json());
        const arch = nativeForm.result?.arch;
        assert.equal(typeof arch, 'string');
        for (const field of ['mobile_packaging_id', 'mobile_standard_weight', 'mobile_kg_per_box']) {
            assert.match(arch, new RegExp(`name="${field}"`));
        }
        if (['0.0.11', '0.0.12'].includes(version)) assert.match(arch, /name="mobile_without_tarja"/);
        const data = await context.request.get(`${origin}/api/harvest/bootstrap`).then(response => response.json());
        assert.ok(data.ok && data.harvest_packagings.length);
        const packaging = data.harvest_packagings.find(row => row.kg_per_box >= 0.01);
        assert.ok(packaging, 'A Cosecha packaging with a positive weight is required');
        const workers = new Set(data.workers.map(row => row.id));
        const crew = data.crews.find(row => (row.type === 'propio' || row.contractor) &&
            (mode === 'live' || row.worker_ids?.some(id => workers.has(id))));
        const worker = crew?.worker_ids.find(id => workers.has(id));
        const center = data.cost_centers.find(row => data.farms.some(farm => farm.id === row.farm_id) &&
            data.varieties.some(variety => variety.id === row.variety_id));
        assert.ok(crew && center && data.approvers.some(user => user.id === data.user.id));
        const nav = page.getByRole('navigation', { name: 'Navegación móvil' });

        async function draft(standard) {
            await page.getByTitle('Configuración', { exact: true }).click();
            await page.locator('.setting').filter({ hasText: 'Pesaje de cosecha' })
                .getByRole('button', { name: standard ? 'Peso estándar' : 'Manual', exact: true }).click();
            await nav.getByRole('button', { name: 'OT', exact: true }).click();
            await page.getByRole('button', { name: 'Nueva OT', exact: true }).click();
            const form = page.locator('form.modal-form');
            await form.locator('[name=packaging]').selectOption(String(packaging.id));
            assert.equal(await form.locator('[name=packaging]').evaluate(select => select.required), standard);
            assert.equal(await form.locator('[name=packaging] option').count(),
                1 + data.harvest_packagings.filter(row => !standard || row.kg_per_box > 0).length);
            await form.locator('[name=id]').fill(`QA-T242-${randomUUID()}`);
            await form.locator('[name=crew]').selectOption(String(crew.id));
            await form.locator('[name=farm]').selectOption(String(center.farm_id));
            if (version === '0.0.12') {
                assert.equal(await form.locator('[name=passNumber]').evaluate(input => input.required), true);
                await form.locator('[name=passNumber]').fill('2');
                await form.locator('[name=harvestType]').selectOption('export');
                const choices = data.operation_locations.filter(row => row.farm_id === center.farm_id);
                assert.equal(await form.locator('[name=operationLocation] option').count(), choices.length + 1);
                if (choices.length) await form.locator('[name=operationLocation]').selectOption(String(choices[0].id));
            }
            await form.locator('[name=variety]').selectOption(String(center.variety_id));
            await form.locator('[name=costCenter]').selectOption(String(center.id));
            await form.getByRole('button', { name: 'Crear jornada local' }).click();
        }

        async function openTarja() {
            await nav.getByRole('button', { name: /^Registrar(?:\s|$)/ }).click();
            await page.locator('[name=tarja]').fill(`T242-${randomUUID()}`);
            await page.getByRole('button', { name: 'Abrir tarja', exact: true }).click();
        }

        await draft(true);
        await openTarja();
        const standard = page.getByLabel('Kilos estándar');
        assert.equal(await standard.evaluate(input => input.readOnly), true);
        const expected = boxes => (Math.round(boxes * Math.round(packaging.kg_per_box * 1000) / 10) / 100).toFixed(2);
        assert.equal(await standard.inputValue(), expected(2));
        await page.getByRole('button', { name: '+', exact: true }).click();
        assert.equal(await standard.inputValue(), expected(3));
        if (mode === 'copy') {
            await nav.getByRole('button', { name: 'Cuadrilla', exact: true }).click();
            await page.getByRole('button', { name: 'Seleccionar trabajador', exact: true }).click();
            const enable = page.getByRole('dialog', { name: 'Seleccionar trabajador', exact: true });
            await enable.locator('[name=worker]').selectOption(String(worker));
            await enable.getByRole('button', { name: 'Habilitar en este equipo', exact: true }).click();
            await nav.getByRole('button', { name: /^Registrar(?:\s|$)/ }).click();
            await page.locator('form.capture-card select').selectOption(String(worker));
            await page.getByLabel('Hilera', { exact: true }).fill('QA-T242');
            await page.getByRole('button', { name: 'Guardar entrega' }).click();
            await page.getByText(new RegExp(`${expected(2)} kg ·`)).waitFor();
            await page.reload();
            await nav.getByRole('button', { name: /^Registrar(?:\s|$)/ }).click();
            await page.getByText(new RegExp(`${expected(2)} kg ·`)).waitFor();
        }
        await draft(false);
        await openTarja();
        const manual = page.locator('.quantity-row input[type=number]');
        await manual.fill('9.27');
        assert.equal(await manual.evaluate(input => !input.readOnly && input.validity.valid && input.step === '0.01'), true);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        const withoutTarja = {};
        if (['0.0.11', '0.0.12'].includes(version)) {
            await page.getByTitle('Configuración', { exact: true }).click();
            await page.locator('.setting').filter({ hasText: 'Folio de tarja' })
                .getByRole('button', { name: 'Sin tarja', exact: true }).click();
            await page.locator('.setting').filter({ hasText: 'Asociar trabajador a tarja' })
                .getByText('Desactivado', { exact: true }).waitFor();
            await draft(false);
            await nav.getByRole('button', { name: /^Registrar(?:\s|$)/ }).click();
            await page.getByRole('button', { name: 'Guardar entrega' }).waitFor();
            assert.equal(await page.getByRole('button', { name: /^(Abrir|Cerrar) tarja$/ }).count(), 0);
            assert.equal(await page.getByLabel('Tarja', { exact: true }).count(), 0);
            if (mode === 'copy') {
                await page.locator('form.capture-card select').selectOption(String(worker));
                await page.getByLabel('Hilera', { exact: true }).fill('QA-T243');
                await page.locator('.quantity-row input[type=number]').fill('9.27');
                await page.getByRole('button', { name: 'Guardar entrega' }).click();
                await page.getByText(/9\.27 kg ·/).waitFor();
            }
            Object.assign(withoutTarja, { capture_without_tarja: true, worker_tarja_association_off: true });
        }
        const hours = {};
        if (version === '0.0.12') {
            await nav.getByRole('button', { name: 'OT', exact: true }).click();
            const card = page.locator('.order-list > article').first();
            await card.getByText('Número de pasada', { exact: true }).waitFor();
            await card.getByRole('button', { name: 'Cerrar OT', exact: true }).click();
            const dialog = page.getByRole('dialog', { name: /^Cerrar OT / });
            await dialog.getByText(/Jornada:/).waitFor();
            for (const name of ['workStart', 'workEnd', 'workHours']) assert.equal(await dialog.locator(`[name=${name}]`).count(), 1);
            await dialog.locator('[name=lastOrder]').check();
            assert.equal(await dialog.locator('[name=workHours]').evaluate(input => input.readOnly), true);
            await dialog.getByText(/100%/).first().waitFor();
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
            await dialog.getByRole('button', { name: 'Cancelar', exact: true }).click();
            Object.assign(hours, { ot_native_fields: true, pass_required: true, ot_work_hours: true, day_allocation: true });
        }
        fs.writeFileSync(output, JSON.stringify({ packaging_selector: true, standard_weight_readonly: true,
            manual_weight_hundredths: true, mobile_layout: true, local_weight_preserved: mode === 'copy',
            native_context: true, native_weight_form: true, harvest_launcher: true,
            company_id: data.company.id, user_id: data.user.id,
            crew_native_type_contractor: true, version, server_writes: false, ...withoutTarja, ...hours }, null, 2));
    } finally {
        await browser.close();
    }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });

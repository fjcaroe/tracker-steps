/* Read-only authenticated T201 browser acceptance. Session files remain private. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
    const proof = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const output = process.argv[3];
    fs.mkdirSync(output, { recursive: true });
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
    let page;
    try {
        const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'es-CL' });
        await context.addCookies([{ name: 'session_id', value: proof.session_id,
            domain: proof.host, path: '/', httpOnly: true, secure: true, sameSite: 'Lax' },
            { name: 'cids', value: String(proof.company_id), domain: proof.host, path: '/', secure: true }]);
        page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const dashboardResponse = () => page.waitForResponse(
            res => res.url().includes('/call_kw/step.packing.order/get_dashboard_data'), { timeout: 60000 });
        const [initialResponse] = await Promise.all([
            dashboardResponse(),
            page.goto(`https://${proof.host}/web#action=${proof.actions.dashboard}&cids=${proof.company_id}`,
                { waitUntil: 'domcontentloaded', timeout: 120000 }),
        ]);
        const initialData = (await initialResponse.json()).result;
        const cards = page.locator('.o_packing_kpis_seven > button');
        await cards.first().waitFor({ timeout: 120000 });
        assert.equal(await cards.count(), 7);
        await page.waitForFunction(count => document.querySelectorAll('.o_packing_period_filters select option').length === count, initialData.species.length + 1);
        async function changeFilter(label, action) {
            const started = Date.now();
            console.log('T201_UI_CHECK ' + label);
            const [response] = await Promise.all([dashboardResponse(), action()]);
            const body = await response.json();
            assert.ok(!body.error, label + ' RPC failed');
            await page.waitForFunction(() => !document.querySelector('.o_packing_loading') &&
                document.querySelectorAll('.o_packing_kpis_seven > button').length === 7);
            console.log('T201_UI_FILTER_OK ' + label + ' ms=' + (Date.now() - started));
            return body.result;
        }
        assert.equal(await page.locator('.o_packing_hero h1').evaluate(el => getComputedStyle(el).color), 'rgb(255, 255, 255)');
        const labels = await cards.locator('span').allTextContents();
        for (const label of ['Último día', 'Semana', 'Mes', 'Temporada']) {
            await changeFilter(label, () => page.getByRole('button', { name: label, exact: true }).click());
        }
        const species = page.locator('.o_packing_period_filters select');
        assert.equal(await species.count(), 1);
        const options = await species.locator('option').evaluateAll(rows => rows.map(row => row.value));
        console.log('T201_UI_SPECIES ' + JSON.stringify({options, supplied: initialData.species}));
        const expectedSpecies = process.env.T201_EXPECT_SPECIES_ID;
        if (expectedSpecies) assert.ok(options.includes(expectedSpecies), 'Expected real species is absent');
        if (options.length > 1) {
            await changeFilter('Especie', () => species.selectOption(options[1]));
            assert.equal(await species.inputValue(), options[1], 'Species selection must remain visible');
            await changeFilter('Todas las especies', () => species.selectOption(''));
        }
        await page.getByLabel('Desde', { exact: true }).fill('2000-01-01');
        await page.getByLabel('Hasta', { exact: true }).fill('2099-12-31');
        const result = await changeFilter('Rango manual', () => page.getByRole('button', { name: 'Aplicar', exact: true }).click());
        assert.equal(result.filters.date_from, '2000-01-01');
        assert.equal(result.filters.date_to, '2099-12-31');
        await cards.first().waitFor();
        await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.waitForTimeout(500);
        await page.locator('.o_packing_dashboard').screenshot({ path: path.join(output, 'mobile.png') });
        const overflow = await page.locator('.o_packing_kpis_seven').evaluate(el => el.scrollWidth > el.clientWidth + 1);
        assert.equal(overflow, false, 'Cards overflow on mobile');
        await page.setViewportSize({ width: 1440, height: 1000 });
        await cards.nth(1).click();
        await page.locator('.o_list_view').waitFor({ timeout: 30000 });
        assert.equal(await page.locator('.o_error_dialog').count(), 0);
        const row = page.locator('.o_data_row').first();
        let formOpened = false;
        if (await row.count()) {
            await row.locator('.o_data_cell').first().click();
            await page.locator('.o_form_view').waitFor({ timeout: 30000 });
            formOpened = true;
        }
        assert.equal(errors.length, 0, errors.join('; '));
        const report = { host: proof.host, labels, periods: 4, speciesFilter: options.length > 1,
            availableSpecies: initialData.species.length, customDates: true, whiteHeading: true, mobileOverflow: false, drilldown: true, formOpened, errors };
        fs.writeFileSync(path.join(output, 'ui-result.json'), JSON.stringify(report, null, 2));
        console.log('PACKING_DASHBOARD_UI_OK ' + JSON.stringify(report));
    } catch (error) {
        if (page) {
            await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {});
            fs.writeFileSync(path.join(output, 'failure.txt'), await page.locator('body').innerText().catch(() => ''));
        }
        throw error;
    } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });

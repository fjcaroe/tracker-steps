/* Exercise the real autocomplete and save only in an isolated QA-Cerro copy. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

async function run() {
    const proof = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const url = new URL(proof.url);
    const privateCopy = url.protocol === 'http:' && url.hostname === '127.0.0.1';
    assert.ok(privateCopy || url.origin === 'https://qa-cerroelplomo.stepsapp.cl');
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
    const errors = [];
    try {
        async function openForm(company) {
            const context = await browser.newContext({ locale: 'es-CL', viewport: { width: 1440, height: 1000 } });
            await context.addCookies([
                { name: 'session_id', value: proof.session_id, url: url.origin, httpOnly: true },
                { name: 'cids', value: String(company), url: url.origin },
            ]);
            const page = await context.newPage();
            page.on('pageerror', error => errors.push(error.message));
            if (process.env.T213_DEBUG) page.on('response', async response => {
                if (!response.url().includes('/step.export.packing.list/onchange')) return;
                const call = response.request().postDataJSON().params;
                const result = await response.json();
                const value = result.result?.value;
                console.log('T213_ONCHANGE ' + JSON.stringify({ company, changed: call.args[2],
                    context: call.kwargs.context.allowed_company_ids, specification: Object.keys(call.args[3] || {}),
                    companies: value?.step_packing_company_ids, guides: value?.available_guide_ids,
                    tags: value?.available_tag_ids, error: result.error?.data?.message }));
            });
            await page.goto(new URL(`/web#action=${proof.action}&cids=${company}`, url).href,
                { waitUntil: 'domcontentloaded', timeout: 120000 });
            await page.locator('.o_list_view').waitFor({ timeout: 120000 });
            await page.locator('.o_list_button_add').click();
            await page.locator('.o_form_view').waitFor({ timeout: 30000 });
            return page;
        }
        async function choose(page, field, search, label) {
            const input = page.locator(`.o_field_widget[name="${field}"] input`);
            await input.click();
            const model = field === 'shipment_id' ? 'step.export.export' : 'step.dispatch.guide';
            const lookup = page.waitForResponse(response => response.url().includes('/' + model + '/name_search')
                && response.request().postDataJSON()?.params?.kwargs?.name === search);
            await input.fill(search);
            const response = await lookup;
            const result = await response.json();
            assert.ok(!result.error, result.error?.data?.message);
            const criteria = response.request().postDataJSON().params.kwargs;
            assert.ok(result.result.some(row => row[1].includes(label)), `No apareció ${search} en ${field} ${JSON.stringify({ domain: criteria.args, companies: criteria.context.allowed_company_ids })}`);
            const option = page.locator('.o-autocomplete--dropdown-item').filter({ hasText: label }).first();
            await option.click();
            await page.waitForFunction(({ field, label }) =>
                document.querySelector(`.o_field_widget[name="${field}"] input`)?.value.includes(label),
            { field, label });
            assert.equal(await page.locator('.o_error_dialog').count(), 0);
        }
        const matrixPage = await openForm(proof.matrix);
        await choose(matrixPage, 'shipment_id', proof.shipment, proof.shipment);
        const branchPage = await openForm(proof.branch);
        await choose(branchPage, 'shipment_id', proof.shipment, proof.shipment);
        await choose(branchPage, 'guide_id', proof.folio, proof.guide);
        const tags = branchPage.locator('.o_field_widget[name="tag_ids"] .o_data_row');
        await tags.nth(2).waitFor();
        assert.equal(await tags.count(), 3);
        let saved = null;
        if (privateCopy) {
            const saveResponse = branchPage.waitForResponse(response => response.url().endsWith('/step.export.packing.list/web_save'));
            await branchPage.locator('.o_form_button_save').click();
            const result = await (await saveResponse).json();
            assert.ok(!result.error, result.error?.data?.message);
            assert.ok(result.result[0].id);
            assert.match(result.result[0].name, /^PL\//);
            saved = result.result[0].name;
            await branchPage.reload({ waitUntil: 'domcontentloaded' });
            await branchPage.getByText(saved, { exact: true }).first().waitFor({ timeout: 30000 });
            await tags.nth(2).waitFor();
            assert.equal(await tags.count(), 3);
        }
        assert.equal(await branchPage.locator('.o_error_dialog').count(), 0);
        assert.deepEqual(errors, []);
        console.log('T213_BROWSER_OK ' + JSON.stringify({ matrixSelector: true, branchSelector: true,
            guide: proof.folio, tags: 3, savedInCopy: saved }));
    } finally {
        await browser.close();
    }
}

run().catch(error => { console.error(error.message); process.exitCode = 1; });

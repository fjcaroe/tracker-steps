/* Read an existing Packing List from Packing and from its parent shipment. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

async function main() {
    const proof = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const url = new URL(proof.url);
    assert.ok(url.origin === 'http://127.0.0.1:18415' || url.origin === 'https://qa-cerroelplomo.stepsapp.cl');
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH });
    try {
        async function open(company, route) {
            const context = await browser.newContext({ locale: 'es-CL' });
            await context.addCookies([
                { name: 'session_id', value: proof.session_id, url: url.origin, httpOnly: true },
                { name: 'cids', value: String(company), url: url.origin },
            ]);
            const page = await context.newPage();
            await page.goto(new URL(`/web#${route}&cids=${company}`, url).href,
                { waitUntil: 'domcontentloaded', timeout: 90000 });
            return page;
        }
        const branch = await open(proof.branch, `action=${proof.action}&menu_id=${proof.menu}`);
        const row = branch.locator('.o_list_view .o_data_row').filter({ hasText: proof.folio });
        await row.first().waitFor({ timeout: 60000 });
        assert.equal(await row.count(), 1);
        await row.click();
        await branch.locator('.o_form_view').waitFor();
        await branch.locator('.o_field_widget[name="tag_ids"] .o_data_row').nth(2).waitFor();
        assert.equal(await branch.locator('.o_field_widget[name="tag_ids"] .o_data_row').count(), 3);
        const matrix = await open(proof.matrix,
            `action=${proof.shipment_action}&id=${proof.shipment}&model=step.export.export&view_type=form`);
        await matrix.getByText(/Tarjas y despachos/i).first().click({ timeout: 60000 });
        await matrix.locator('.o_field_widget[name="packing_list_ids"] .o_data_row')
            .filter({ hasText: proof.folio }).first().waitFor();
        for (const page of [branch, matrix]) assert.equal(await page.locator('.o_error_dialog').count(), 0);
        console.log('T215_BROWSER_OK ' + JSON.stringify({ packing: proof.packing,
            folio: proof.folio, branchListing: true, matrixShipment: true, tags: 3 }));
    } finally {
        await browser.close();
    }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });

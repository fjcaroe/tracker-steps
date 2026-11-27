/* Open both real forms and their correction dialogs without saving anything. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

(async () => {
    const proof = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const output = process.argv[3];
    assert.equal(proof.version, '18.0.1.1.2');
    assert.match(proof.backend_commit, /^[a-f0-9]{40}$/);
    const url = new URL(proof.url);
    assert.ok(['https://desarrollo.stepsapp.cl', 'https://cerroelplomo.stepsapp.cl',
        'https://qa-cerroelplomo.stepsapp.cl'].includes(url.origin));
    const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH});
    const results = [];
    const errors = [];
    const blocked = [];
    try {
        for (const [kind, model, id, name, action] of [
            ['receipt', 'stock.picking', proof.receipt, proof.receipt_name, proof.receipt_action],
            ['tag', 'stock.quant.package', proof.tag, proof.tag_name, proof.tag_action],
        ]) {
            const context = await browser.newContext({locale: 'es-CL', viewport: {width: 1440, height: 1000}});
            await context.addCookies([
                {name: 'session_id', value: proof.session_id, url: url.origin, httpOnly: true, secure: true},
                {name: 'cids', value: String(proof.company_id), url: url.origin, secure: true},
            ]);
            const page = await context.newPage();
            page.on('pageerror', err => errors.push(err.message));
            await page.route('**/web/dataset/**', async route => {
                const params = route.request().postDataJSON()?.params || {};
                const method = params.method || '';
                const unsafe = ['create','write','unlink','web_save','action_apply','button_validate'].includes(method)
                    || (method.startsWith('action_') && method !== 'action_step_change_received_producer'
                        && method !== 'action_get_attachment_view');
                if (unsafe) { blocked.push({model: params.model, method}); return route.abort(); }
                return route.continue();
            });
            await page.goto(`${url.origin}/web#action=${action}&model=${model}&id=${id}&view_type=form&cids=${proof.company_id}`,
                {waitUntil: 'domcontentloaded', timeout: 120000});
            await page.locator('.o_form_view').waitFor({timeout: 120000});
            await page.locator('button[name="action_step_change_received_producer"]:visible').click();
            const dialog = page.locator('.modal:visible').last();
            await dialog.locator('.o_field_widget[name="previous_producer_id"]').waitFor({timeout: 30000});
            assert.ok((await dialog.innerText()).includes(proof.producer));
            for (const tag of proof.tags) assert.ok((await dialog.innerText()).includes(tag));
            assert.equal(await dialog.locator('button[name="action_apply"]').count(), 1);
            await page.screenshot({path: `${output}.${kind}.png`, fullPage: true});
            await dialog.getByRole('button', {name: 'Cancelar', exact: true}).click();
            assert.equal(await page.locator('.o_error_dialog').count(), 0);
            results.push({kind, model, id, name, wizard: true});
            await context.close();
        }
        assert.deepEqual(blocked, []);
        assert.deepEqual(errors, []);
        fs.writeFileSync(output, JSON.stringify({ticket: 246, version: proof.version, backend_commit: proof.backend_commit, url: url.origin, company: proof.company_id,
            user: proof.user_id, forms: results, no_business_writes: true, errors}, null, 2));
        console.log('T246_BROWSER_FORMS_OK ' + url.origin);
    } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exit(1);});
